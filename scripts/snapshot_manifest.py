#!/usr/bin/env python3
"""
JudgeX Snapshot & Manifest Coordinator - Revision 20
Validates RUN_ID syntax and application_name byte length before startup,
records process identity (PID + /proc/self/stat starttime) immediately,
exports a REPEATABLE READ READ ONLY PostgreSQL transaction snapshot,
records PostgreSQL server_version and server_version_num from SQL,
enforces an explicit allowlist of supported PostgreSQL UDT data types
(failing closed on unsupported types), computes exact row counts, full
column-precision schema signatures, and streaming deterministic type-tagged
SHA-256 content signatures inside that snapshot using a server-side named
cursor, records canonical database name from current_database(), and holds
the snapshot open until signaled via token file (RELEASE or ABORT).
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import time

import psycopg2
from psycopg2 import sql

ALLOWED_TABLES = (
    "users",
    "problems",
    "test_cases",
    "submissions",
    "contests",
    "contest_problems",
)

# Exact UDT types present in the 6 JudgeX production tables (app/models/models.py + migrations)
AUDITED_TABLE_UDT_NAMES = frozenset({
    "int4",         # INTEGER (id, user_id, problem_id, contest_id, time_limit_ms, memory_limit_kb, etc.)
    "varchar",      # VARCHAR(N) (username, email, password_hash, role, slug, title, difficulty, language, verdict, status, worker_id)
    "text",         # TEXT (statement, input_data, expected_output, source_code, compile_output, error_message, description)
    "bool",         # BOOLEAN (is_active, is_public, is_sample)
    "float8",       # DOUBLE PRECISION (submissions.execution_time_ms)
    "timestamptz",  # TIMESTAMP WITH TIME ZONE (created_at, updated_at, submitted_at, judged_at, start_time, end_time)
})

# Additional PostgreSQL types explicitly canonicalized and regression-tested via pg_dump/pg_restore
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

IGNORED_PUBLIC_TABLES = frozenset({"alembic_version"})
RUN_ID_RE = re.compile(r"^[a-z0-9]{6,32}$")
DB_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
RESERVED_DATABASES = frozenset({"postgres", "template0", "template1"})
CURSOR_ITERSIZE = 500
SIGNATURE_ALGORITHM = "sha256_canonical_tagged_stream_v2"


def normalize_dsn(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql://" + url[len("postgresql+psycopg2://") :]
    return url


def validate_run_id(run_id: str) -> str:
    if not isinstance(run_id, str) or not RUN_ID_RE.match(run_id):
        raise ValueError(
            f"Invalid run_id {run_id!r}: must match ^[a-z0-9]{{6,32}}$"
        )
    app_name = f"judgex_backup_{run_id}"
    if len(app_name.encode("utf-8")) > 63:
        raise ValueError(
            f"Derived application_name {app_name!r} exceeds PostgreSQL 63-byte NAMEDATALEN limit"
        )
    return app_name


def get_self_starttime() -> str:
    """Reads Linux kernel process starttime (field 22 of /proc/self/stat)."""
    try:
        with open("/proc/self/stat", "r", encoding="utf-8") as sf:
            stat_content = sf.read()
        after_comm = stat_content.rsplit(")", 1)[1].split()
        return after_comm[19]
    except Exception:
        return "unknown"


def configure_deterministic_session(cur) -> None:
    """
    Normalizes session formatting settings inside the current transaction so
    canonical text/JSON/array/numeric/float/bytea/timestamp serialization is
    identical across environments and session time zones.
    """
    cur.execute("SET LOCAL TimeZone = 'UTC';")
    cur.execute("SET LOCAL DateStyle = 'ISO, YMD';")
    cur.execute("SET LOCAL extra_float_digits = 3;")
    cur.execute("SET LOCAL bytea_output = 'hex';")
    cur.execute("SET LOCAL intervalstyle = 'iso_8601';")


def build_column_canonical_expr(
    col_name: str, data_type: str, udt_name: str
) -> sql.Composable:
    """
    Builds a deterministic, type-tagged canonical SQL expression for a single column:
    - Enforces that udt_name is in SUPPORTED_UDT_NAMES (fails closed on unsupported types).
    - SQL NULL is encoded as json_build_array(0) -> '[0]'.
    - Non-NULL values are encoded as json_build_array(1, <canonical_text>) -> '[1, "..."]'.
      This guarantees SQL NULL never collides with '', 'null', 'null'::json, or 'null'::jsonb.
    - timestamptz is explicitly normalized to UTC ('YYYY-MM-DD"T"HH24:MI:SS.US"Z"', plus ' BC' if <= 0).
    - timestamp without time zone is formatted as 'YYYY-MM-DD"T"HH24:MI:SS.US' (plus ' BC' if <= 0).
    - date is formatted as 'YYYY-MM-DD' (plus ' BC' if <= 0).
    - bool is formatted as 'true' or 'false'.
    - bytea is encoded via encode(col, 'hex').
    - numeric, float8/float4, int2/int4/int8, text/varchar/bpchar, uuid, json, jsonb,
      and supported arrays use canonical PostgreSQL text output under the normalized
      transaction session.
    """
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
    """
    Computes deterministic row_count, column_count, schema_sha256, and streaming
    content_sha256 for a table inside the caller's active REPEATABLE READ
    transaction without loading the full table into client memory.
    """
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
    cursor_name = f"judgex_sig_{table_name}_{os.getpid()}"

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


def discover_untracked_public_tables(cur) -> list:
    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name ASC;
        """
    )
    all_public = [r[0] for r in cur.fetchall()]
    known = set(ALLOWED_TABLES) | IGNORED_PUBLIC_TABLES
    return [t for t in all_public if t not in known]


