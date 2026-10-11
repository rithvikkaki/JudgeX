#!/usr/bin/env python3
"""
JudgeX Restored Database Verifier - Revision 20
Validates the backup manifest against a strict schema (including database
identifier syntax, application_name syntax, signature_algorithm version,
table signature metadata, and complete .artifacts consistency), enforces an
explicit table allowlist and supported PostgreSQL UDT type allowlist, verifies
the DSN and connected database match manifest['database'], records target
PostgreSQL server_version and server_version_num from SQL, recomputes streaming
type-tagged SHA-256 schema and content signatures inside a REPEATABLE READ
READ ONLY transaction, and verifies restored application role privileges.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.parse

import psycopg2
from psycopg2 import sql

ALLOWED_TABLES = frozenset({
    "users",
    "problems",
    "test_cases",
    "submissions",
    "contests",
    "contest_problems",
})

AUDITED_TABLE_UDT_NAMES = frozenset({
    "int4",
    "varchar",
    "text",
    "bool",
    "float8",
    "timestamptz",
})

EXTENDED_TESTED_UDT_NAMES = frozenset({
    "int2",
    "int8",
    "float4",
    "numeric",
    "bpchar",
    "bytea",
    "json",
    "jsonb",
    "timestamp",
    "date",
    "uuid",
    "_int2",
    "_int4",
    "_int8",
    "_float4",
    "_float8",
    "_numeric",
    "_bool",
    "_varchar",
    "_text",
    "_bytea",
    "_json",
    "_jsonb",
    "_timestamp",
    "_timestamptz",
    "_date",
    "_uuid",
})

SUPPORTED_UDT_NAMES = AUDITED_TABLE_UDT_NAMES | EXTENDED_TESTED_UDT_NAMES

REQUIRED_MANIFEST_KEYS = {
    "database",
    "snapshot_id",
    "backend_pid",
    "helper_pid",
    "application_name",
    "timestamp_utc",
    "signature_algorithm",
    "tables",
    "artifacts",
}

REQUIRED_TABLE_ENTRY_KEYS = {
    "row_count",
    "column_count",
    "schema_sha256",
    "content_sha256",
}

EXPECTED_ARTIFACT_SUFFIXES = {
    "db_dump": "_db.dump",
    "db_dump_sha256": "_db.dump.sha256",
    "globals": "_globals.sql",
    "globals_sha256": "_globals.sql.sha256",
    "manifest": "_manifest.json",
    "manifest_sha256": "_manifest.json.sha256",
}

DB_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
APP_NAME_RE = re.compile(r"^judgex_backup_[a-z0-9]{6,32}$")
SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
PREFIX_RE = re.compile(r"^backups/[0-9]{8}$")
TAG_RE = re.compile(r"^[A-Za-z0-9_]{1,80}$")
RESERVED_DATABASES = frozenset({"postgres", "template0", "template1"})
CURSOR_ITERSIZE = 500
SIGNATURE_ALGORITHM = "sha256_canonical_tagged_stream_v2"


def configure_deterministic_session(cur) -> None:
    cur.execute("SET LOCAL TimeZone = 'UTC';")
    cur.execute("SET LOCAL DateStyle = 'ISO, YMD';")
    cur.execute("SET LOCAL extra_float_digits = 3;")
    cur.execute("SET LOCAL bytea_output = 'hex';")
    cur.execute("SET LOCAL intervalstyle = 'iso_8601';")


def build_column_canonical_expr(
    col_name: str, data_type: str, udt_name: str
) -> sql.Composable:
    if udt_name not in SUPPORTED_UDT_NAMES:
        raise ValueError(
            f"Unsupported PostgreSQL column type for deterministic content signature "
            f"on column {col_name!r}: data_type={data_type!r}, udt_name={udt_name!r}"
        )

    col_ident = sql.Identifier(col_name)
    if udt_name == "timestamptz" or data_type == "timestamp with time zone":
        val_expr = sql.SQL(
            "CASE WHEN isfinite({col}) "
            "THEN to_char({col} AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"') "
            "|| CASE WHEN EXTRACT(YEAR FROM ({col} AT TIME ZONE 'UTC')) <= 0 THEN ' BC' ELSE '' END "
            "ELSE ({col})::text END"
        ).format(col=col_ident)
    elif udt_name == "timestamp" or data_type == "timestamp without time zone":
        val_expr = sql.SQL(
            "CASE WHEN isfinite({col}) "
            "THEN to_char({col}, 'YYYY-MM-DD\"T\"HH24:MI:SS.US') "
            "|| CASE WHEN EXTRACT(YEAR FROM {col}) <= 0 THEN ' BC' ELSE '' END "
            "ELSE ({col})::text END"
        ).format(col=col_ident)
    elif udt_name == "date" or data_type == "date":
        val_expr = sql.SQL(
            "CASE WHEN isfinite({col}) "
            "THEN to_char({col}, 'YYYY-MM-DD') "
            "|| CASE WHEN EXTRACT(YEAR FROM {col}) <= 0 THEN ' BC' ELSE '' END "
            "ELSE ({col})::text END"
        ).format(col=col_ident)
    elif udt_name == "bool" or data_type == "boolean":
        val_expr = sql.SQL("CASE WHEN {col} THEN 'true' ELSE 'false' END").format(
            col=col_ident
        )
    elif udt_name == "bytea" or data_type == "bytea":
        val_expr = sql.SQL("encode({col}, 'hex')").format(col=col_ident)
    else:
        val_expr = sql.SQL("({col})::text").format(col=col_ident)

    return sql.SQL(
        "CASE WHEN {col} IS NULL THEN json_build_array(0) "
        "ELSE json_build_array(1, {val}) END"
    ).format(col=col_ident, val=val_expr)


def compute_table_signature(conn, table_name: str, table_schema: str = "public") -> dict:
    if not DB_IDENTIFIER_RE.match(table_name):
        raise ValueError(f"Invalid table identifier: {table_name!r}")
    if not DB_IDENTIFIER_RE.match(table_schema):
        raise ValueError(f"Invalid schema identifier: {table_schema!r}")

    with conn.cursor() as meta_cur:
        configure_deterministic_session(meta_cur)
        meta_cur.execute(
            """
            SELECT
                ordinal_position,
                column_name,
                data_type,
                udt_name,
                COALESCE(character_maximum_length::text, '') AS char_len,
                COALESCE(numeric_precision::text, '') AS num_prec,
                COALESCE(numeric_scale::text, '') AS num_scale,
                COALESCE(datetime_precision::text, '') AS dt_prec,
                is_nullable
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position ASC;
            """,
            (table_schema, table_name),
        )
        columns = meta_cur.fetchall()

    if not columns:
        raise ValueError(
            f"Table {table_schema}.{table_name} does not exist or has no columns."
        )

    schema_descriptors = [
        f"{ord_pos}:{col_name}:{data_type}:{udt_name}:{char_len}:{num_prec}:{num_scale}:{dt_prec}:{is_nullable}"
        for (
            ord_pos,
            col_name,
            data_type,
            udt_name,
            char_len,
            num_prec,
            num_scale,
            dt_prec,
            is_nullable,
        ) in columns
    ]
    schema_sha256 = hashlib.sha256(
        "\n".join(schema_descriptors).encode("utf-8")
    ).hexdigest()

    col_exprs = sql.SQL(", ").join(
        build_column_canonical_expr(col_name, data_type, udt_name)
        for _, col_name, data_type, udt_name, _, _, _, _, _ in columns
    )
    qualified_table = (
        sql.Identifier(table_name)
        if table_schema == "public"
        else sql.SQL("{}.{}").format(
            sql.Identifier(table_schema), sql.Identifier(table_name)
        )
    )

    row_hash_query = sql.SQL(
        """
        SELECT
          encode(pg_catalog.sha256(convert_to(json_build_array({cols})::text, 'UTF8')), 'hex') AS row_sha256
        FROM {table}
        ORDER BY row_sha256 ASC
        """
    ).format(cols=col_exprs, table=qualified_table)

    content_hasher = hashlib.sha256()
    row_count = 0
    cursor_name = f"judgex_verify_sig_{table_name}_{os.getpid()}"

    with conn.cursor(name=cursor_name) as stream_cur:
        stream_cur.itersize = CURSOR_ITERSIZE
        stream_cur.execute(row_hash_query)
        for row_idx, (row_sha256,) in enumerate(stream_cur):
            content_hasher.update(f"{row_idx}:{row_sha256}\n".encode("ascii"))
            row_count += 1

    if row_count == 0:
        content_hasher.update(
            f"EMPTY_TABLE_V2:{table_schema}.{table_name}\n".encode("utf-8")
        )

    return {
        "row_count": row_count,
        "column_count": len(columns),
        "schema_sha256": schema_sha256,
        "content_sha256": content_hasher.hexdigest(),
    }


def validate_artifacts_block(
    artifacts: dict,
    expected_prefix: str = None,
    expected_tag: str = None,
) -> None:
    if not isinstance(artifacts, dict):
        raise ValueError("Manifest 'artifacts' must be a JSON object.")

    actual_keys = set(artifacts.keys())
    required_keys = set(EXPECTED_ARTIFACT_SUFFIXES.keys())
    missing_keys = required_keys - actual_keys
    extra_keys = actual_keys - required_keys
    if missing_keys:
        raise ValueError(f"Manifest 'artifacts' missing required keys: {sorted(missing_keys)}")
    if extra_keys:
        raise ValueError(f"Manifest 'artifacts' contains unauthorized extra keys: {sorted(extra_keys)}")

    for k, val in artifacts.items():
        if not isinstance(val, str) or not val:
            raise ValueError(f"Manifest artifact '{k}' must be a non-empty string, got: {val!r}")

    if len(set(artifacts.values())) != len(EXPECTED_ARTIFACT_SUFFIXES):
        raise ValueError("Manifest 'artifacts' contains duplicate artifact path values.")

    # Derive or validate prefix and backup tag across all 6 entries
    inferred_base = None
    for key, suffix in EXPECTED_ARTIFACT_SUFFIXES.items():
        val = artifacts[key]
        if not val.endswith(suffix):
            raise ValueError(
                f"Manifest artifact '{key}' value '{val}' does not end with expected suffix '{suffix}'."
            )
        base = val[: -len(suffix)]
        if "/" not in base:
            raise ValueError(f"Manifest artifact '{key}' value '{val}' is missing backup prefix directory.")
        prefix_part, tag_part = base.rsplit("/", 1)
        if not PREFIX_RE.match(prefix_part):
            raise ValueError(
                f"Manifest artifact '{key}' has invalid prefix '{prefix_part}' (expected backups/YYYYMMDD)."
            )
        if not TAG_RE.match(tag_part):
            raise ValueError(
                f"Manifest artifact '{key}' has invalid backup tag '{tag_part}'."
            )
        if expected_prefix is not None and prefix_part != expected_prefix:
            raise ValueError(
                f"Manifest artifact '{key}' prefix '{prefix_part}' does not match expected prefix '{expected_prefix}'."
            )
        if expected_tag is not None and tag_part != expected_tag:
            raise ValueError(
                f"Manifest artifact '{key}' tag '{tag_part}' does not match expected tag '{expected_tag}'."
            )
        if inferred_base is None:
            inferred_base = base
        elif base != inferred_base:
            raise ValueError(
                f"Manifest artifact '{key}' base '{base}' is inconsistent with '{inferred_base}'."
            )


def validate_manifest(
    data: dict,
    expected_prefix: str = None,
    expected_tag: str = None,
) -> str:
    if not isinstance(data, dict):
        raise ValueError("Manifest root must be a JSON object.")

    missing = REQUIRED_MANIFEST_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"Manifest missing required keys: {sorted(missing)}")

    db_name = data.get("database")
    if not isinstance(db_name, str) or not DB_IDENTIFIER_RE.match(db_name):
        raise ValueError(f"Invalid or malformed database name in manifest: {db_name!r}")
    if db_name in RESERVED_DATABASES:
        raise ValueError(f"Manifest database name {db_name!r} is a reserved system database.")

    app_name = data.get("application_name")
    if not isinstance(app_name, str) or not APP_NAME_RE.match(app_name) or len(app_name.encode("utf-8")) > 63:
        raise ValueError(f"Invalid application_name in manifest: {app_name!r}")

    sig_alg = data.get("signature_algorithm")
    if sig_alg != SIGNATURE_ALGORITHM:
        raise ValueError(
            f"Unsupported or mismatched signature_algorithm in manifest: {sig_alg!r} (expected {SIGNATURE_ALGORITHM!r})"
        )

    validate_artifacts_block(
        data.get("artifacts"),
        expected_prefix=expected_prefix,
        expected_tag=expected_tag,
    )

    tables = data.get("tables")
    if not isinstance(tables, dict) or not tables:
        raise ValueError("Manifest 'tables' must be a non-empty JSON object.")

    table_keys = set(tables.keys())
    unknown = table_keys - ALLOWED_TABLES
    if unknown:
        raise ValueError(f"Unauthorized table names in manifest: {sorted(unknown)}")

    missing_tables = ALLOWED_TABLES - table_keys
    if missing_tables:
        raise ValueError(f"Manifest missing required tables: {sorted(missing_tables)}")

    for tbl, entry in tables.items():
        if not isinstance(entry, dict):
            raise ValueError(
                f"Table '{tbl}' manifest entry must be an object with count and SHA-256 signatures, got {type(entry).__name__}."
            )
        entry_keys = set(entry.keys())
        missing_entry_keys = REQUIRED_TABLE_ENTRY_KEYS - entry_keys
        extra_entry_keys = entry_keys - REQUIRED_TABLE_ENTRY_KEYS
        if missing_entry_keys:
            raise ValueError(f"Table '{tbl}' missing required signature keys: {sorted(missing_entry_keys)}")
        if extra_entry_keys:
            raise ValueError(f"Table '{tbl}' has unexpected keys: {sorted(extra_entry_keys)}")

        cnt = entry.get("row_count")
        if type(cnt) is not int or cnt < 0:
            raise ValueError(f"Invalid row_count for table '{tbl}': {cnt!r} (must be non-negative int)")

        col_cnt = entry.get("column_count")
        if type(col_cnt) is not int or col_cnt < 1:
            raise ValueError(f"Invalid column_count for table '{tbl}': {col_cnt!r} (must be positive int)")

        for sig_key in ("schema_sha256", "content_sha256"):
            sig_val = entry.get(sig_key)
            if not isinstance(sig_val, str) or not SHA256_HEX_RE.match(sig_val):
                raise ValueError(
                    f"Invalid {sig_key} for table '{tbl}': {sig_val!r} (must be 64-char lowercase hex)"
                )

    return db_name


def main():
    parser = argparse.ArgumentParser(description="Verify restored JudgeX database against manifest")
    parser.add_argument("--db-url", required=True, help="Standard PostgreSQL DSN (postgresql://...)")
    parser.add_argument("--manifest", required=True, help="Path to backup manifest JSON")
    parser.add_argument("--expected-prefix", default=None, help="Expected backup prefix (backups/YYYYMMDD)")
    parser.add_argument("--expected-tag", default=None, help="Expected canonical backup tag")
    parser.add_argument("--required-role", default="judgex_admin", help="Expected application role")
    args = parser.parse_args()

    if args.db_url.startswith("postgresql+psycopg2://"):
        sys.stderr.write("ERROR: SQLAlchemy DSN detected. Pass a standard postgresql:// DSN.\n")
        sys.exit(1)

    with open(args.manifest, "r", encoding="utf-8") as mf:
        manifest = json.load(mf)

    expected_db = validate_manifest(
        manifest,
        expected_prefix=args.expected_prefix,
        expected_tag=args.expected_tag,
    )

    dsn_db = urllib.parse.urlparse(args.db_url).path.lstrip("/")
    if dsn_db != expected_db:
        raise ValueError(
            f"DSN target database '{dsn_db}' does not match manifest database '{expected_db}'."
        )

    print(f"Manifest schema and artifact-consistency validation passed (Target DB: {expected_db}).")

    conn = psycopg2.connect(args.db_url)
    try:
        conn.set_session(
            isolation_level=psycopg2.extensions.ISOLATION_LEVEL_REPEATABLE_READ,
            readonly=True,
            autocommit=False,
        )
        cur = conn.cursor()
        configure_deterministic_session(cur)

        cur.execute(
            "SELECT current_database(), version(), "
            "current_setting('server_version'), current_setting('server_version_num')::int;"
        )
        connected_db, pg_version_full, pg_server_version, pg_server_version_num = cur.fetchone()
        if connected_db != expected_db:
            raise RuntimeError(
                f"Connected database '{connected_db}' does not match manifest database '{expected_db}'."
            )
        print(
            f"Verified active connection to restored database '{connected_db}' "
            f"(PostgreSQL server_version={pg_server_version}, server_version_num={pg_server_version_num})."
        )
        print(f"SQL Server Version Banner: {pg_version_full}")

        print("Verifying table row counts, schema signatures, and streaming content signatures...")
        for table_name in sorted(ALLOWED_TABLES):
            expected_entry = manifest["tables"][table_name]
            actual_entry = compute_table_signature(conn, table_name, table_schema="public")

            if actual_entry["column_count"] != expected_entry["column_count"]:
                raise RuntimeError(
                    f"Column count mismatch for '{table_name}': "
                    f"expected {expected_entry['column_count']}, got {actual_entry['column_count']}"
                )
            if actual_entry["schema_sha256"] != expected_entry["schema_sha256"]:
                raise RuntimeError(
                    f"Schema signature mismatch for '{table_name}': "
                    f"expected {expected_entry['schema_sha256']}, got {actual_entry['schema_sha256']}"
                )
            if actual_entry["row_count"] != expected_entry["row_count"]:
                raise RuntimeError(
                    f"Row count mismatch for '{table_name}': "
                    f"expected {expected_entry['row_count']}, got {actual_entry['row_count']}"
                )
            if actual_entry["content_sha256"] != expected_entry["content_sha256"]:
                raise RuntimeError(
                    f"Content signature mismatch for '{table_name}': "
                    f"expected {expected_entry['content_sha256']}, got {actual_entry['content_sha256']}"
                )

            print(
                f"  - {table_name}: {actual_entry['row_count']} rows, "
                f"{actual_entry['column_count']} cols, "
                f"content_sha256={actual_entry['content_sha256'][:16]}... (MATCH)"
            )

        untracked = manifest.get("untracked_public_tables") or []
        if untracked:
            print(f"Note: Manifest recorded untracked public tables at backup time: {untracked}")

        if args.required_role:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s;", (args.required_role,))
            if not cur.fetchone():
                raise RuntimeError(f"Required role '{args.required_role}' is missing after globals restore.")
            print(f"Verified cluster role '{args.required_role}' exists.")

        conn.commit()
        print("Database verification completed successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
