#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# JudgeX Production Restore & Verification Script - Revision 19
# Pre-Restore Artifact-Manifest Consistency Validation, Manifest-Driven Target
# Database Resolution, Deterministic Multi-Network Discovery, Active Container
# Reachability Check, Parameterized SQL & Streaming Type-Tagged Content-Signature
# Verification
# ==============================================================================

export LC_ALL=C
export MSYS_NO_PATHCONV=1
umask 077

OCI_BUCKET_NAME="${OCI_BUCKET_NAME:-judgex-backups}"
if [[ $# -ge 1 ]]; then
  BACKUP_DATE="$1"
elif [[ "${BACKUP_DATE_OVERRIDE+x}" == "x" ]]; then
  BACKUP_DATE="${BACKUP_DATE_OVERRIDE}"
else
  BACKUP_DATE="$(date -u +"%Y%m%d")"
fi

API_CONTAINER="${API_CONTAINER:-online_judge_api}"
RESTORE_NETWORK="${RESTORE_NETWORK:-}"
RESTORE_CONTAINER="judgex_restore_test_$(openssl rand -hex 4)"
RESTORE_PASSWORD=$(openssl rand -hex 16)

SELECTED_NETWORK="NONE"
MANIFEST_DB="UNSET"
MANIFEST_ARTIFACTS_VALIDATED=0
RESTORE_CONTAINER_STARTED=0
RESTORED_DB_CONFIRMED=0
RESTORE_PG_IMAGE="postgres:16-alpine"
RESTORE_PG_SERVER_VERSION="UNCHECKED"
RESTORE_PG_SERVER_VERSION_NUM="UNCHECKED"

# Pre-execution validation of BACKUP_DATE and optional BACKUP_TAG_OVERRIDE
if [[ -z "${BACKUP_DATE}" ]] || [[ ! "${BACKUP_DATE}" =~ ^[0-9]{8}$ ]]; then
  echo "ERROR: Invalid BACKUP_DATE '${BACKUP_DATE}' (must match ^[0-9]{8}$)." >&2
  exit 1
fi

if [[ "${BACKUP_TAG_OVERRIDE+x}" == "x" ]]; then
  if [[ -z "${BACKUP_TAG_OVERRIDE}" ]] || [[ ! "${BACKUP_TAG_OVERRIDE}" =~ ^[A-Za-z0-9_]{1,80}$ ]]; then
    echo "ERROR: Invalid BACKUP_TAG_OVERRIDE '${BACKUP_TAG_OVERRIDE}' (must match ^[A-Za-z0-9_]{1,80}$)." >&2
    exit 1
  fi
fi

WORK_DIR=$(mktemp -d -t "judgex_restore_XXXXXX")
if command -v cygpath >/dev/null 2>&1; then
  WORK_DIR=$(cygpath -m "${WORK_DIR}")
fi

cleanup_restore() {
  local exit_code=$?
  set +e
  echo "Cleaning up restore resources (Exit code: ${exit_code})..." >&2
  docker rm -f "${RESTORE_CONTAINER}" >/dev/null 2>&1 || true
  docker exec "${API_CONTAINER}" rm -f "/tmp/verify_manifest_${RESTORE_CONTAINER}.json" >/dev/null 2>&1 || true
  rm -rf "${WORK_DIR}" 2>/dev/null || true

  echo "--------------------------------------------------------" >&2
  echo "[RESTORE_VERIFICATION_SUMMARY]" >&2
  echo "FINAL_EXIT_CODE=${exit_code}" >&2
  echo "MANIFEST_ARTIFACTS_VALIDATED=${MANIFEST_ARTIFACTS_VALIDATED}" >&2
  echo "RESTORE_CONTAINER_STARTED=${RESTORE_CONTAINER_STARTED}" >&2
  echo "RESTORE_PG_IMAGE=${RESTORE_PG_IMAGE}" >&2
  echo "RESTORE_PG_SERVER_VERSION=${RESTORE_PG_SERVER_VERSION}" >&2
  echo "RESTORE_PG_SERVER_VERSION_NUM=${RESTORE_PG_SERVER_VERSION_NUM}" >&2
  echo "SELECTED_NETWORK=${SELECTED_NETWORK}" >&2
  echo "MANIFEST_DATABASE=${MANIFEST_DB}" >&2
  echo "RESTORED_DB_CONFIRMED=${RESTORED_DB_CONFIRMED}" >&2
  echo "--------------------------------------------------------" >&2
  exit "${exit_code}"
}

trap cleanup_restore EXIT

# 1. Discover latest backup via canonical _db.dump suffix (or BACKUP_TAG_OVERRIDE)
echo "Discovering backup in bucket '${OCI_BUCKET_NAME}' for date '${BACKUP_DATE}'..."
LIST_OUT=$(oci os object list -bn "${OCI_BUCKET_NAME}" --prefix "backups/${BACKUP_DATE}/" --output json)

if [[ -n "${BACKUP_TAG_OVERRIDE:-}" ]]; then
  BACKUP_TAG="${BACKUP_TAG_OVERRIDE}"
else
  LATEST_DUMP=$(echo "${LIST_OUT}" | jq -r '.data[].name | select(endswith("_db.dump"))' | sort | tail -n 1)
  if [[ -z "${LATEST_DUMP}" ]]; then
    echo "ERROR: No canonical backup dump found for ${BACKUP_DATE}." >&2
    exit 1
  fi
  BACKUP_TAG=$(basename "${LATEST_DUMP%_db.dump}")
fi

if [[ -z "${BACKUP_TAG}" ]] || [[ ! "${BACKUP_TAG}" =~ ^[A-Za-z0-9_]{1,80}$ ]]; then
  echo "ERROR: Invalid discovered BACKUP_TAG '${BACKUP_TAG}'." >&2
  exit 1
fi

PREFIX="backups/${BACKUP_DATE}"
echo "Identified canonical backup tag: ${BACKUP_TAG}"

REMOTE_DB="${PREFIX}/${BACKUP_TAG}_db.dump"
REMOTE_DB_SHA="${REMOTE_DB}.sha256"
REMOTE_GLOBALS="${PREFIX}/${BACKUP_TAG}_globals.sql"
REMOTE_GLOBALS_SHA="${REMOTE_GLOBALS}.sha256"
REMOTE_MANIFEST="${PREFIX}/${BACKUP_TAG}_manifest.json"
REMOTE_MANIFEST_SHA="${REMOTE_MANIFEST}.sha256"

REQUIRED_ARTIFACTS=(
  "${REMOTE_DB}"
  "${REMOTE_DB_SHA}"
  "${REMOTE_GLOBALS}"
  "${REMOTE_GLOBALS_SHA}"
  "${REMOTE_MANIFEST}"
  "${REMOTE_MANIFEST_SHA}"
)

# Verify all 6 artifacts exist before downloading
EXISTING_NAMES=$(echo "${LIST_OUT}" | jq -r '.data[].name // empty')
for req in "${REQUIRED_ARTIFACTS[@]}"; do
  if ! echo "${EXISTING_NAMES}" | grep -Fxq "${req}"; then
    echo "ERROR: Missing required canonical artifact in OCI bucket: ${req}" >&2
    exit 1
  fi
done

LOCAL_DB="${WORK_DIR}/${BACKUP_TAG}_db.dump"
LOCAL_GLOBALS="${WORK_DIR}/${BACKUP_TAG}_globals.sql"
LOCAL_MANIFEST="${WORK_DIR}/${BACKUP_TAG}_manifest.json"

# 2. Download all 6 artifacts & Verify Checksums BEFORE starting any container
echo "Downloading all 6 canonical artifacts..."
oci os object get -bn "${OCI_BUCKET_NAME}" --name "${REMOTE_DB}" --file "${LOCAL_DB}"
oci os object get -bn "${OCI_BUCKET_NAME}" --name "${REMOTE_DB_SHA}" --file "${LOCAL_DB}.sha256"
oci os object get -bn "${OCI_BUCKET_NAME}" --name "${REMOTE_GLOBALS}" --file "${LOCAL_GLOBALS}"
oci os object get -bn "${OCI_BUCKET_NAME}" --name "${REMOTE_GLOBALS_SHA}" --file "${LOCAL_GLOBALS}.sha256"
oci os object get -bn "${OCI_BUCKET_NAME}" --name "${REMOTE_MANIFEST}" --file "${LOCAL_MANIFEST}"
oci os object get -bn "${OCI_BUCKET_NAME}" --name "${REMOTE_MANIFEST_SHA}" --file "${LOCAL_MANIFEST}.sha256"

echo "Verifying SHA-256 checksums..."
(cd "${WORK_DIR}" && sha256sum -c "${BACKUP_TAG}_db.dump.sha256")
(cd "${WORK_DIR}" && sha256sum -c "${BACKUP_TAG}_globals.sql.sha256")
(cd "${WORK_DIR}" && sha256sum -c "${BACKUP_TAG}_manifest.json.sha256")
echo "All checksums verified successfully."

# 3. Strictly Validate Manifest .artifacts Consistency & .database BEFORE starting restore container
echo "Validating manifest .artifacts consistency against prefix '${PREFIX}' and tag '${BACKUP_TAG}'..."
ARTIFACTS_CHECK=$(jq -r \
  --arg prefix "${PREFIX}" \
  --arg tag "${BACKUP_TAG}" \
  '
  if (.artifacts | type) != "object" then
    "ERR:artifacts_not_object"
  elif ((.artifacts | keys | sort) != ["db_dump", "db_dump_sha256", "globals", "globals_sha256", "manifest", "manifest_sha256"]) then
    "ERR:keys_mismatch"
  elif ([.artifacts[] | select(type != "string" or length == 0)] | length) > 0 then
    "ERR:non_string_or_empty_value"
  elif ((.artifacts | to_entries | map(.value) | unique | length) != 6) then
    "ERR:duplicate_artifact_values"
  elif .artifacts.db_dump != ($prefix + "/" + $tag + "_db.dump") then
    "ERR:db_dump_mismatch:" + .artifacts.db_dump
  elif .artifacts.db_dump_sha256 != ($prefix + "/" + $tag + "_db.dump.sha256") then
    "ERR:db_dump_sha256_mismatch:" + .artifacts.db_dump_sha256
  elif .artifacts.globals != ($prefix + "/" + $tag + "_globals.sql") then
    "ERR:globals_mismatch:" + .artifacts.globals
  elif .artifacts.globals_sha256 != ($prefix + "/" + $tag + "_globals.sql.sha256") then
    "ERR:globals_sha256_mismatch:" + .artifacts.globals_sha256
  elif .artifacts.manifest != ($prefix + "/" + $tag + "_manifest.json") then
    "ERR:manifest_mismatch:" + .artifacts.manifest
  elif .artifacts.manifest_sha256 != ($prefix + "/" + $tag + "_manifest.json.sha256") then
    "ERR:manifest_sha256_mismatch:" + .artifacts.manifest_sha256
  else
    "VALID"
  end
  ' "${LOCAL_MANIFEST}" 2>/dev/null || echo "ERR:jq_execution_failed")

if [[ "${ARTIFACTS_CHECK}" != "VALID" ]]; then
  echo "ERROR: Manifest .artifacts consistency validation failed (${ARTIFACTS_CHECK}). Aborting before container launch." >&2
  exit 1
fi
MANIFEST_ARTIFACTS_VALIDATED=1
echo "Validated all 6 manifest .artifacts paths match '${PREFIX}/${BACKUP_TAG}_*'."

MANIFEST_DB=$(jq -r 'if (.database | type) == "string" then .database else "" end' "${LOCAL_MANIFEST}" 2>/dev/null || echo "")
if [[ -z "${MANIFEST_DB}" ]] || [[ ! "${MANIFEST_DB}" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]]; then
  echo "ERROR: Missing or malformed database name in manifest: '${MANIFEST_DB}'" >&2
  exit 1
fi
if [[ "${MANIFEST_DB}" == "postgres" || "${MANIFEST_DB}" == "template0" || "${MANIFEST_DB}" == "template1" ]]; then
  echo "ERROR: Manifest database name '${MANIFEST_DB}' is a reserved system database." >&2
  exit 1
fi
echo "Validated target database name from manifest: '${MANIFEST_DB}'"

# 4. Deterministic Shared Docker Network Selection (Supports Single & Multi-Network Containers)
if ! docker inspect "${API_CONTAINER}" >/dev/null 2>&1; then
  echo "ERROR: API container '${API_CONTAINER}' does not exist or is not inspectable." >&2
  exit 1
fi

RAW_NETWORKS=$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}' "${API_CONTAINER}" 2>/dev/null || true)
ATTACHED_NETWORKS=$(echo "${RAW_NETWORKS}" | sed '/^[[:space:]]*$/d' | LC_ALL=C sort -u)

if [[ -z "${ATTACHED_NETWORKS}" ]]; then
  echo "ERROR: No Docker networks found on API container '${API_CONTAINER}'." >&2
  exit 1
fi

USABLE_NETWORKS=()
while IFS= read -r net_name; do
  [[ -z "${net_name}" ]] && continue
  if [[ "${net_name}" == "none" || "${net_name}" == "host" || "${net_name}" == "bridge" ]]; then
    continue
  fi
  if docker network inspect "${net_name}" >/dev/null 2>&1; then
    USABLE_NETWORKS+=("${net_name}")
  fi
done <<< "${ATTACHED_NETWORKS}"

if [[ ${#USABLE_NETWORKS[@]} -eq 0 ]]; then
  echo "ERROR: API container '${API_CONTAINER}' has no usable user-defined shared Docker network (attached: ${ATTACHED_NETWORKS//$'\n'/, })." >&2
  exit 1
fi

if [[ -n "${RESTORE_NETWORK}" ]]; then
  for net_name in "${USABLE_NETWORKS[@]}"; do
    if [[ "${net_name}" == "${RESTORE_NETWORK}" ]]; then
      SELECTED_NETWORK="${net_name}"
      break
    fi
  done
  if [[ "${SELECTED_NETWORK}" == "NONE" ]]; then
    echo "ERROR: Configured RESTORE_NETWORK='${RESTORE_NETWORK}' is not attached as a usable network on '${API_CONTAINER}' (usable: ${USABLE_NETWORKS[*]})." >&2
    exit 1
  fi
  echo "Using explicitly configured shared Docker network: '${SELECTED_NETWORK}' (from usable: ${USABLE_NETWORKS[*]})"
else
  SELECTED_NETWORK="${USABLE_NETWORKS[0]}"
  echo "Deterministically selected shared Docker network: '${SELECTED_NETWORK}' (from usable: ${USABLE_NETWORKS[*]})"
fi

# 5. Start Ephemeral PostgreSQL Container on Selected Shared Network
echo "Starting ephemeral container '${RESTORE_CONTAINER}' on network '${SELECTED_NETWORK}'..."
docker run -d \
  --name "${RESTORE_CONTAINER}" \
  --network "${SELECTED_NETWORK}" \
  --network-alias "${RESTORE_CONTAINER}" \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD="${RESTORE_PASSWORD}" \
  -e POSTGRES_DB=postgres \
  -e TZ="${RESTORE_CONTAINER_TZ:-UTC}" \
  -e PGTZ="${RESTORE_CONTAINER_TZ:-UTC}" \
  postgres:16-alpine
RESTORE_CONTAINER_STARTED=1

READY_WAIT=0
until docker exec "${RESTORE_CONTAINER}" pg_isready -U postgres >/dev/null 2>&1; do
  READY_WAIT=$((READY_WAIT + 1))
  if [[ ${READY_WAIT} -ge 30 ]]; then
    echo "ERROR: Timed out waiting for ephemeral PostgreSQL container '${RESTORE_CONTAINER}'." >&2
    exit 1
  fi
  sleep 0.5
done

RESTORE_PG_VER_LINE=$(docker exec -i "${RESTORE_CONTAINER}" psql -U postgres -d postgres -t -A -c "SELECT current_setting('server_version') || '|' || current_setting('server_version_num');" 2>/dev/null || echo "UNKNOWN|UNKNOWN")
RESTORE_PG_SERVER_VERSION="${RESTORE_PG_VER_LINE%%|*}"
RESTORE_PG_SERVER_VERSION_NUM="${RESTORE_PG_VER_LINE##*|}"
echo "Ephemeral restore container '${RESTORE_CONTAINER}' online (Image: ${RESTORE_PG_IMAGE}, SQL server_version=${RESTORE_PG_SERVER_VERSION}, server_version_num=${RESTORE_PG_SERVER_VERSION_NUM})."

# Actively verify TCP reachability from API_CONTAINER to RESTORE_CONTAINER:5432
if ! docker exec "${API_CONTAINER}" python -c "
import socket, sys
try:
    with socket.create_connection((sys.argv[1], 5432), timeout=3):
        sys.exit(0)
except Exception as e:
    sys.stderr.write(f'Reachability check failed: {e}\n')
    sys.exit(1)
" "${RESTORE_CONTAINER}"; then
  echo "ERROR: Ephemeral container '${RESTORE_CONTAINER}:5432' is not reachable from '${API_CONTAINER}' over network '${SELECTED_NETWORK}'." >&2
  exit 1
fi
echo "Verified TCP reachability from '${API_CONTAINER}' to '${RESTORE_CONTAINER}:5432' over '${SELECTED_NETWORK}'."

# 6. Restore Cluster Globals natively via psql -v ON_ERROR_STOP=1
echo "Restoring globals via filter_globals.py into native psql..."
docker exec -i "${API_CONTAINER}" python docker/scripts/filter_globals.py < "${LOCAL_GLOBALS}" | \
  docker exec -i "${RESTORE_CONTAINER}" psql -U postgres -v ON_ERROR_STOP=1

# 7. Restore Database Dump via pg_restore -C
echo "Restoring database dump via pg_restore -C..."
docker exec -i "${RESTORE_CONTAINER}" pg_restore \
  -U postgres \
  -C \
  -d postgres \
  -v < "${LOCAL_DB}"

# 8. Confirm Restored Database Name Matches Manifest and pg_restore -C Output (Parameterized via psql stdin -v)
DB_MATCH=$(docker exec -i "${RESTORE_CONTAINER}" psql -U postgres -d postgres \
  -v ON_ERROR_STOP=1 \
  -v expected_db="${MANIFEST_DB}" \
  -t -A <<< "SELECT datname FROM pg_database WHERE datname = :'expected_db';" 2>&1) || {
  echo "ERROR: Failed to inspect pg_database in '${RESTORE_CONTAINER}': ${DB_MATCH}" >&2
  exit 1
}

if [[ "${DB_MATCH}" != "${MANIFEST_DB}" ]]; then
  echo "ERROR: Database '${MANIFEST_DB}' specified in manifest was not created by pg_restore -C (found: '${DB_MATCH}')." >&2
  exit 1
fi
RESTORED_DB_CONFIRMED=1
echo "Confirmed pg_restore -C created database '${MANIFEST_DB}' matching manifest."

# 9. Run verify_database.py with Manifest-Derived Standard PostgreSQL DSN + Expected Prefix/Tag
STANDARD_DSN="postgresql://postgres:${RESTORE_PASSWORD}@${RESTORE_CONTAINER}:5432/${MANIFEST_DB}"

echo "Verifying restored database '${MANIFEST_DB}' using standard DSN (${RESTORE_CONTAINER}:5432/${MANIFEST_DB})..."
docker exec -i "${API_CONTAINER}" sh -c "cat > /tmp/verify_manifest_${RESTORE_CONTAINER}.json" < "${LOCAL_MANIFEST}"
docker exec -e PGTZ="${RESTORE_PGTZ:-UTC}" "${API_CONTAINER}" python docker/scripts/verify_database.py \
  --db-url "${STANDARD_DSN}" \
  --manifest "/tmp/verify_manifest_${RESTORE_CONTAINER}.json" \
  --expected-prefix "${PREFIX}" \
  --expected-tag "${BACKUP_TAG}"

echo "===> Restore and verification of '${MANIFEST_DB}' completed with 100% integrity."