def main():
    parser = argparse.ArgumentParser(description="JudgeX Snapshot Coordinator")
    parser.add_argument("--db-url", required=True, help="PostgreSQL connection DSN")
    parser.add_argument("--token-dir", required=True, help="Isolated directory for coordination tokens")
    parser.add_argument("--manifest-out", required=True, help="Output file path for JSON manifest")
    parser.add_argument("--run-id", required=True, help="Unique run identifier for application_name")
    parser.add_argument("--timeout", type=int, default=300, help="Max seconds to hold snapshot open")
    args = parser.parse_args()

    # Validate run_id and derived application_name BEFORE touching filesystem or DB
    try:
        app_name = validate_run_id(args.run_id)
    except Exception as exc:
        sys.stderr.write(f"[snapshot_manifest] INVALID_RUN_ID: {exc}\n")
        sys.exit(1)

    os.makedirs(args.token_dir, exist_ok=True)
    helper_pid = os.getpid()
    helper_starttime = get_self_starttime()

    # 0. Publish STARTED token immediately before DB connection so early failures are tracked
    started_tmp = os.path.join(args.token_dir, f"STARTED.helper.{helper_pid}.tmp")
    started_final = os.path.join(args.token_dir, "STARTED")
    with open(started_tmp, "w", encoding="utf-8") as stf:
        stf.write(
            f"HELPER_PID={helper_pid}\n"
            f"STARTTIME={helper_starttime}\n"
            f"RUN_ID={args.run_id}\n"
        )
    os.replace(started_tmp, started_final)

    dsn = normalize_dsn(args.db_url)

    conn = None
    try:
        conn = psycopg2.connect(dsn, application_name=app_name)
        conn.set_session(
            isolation_level=psycopg2.extensions.ISOLATION_LEVEL_REPEATABLE_READ,
            readonly=True,
            autocommit=False,
        )
        cur = conn.cursor()
        configure_deterministic_session(cur)

        # 1. Obtain canonical database name and PostgreSQL server version from active connection
        cur.execute(
            "SELECT current_database(), version(), "
            "current_setting('server_version'), current_setting('server_version_num')::int;"
        )
        db_name, pg_version_full, pg_server_version, pg_server_version_num = cur.fetchone()
        if not isinstance(db_name, str) or not DB_IDENTIFIER_RE.match(db_name) or db_name in RESERVED_DATABASES:
            raise ValueError(f"Invalid or reserved target database name: {db_name!r}")

        # 2. Export transaction snapshot
        cur.execute("SELECT pg_export_snapshot();")
        snapshot_id = cur.fetchone()[0]

        # 3. Capture backend PID for deterministic session tracking
        cur.execute("SELECT pg_backend_pid();")
        backend_pid = cur.fetchone()[0]

        # 4. Compute streaming table signatures and counts inside the exact same REPEATABLE READ snapshot
        table_signatures = {}
        for table_name in ALLOWED_TABLES:
            sig = compute_table_signature(conn, table_name, table_schema="public")
            if type(sig["row_count"]) is not int or sig["row_count"] < 0:
                raise ValueError(f"Invalid row count for {table_name}: {sig['row_count']!r}")
            table_signatures[table_name] = sig

        untracked_tables = discover_untracked_public_tables(cur)
        if untracked_tables:
            sys.stderr.write(
                f"[snapshot_manifest] WARNING: Untracked public tables detected outside ALLOWED_TABLES: {untracked_tables}\n"
            )

        # 5. Write preliminary manifest atomically
        manifest_data = {
            "manifest_version": 2,
            "database": db_name,
            "postgres_server_version": pg_server_version,
            "postgres_server_version_num": pg_server_version_num,
            "postgres_version_banner": pg_version_full,
            "snapshot_id": snapshot_id,
            "backend_pid": backend_pid,
            "helper_pid": helper_pid,
            "helper_starttime": helper_starttime,
            "application_name": app_name,
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "signature_algorithm": SIGNATURE_ALGORITHM,
            "tables": table_signatures,
            "untracked_public_tables": untracked_tables,
        }

        tmp_manifest = f"{args.manifest_out}.tmp"
        with open(tmp_manifest, "w", encoding="utf-8") as mf:
            json.dump(manifest_data, mf, indent=2)
        os.replace(tmp_manifest, args.manifest_out)

        # 6. Publish SNAPSHOT_READY token atomically
        ready_tmp = os.path.join(args.token_dir, "SNAPSHOT_READY.tmp")
        ready_final = os.path.join(args.token_dir, "SNAPSHOT_READY")
        with open(ready_tmp, "w", encoding="utf-8") as rf:
            rf.write(
                f"SNAPSHOT_ID={snapshot_id}\n"
                f"BACKEND_PID={backend_pid}\n"
                f"HELPER_PID={helper_pid}\n"
                f"STARTTIME={helper_starttime}\n"
                f"DATABASE={db_name}\n"
                f"SERVER_VERSION={pg_server_version}\n"
                f"SERVER_VERSION_NUM={pg_server_version_num}\n"
            )
        os.replace(ready_tmp, ready_final)

        # 7. Wait for RELEASE or ABORT token while verifying connection health
        release_path = os.path.join(args.token_dir, "RELEASE")
        abort_path = os.path.join(args.token_dir, "ABORT")
        deadline = time.monotonic() + args.timeout

        while time.monotonic() < deadline:
            if os.path.exists(abort_path):
                sys.stderr.write("[snapshot_manifest] ABORT token detected. Rolling back snapshot.\n")
                conn.rollback()
                conn.close()
                sys.exit(2)

            if os.path.exists(release_path):
                conn.commit()
                conn.close()
                sys.exit(0)

            cur.execute("SELECT 1;")
            if cur.fetchone()[0] != 1:
                raise RuntimeError("Transaction health check failed")

            time.sleep(0.2)

        sys.stderr.write("[snapshot_manifest] ERROR: Timeout waiting for RELEASE/ABORT token.\n")
        conn.rollback()
        conn.close()
        sys.exit(3)

    except Exception as exc:
        sys.stderr.write(f"[snapshot_manifest] FATAL: {exc}\n")
        try:
            err_path = os.path.join(args.token_dir, "ERROR")
            with open(err_path, "w", encoding="utf-8") as ef:
                ef.write(f"{exc}\n")
        except Exception:
            pass
        if conn is not None:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
        sys.exit(1)


if __name__ == "__main__":
    main()
