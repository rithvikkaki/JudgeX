#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# JudgeX Production Backup Script - Revision 19
# Pre-Execution Identifier & SQL Hardening, Type-Tagged Streaming Snapshot
# Signatures, Fail-Closed Coordinator Lifecycle, PID-Reuse-Safe Identity
# Verification, Independent Session Closure Proof & Ambiguous-Upload-Safe
# Conditional OCI Operations
# ==============================================================================

export LC_ALL=C
export MSYS_NO_PATHCONV=1
umask 077

# Use parameter-unset syntax (-) rather than parameter-empty (:-) for overrides so
# an explicitly empty override (e.g. RUN_ID_OVERRIDE="") is caught and rejected.
if [[ "${RUN_ID_OVERRIDE+x}" == "x" ]]; then
  RUN_ID="${RUN_ID_OVERRIDE}"
else
  RUN_ID="$(openssl rand -hex 6)"
fi

TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
if [[ "${BACKUP_DATE_OVERRIDE+x}" == "x" ]]; then
  BACKUP_DATE="${BACKUP_DATE_OVERRIDE}"
else
  BACKUP_DATE=$(date -u +"%Y%m%d")
fi

if [[ "${BACKUP_TAG_OVERRIDE+x}" == "x" ]]; then
  BACKUP_TAG="${BACKUP_TAG_OVERRIDE}"
else
  BACKUP_TAG="judgex_backup_${TIMESTAMP}_${RUN_ID}"
fi

OCI_BUCKET_NAME="${OCI_BUCKET_NAME:-judgex-backups}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-online_judge_db}"
API_CONTAINER="${API_CONTAINER:-online_judge_api}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_INSPECT_USER="${POSTGRES_INSPECT_USER:-${POSTGRES_USER}}"
SNAPSHOT_READY_TIMEOUT="${SNAPSHOT_READY_TIMEOUT:-30}"
RELEASE_EXIT_TIMEOUT_ITERATIONS="${RELEASE_EXIT_TIMEOUT_ITERATIONS:-10}"
ALLOW_FORCE_KILL="${ALLOW_FORCE_KILL:-1}"

# ------------------------------------------------------------------------------
# Phase 0: Strict Pre-Execution Identifier & Parameter Validation
# Executed BEFORE creating temp dirs, starting coordinator, or calling OCI/Docker.
# PostgreSQL NAMEDATALEN is 64 bytes (max identifier/application_name = 63 bytes).
# With prefix 'judgex_backup_' (14 bytes), RUN_ID of 6..32 ASCII [a-z0-9] yields
# an application_name of 20..46 bytes, strictly within the 63-byte limit.
# ------------------------------------------------------------------------------
emit_early_validation_failure() {
  local reason="$1"
  echo "ERROR: Pre-execution identifier validation failed: ${reason}" >&2
  echo "--------------------------------------------------------" >&2
  echo "[BACKUP_CLEANUP_SUMMARY]" >&2
  echo "ORIGINAL_EXIT_CODE=1" >&2
  echo "FINAL_EXIT_CODE=1" >&2
  echo "INPUT_VALIDATION_STATUS=FAILED_INVALID_IDENTIFIER" >&2
  echo "HELPER_TERMINATION_STATUS=NOT_STARTED" >&2
  echo "DB_SESSION_STATUS=NOT_CHECKED_INVALID_INPUT" >&2
  echo "REMOTE_CLEANUP_STATUS=CLEANUP_NOT_NEEDED" >&2
  echo "AMBIGUOUS_UPLOAD_COUNT=0" >&2
  echo "AMBIGUOUS_UPLOAD_OBJECTS=NONE" >&2
  echo "DIAGNOSTIC_ARTIFACTS_RETAINED=0" >&2
  echo "--------------------------------------------------------" >&2
  exit 1
}

if [[ -z "${RUN_ID}" ]] || [[ ! "${RUN_ID}" =~ ^[a-z0-9]{6,32}$ ]]; then
  emit_early_validation_failure "RUN_ID must match ^[a-z0-9]{6,32}$ (got '${RUN_ID}')"
fi

APP_NAME="judgex_backup_${RUN_ID}"
if [[ ${#APP_NAME} -gt 63 ]]; then
  emit_early_validation_failure "Derived application_name '${APP_NAME}' exceeds 63-byte PostgreSQL NAMEDATALEN limit"
fi

if [[ -z "${BACKUP_DATE}" ]] || [[ ! "${BACKUP_DATE}" =~ ^[0-9]{8}$ ]]; then
  emit_early_validation_failure "BACKUP_DATE must match ^[0-9]{8}$ (got '${BACKUP_DATE}')"
fi

if [[ -z "${BACKUP_TAG}" ]] || [[ ! "${BACKUP_TAG}" =~ ^[A-Za-z0-9_]{1,80}$ ]]; then
  emit_early_validation_failure "BACKUP_TAG must match ^[A-Za-z0-9_]{1,80}$ (got '${BACKUP_TAG}')"
fi

if [[ -z "${POSTGRES_USER}" ]] || [[ ! "${POSTGRES_USER}" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]]; then
  emit_early_validation_failure "POSTGRES_USER must match ^[A-Za-z_][A-Za-z0-9_]{0,62}$"
fi

if [[ -z "${POSTGRES_INSPECT_USER}" ]] || [[ ! "${POSTGRES_INSPECT_USER}" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]]; then
  emit_early_validation_failure "POSTGRES_INSPECT_USER must match ^[A-Za-z_][A-Za-z0-9_]{0,62}$"
fi

INPUT_VALIDATION_STATUS="PASSED"
PREFIX="backups/${BACKUP_DATE}"

WORK_DIR=$(mktemp -d -t "${BACKUP_TAG}_XXXXXX")
if command -v cygpath >/dev/null 2>&1; then
  WORK_DIR=$(cygpath -m "${WORK_DIR}")
fi
CONTAINER_TOKEN_DIR="/tmp/tokens_${RUN_ID}"
HOST_TOKEN_DIR="${WORK_DIR}/tokens"
mkdir -p "${HOST_TOKEN_DIR}"

LOCAL_DB_DUMP="${WORK_DIR}/${BACKUP_TAG}_db.dump"
LOCAL_GLOBALS="${WORK_DIR}/${BACKUP_TAG}_globals.sql"
LOCAL_MANIFEST="${WORK_DIR}/${BACKUP_TAG}_manifest.json"

REMOTE_DB_DUMP="${PREFIX}/${BACKUP_TAG}_db.dump"
REMOTE_GLOBALS="${PREFIX}/${BACKUP_TAG}_globals.sql"
REMOTE_MANIFEST="${PREFIX}/${BACKUP_TAG}_manifest.json"

EXACT_OBJECTS=(
  "${REMOTE_DB_DUMP}"
  "${REMOTE_DB_DUMP}.sha256"
  "${REMOTE_GLOBALS}"
  "${REMOTE_GLOBALS}.sha256"
  "${REMOTE_MANIFEST}"
  "${REMOTE_MANIFEST}.sha256"
)

touch "${WORK_DIR}/owned_objects.tsv"
PREFLIGHT_PASSED=0
HELPER_LAUNCH_ATTEMPTED=0
HELPER_PID=""
HELPER_STARTTIME=""
BACKEND_PID=""
BACKUP_SUCCESS=0
AMBIGUOUS_UPLOAD_COUNT=0
AMBIGUOUS_UPLOAD_LIST=""

HELPER_TERMINATION_STATUS="NOT_STARTED"
DB_SESSION_STATUS="NOT_CHECKED"
REMOTE_CLEANUP_STATUS="CLEANUP_NOT_NEEDED"
DIAGNOSTIC_ARTIFACTS_RETAINED=0
ORIGIN_PG_IMAGE="UNCHECKED"
ORIGIN_PG_SERVER_VERSION="UNCHECKED"
ORIGIN_PG_SERVER_VERSION_NUM="UNCHECKED"

# ------------------------------------------------------------------------------
# PID-Reuse-Safe Process Identity Inspection & Signaling
# Verifies /proc/<pid>/stat (non-zombie state + field 22 starttime) and
# /proc/<pid>/cmdline (contains 'snapshot_manifest.py' and RUN_ID).
# Returns:
#   0  = Confirmed still running (exact coordinator process)
#   42 = Confirmed exited (/proc/<pid> absent or zombie 'Z')
#   43 = Confirmed exited (PID reused by an unrelated process)
#   1  = Inspection error (docker exec failed or unexpected exception)
# ------------------------------------------------------------------------------
check_helper_state() {
  local pid="$1"
  local run_id="$2"
  local expected_starttime="${3:-}"
  local rc=0
  docker exec "${API_CONTAINER}" python -c "
import os, sys

pid = int(sys.argv[1])
run_id = sys.argv[2]
expected_st = sys.argv[3]

proc_dir = f'/proc/{pid}'
if not os.path.exists(proc_dir):
    sys.exit(42)

try:
    with open(f'{proc_dir}/stat', 'r', encoding='utf-8') as sf:
        stat_data = sf.read()
    after_comm = stat_data.rsplit(')', 1)[1].split()
    state = after_comm[0]
    starttime = after_comm[19]
    if state == 'Z':
        sys.exit(42)

    with open(f'{proc_dir}/cmdline', 'rb') as cf:
        cmdline = cf.read().decode('utf-8', errors='replace')
except FileNotFoundError:
    sys.exit(42)
except Exception:
    sys.exit(1)

if 'snapshot_manifest.py' not in cmdline or run_id not in cmdline:
    sys.exit(43)

if expected_st and expected_st != 'unknown' and starttime != expected_st:
    sys.exit(43)

sys.exit(0)
" "${pid}" "${run_id}" "${expected_starttime}" >/dev/null 2>&1 || rc=$?
  return ${rc}
}

# Safely sends a signal ONLY if /proc/<pid> identity matches snapshot_manifest.py + RUN_ID + STARTTIME
signal_helper() {
  local pid="$1"
  local run_id="$2"
  local expected_starttime="${3:-}"
  local sig_name="$4"
  local rc=0
  docker exec "${API_CONTAINER}" python -c "
import os, signal, sys

pid = int(sys.argv[1])
run_id = sys.argv[2]
expected_st = sys.argv[3]
sig_name = sys.argv[4]

proc_dir = f'/proc/{pid}'
if not os.path.exists(proc_dir):
    sys.exit(42)

try:
    with open(f'{proc_dir}/stat', 'r', encoding='utf-8') as sf:
        stat_data = sf.read()
    after_comm = stat_data.rsplit(')', 1)[1].split()
    state = after_comm[0]
    starttime = after_comm[19]
    if state == 'Z':
        sys.exit(42)

    with open(f'{proc_dir}/cmdline', 'rb') as cf:
        cmdline = cf.read().decode('utf-8', errors='replace')

    if 'snapshot_manifest.py' not in cmdline or run_id not in cmdline:
        sys.exit(43)
    if expected_st and expected_st != 'unknown' and starttime != expected_st:
        sys.exit(43)

    sig = getattr(signal, sig_name)
    os.kill(pid, sig)
    sys.exit(0)
except (FileNotFoundError, ProcessLookupError):
    sys.exit(42)
except Exception:
    sys.exit(1)
" "${pid}" "${run_id}" "${expected_starttime}" "${sig_name}" >/dev/null 2>&1 || rc=$?
  return ${rc}
}

# Fallback scan of /proc inside container if STARTED token was not yet read before a failure
discover_helper_by_run_id() {
  local run_id="$1"
  docker exec "${API_CONTAINER}" python -c "
import glob, os, sys

run_id = sys.argv[1]
try:
    for stat_path in glob.glob('/proc/[0-9]*/stat'):
        pid_str = stat_path.split('/')[2]
        try:
            with open(stat_path, 'r', encoding='utf-8') as sf:
                after_comm = sf.read().rsplit(')', 1)[1].split()
            if after_comm[0] == 'Z':
                continue
            st = after_comm[19]
            with open(f'/proc/{pid_str}/cmdline', 'rb') as cf:
                cmd = cf.read().decode('utf-8', errors='replace')
            if 'snapshot_manifest.py' in cmd and run_id in cmd:
                print(f'{pid_str}:{st}')
                sys.exit(0)
        except Exception:
            continue
    print('NONE')
except Exception:
    print('ERROR')
" "${run_id}" 2>/dev/null || echo "ERROR"
}

is_helper_verified_dead() {
  case "$1" in
    NOT_STARTED|VERIFIED_CLEAN_EXIT|VERIFIED_PID_REUSED_AFTER_EXIT|TERMINATED_BEFORE_READY|VERIFIED_TERMINATED_ON_ABORT|TERMINATED_BY_FORCE_KILL|FAILED_DEADLINE_TERMINATED_BY_SIGTERM|FAILED_DEADLINE_TERMINATED_BY_SIGKILL)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

is_db_verified_closed() {
  case "$1" in
    VERIFIED_CLOSED|VERIFIED_CLOSED_AFTER_TERMINATE)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

cleanup_trap() {
  local original_exit=$?
  local final_exit=${original_exit}
  set +e

  echo "===> Invoking backup cleanup trap (Exit code: ${original_exit})..." >&2

  # 1. Fail-Closed Helper Termination & Verification
  if [[ ${HELPER_LAUNCH_ATTEMPTED} -eq 1 ]] && ! is_helper_verified_dead "${HELPER_TERMINATION_STATUS}"; then
    echo "Signaling ABORT to snapshot coordinator..." >&2
    docker exec "${API_CONTAINER}" touch "${CONTAINER_TOKEN_DIR}/ABORT" 2>/dev/null || true

    if [[ -z "${HELPER_PID}" ]]; then
      if docker exec "${API_CONTAINER}" test -f "${CONTAINER_TOKEN_DIR}/STARTED" 2>/dev/null; then
        STARTED_CONTENT=$(docker exec "${API_CONTAINER}" cat "${CONTAINER_TOKEN_DIR}/STARTED" 2>/dev/null || true)
        HELPER_PID=$(echo "${STARTED_CONTENT}" | grep '^HELPER_PID=' | cut -d'=' -f2)
        HELPER_STARTTIME=$(echo "${STARTED_CONTENT}" | grep '^STARTTIME=' | cut -d'=' -f2)
      fi
    fi

    if [[ -z "${HELPER_PID}" ]]; then
      DISCOVERED=$(discover_helper_by_run_id "${RUN_ID}")
      if [[ "${DISCOVERED}" == "NONE" ]]; then
        HELPER_TERMINATION_STATUS="TERMINATED_BEFORE_READY"
      elif [[ "${DISCOVERED}" == "ERROR" || -z "${DISCOVERED}" ]]; then
        HELPER_TERMINATION_STATUS="UNVERIFIED_INSPECTION_FAILED"
      else
        HELPER_PID="${DISCOVERED%%:*}"
        HELPER_STARTTIME="${DISCOVERED#*:}"
      fi
    fi

    if [[ -n "${HELPER_PID}" ]] && ! is_helper_verified_dead "${HELPER_TERMINATION_STATUS}"; then
      for _ in 1 2 3 4; do
        check_helper_state "${HELPER_PID}" "${RUN_ID}" "${HELPER_STARTTIME}"
        STATE_RC=$?
        if [[ ${STATE_RC} -eq 42 ]]; then
          HELPER_TERMINATION_STATUS="VERIFIED_TERMINATED_ON_ABORT"
          break
        elif [[ ${STATE_RC} -eq 43 ]]; then
          HELPER_TERMINATION_STATUS="VERIFIED_PID_REUSED_AFTER_EXIT"
          break
        fi
        sleep 0.3
      done

      if ! is_helper_verified_dead "${HELPER_TERMINATION_STATUS}"; then
        signal_helper "${HELPER_PID}" "${RUN_ID}" "${HELPER_STARTTIME}" "SIGTERM"
        sleep 1
        check_helper_state "${HELPER_PID}" "${RUN_ID}" "${HELPER_STARTTIME}"
        STATE_RC=$?
        if [[ ${STATE_RC} -eq 42 ]]; then
          HELPER_TERMINATION_STATUS="VERIFIED_TERMINATED_ON_ABORT"
        elif [[ ${STATE_RC} -eq 43 ]]; then
          HELPER_TERMINATION_STATUS="VERIFIED_PID_REUSED_AFTER_EXIT"
        elif [[ ${ALLOW_FORCE_KILL} -eq 1 ]]; then
          signal_helper "${HELPER_PID}" "${RUN_ID}" "${HELPER_STARTTIME}" "SIGKILL"
          sleep 0.5
          check_helper_state "${HELPER_PID}" "${RUN_ID}" "${HELPER_STARTTIME}"
          KILL_RC=$?
          if [[ ${KILL_RC} -eq 42 ]]; then
            HELPER_TERMINATION_STATUS="TERMINATED_BY_FORCE_KILL"
          elif [[ ${KILL_RC} -eq 43 ]]; then
            HELPER_TERMINATION_STATUS="VERIFIED_PID_REUSED_AFTER_EXIT"
          elif [[ ${KILL_RC} -eq 0 ]]; then
            HELPER_TERMINATION_STATUS="UNVERIFIED_STILL_RUNNING"
          else
            HELPER_TERMINATION_STATUS="UNVERIFIED_INSPECTION_FAILED"
          fi
        else
          check_helper_state "${HELPER_PID}" "${RUN_ID}" "${HELPER_STARTTIME}"
          FINAL_RC=$?
          if [[ ${FINAL_RC} -eq 0 ]]; then
            HELPER_TERMINATION_STATUS="UNVERIFIED_STILL_RUNNING"
          else
            HELPER_TERMINATION_STATUS="UNVERIFIED_INSPECTION_FAILED"
          fi
        fi
      fi
    fi
  fi

  # 2. Independent PostgreSQL Session Closure Verification (Parameterized via psql stdin -v)
  if [[ ${original_exit} -ne 0 && -n "${BACKEND_PID}" && "${BACKEND_PID}" =~ ^[0-9]+$ ]]; then
    docker exec -i "${POSTGRES_CONTAINER}" psql -U "${POSTGRES_USER}" \
      -v ON_ERROR_STOP=1 \
      -v target_bpid="${BACKEND_PID}" \
      <<< "SELECT pg_terminate_backend(:'target_bpid'::integer);" >/dev/null 2>&1 || true
  fi

  local q_err=0
  local session_count=""
  session_count=$(docker exec -i "${POSTGRES_CONTAINER}" psql -U "${POSTGRES_INSPECT_USER}" \
    -v ON_ERROR_STOP=1 \
    -v app_name="${APP_NAME}" \
    -t -A <<< "SELECT count(*) FROM pg_stat_activity WHERE application_name = :'app_name';" 2>&1) || q_err=$?

  if [[ ${q_err} -ne 0 ]]; then
    DB_SESSION_STATUS="UNVERIFIED_QUERY_FAILED"
  elif [[ "${session_count}" =~ ^[0-9]+$ ]]; then
    if [[ "${session_count}" -eq 0 ]]; then
      DB_SESSION_STATUS="VERIFIED_CLOSED"
    else
      echo "WARNING: Active session remaining (${session_count}). Terminating and re-verifying..." >&2
      docker exec -i "${POSTGRES_CONTAINER}" psql -U "${POSTGRES_INSPECT_USER}" \
        -v ON_ERROR_STOP=1 \
        -v app_name="${APP_NAME}" \
        <<< "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = :'app_name';" >/dev/null 2>&1 || true
      sleep 0.5
      local re_err=0
      local re_count=""
      re_count=$(docker exec -i "${POSTGRES_CONTAINER}" psql -U "${POSTGRES_INSPECT_USER}" \
        -v ON_ERROR_STOP=1 \
        -v app_name="${APP_NAME}" \
        -t -A <<< "SELECT count(*) FROM pg_stat_activity WHERE application_name = :'app_name';" 2>&1) || re_err=$?
      if [[ ${re_err} -eq 0 && "${re_count}" =~ ^[0-9]+$ && "${re_count}" -eq 0 ]]; then
        DB_SESSION_STATUS="VERIFIED_CLOSED_AFTER_TERMINATE"
      else
        DB_SESSION_STATUS="UNVERIFIED_ACTIVE_SESSION_REMAINS"
      fi
    fi
  else
    DB_SESSION_STATUS="UNVERIFIED_CORRUPTED_OUTPUT"
  fi

  # 3. Cleanup Remote Objects (Deletes ONLY demonstrably owned objects with --if-match <etag>)
  if [[ ${original_exit} -ne 0 && ${PREFLIGHT_PASSED} -eq 1 ]]; then
    local owned_file="${WORK_DIR}/owned_objects.tsv"
    local owned_count=0
    local del_err=0
    if [[ -f "${owned_file}" && -s "${owned_file}" ]]; then
      echo "Cleaning up demonstrably owned objects from OCI..." >&2
      while IFS=$'\t' read -r obj etag; do
        [[ -z "${obj}" ]] && continue
        owned_count=$((owned_count + 1))
        if [[ -z "${etag}" ]] || [[ "${etag}" =~ [[:cntrl:]] ]]; then
          echo "ERROR: Refusing to delete '${obj}' due to missing or invalid ETag in owned_objects.tsv." >&2
          del_err=$((del_err + 1))
          continue
        fi
        if ! oci os object delete \
          -bn "${OCI_BUCKET_NAME}" \
          --name "${obj}" \
          --if-match "${etag}" \
          --force >/dev/null 2>&1; then
          echo "ERROR: Conditional delete (--if-match ${etag}) failed for owned object '${obj}'." >&2
          del_err=$((del_err + 1))
        fi
      done < "${owned_file}"
    fi

    if [[ ${del_err} -gt 0 ]]; then
      REMOTE_CLEANUP_STATUS="UNVERIFIED_OWNED_DELETION_FAILED"
      final_exit=1
    elif [[ ${AMBIGUOUS_UPLOAD_COUNT} -gt 0 ]]; then
      if [[ ${owned_count} -gt 0 ]]; then
        REMOTE_CLEANUP_STATUS="INCOMPLETE_OWNED_DELETED_AMBIGUOUS_RETAINED"
      else
        REMOTE_CLEANUP_STATUS="INCOMPLETE_ZERO_OWNED_AMBIGUOUS_RETAINED"
      fi
      echo "WARNING: Ambiguous upload object(s) were NOT deleted because ownership/ETag was never confirmed: ${AMBIGUOUS_UPLOAD_LIST}" >&2
      final_exit=1
    elif [[ ${owned_count} -gt 0 ]]; then
      REMOTE_CLEANUP_STATUS="VERIFIED_ALL_OWNED_DELETED"
    else
      REMOTE_CLEANUP_STATUS="CLEANUP_NOT_NEEDED_ZERO_OWNED"
    fi
  fi

  # 4. Fail-Closed Token & Diagnostic Artifact Retention
  if is_helper_verified_dead "${HELPER_TERMINATION_STATUS}" && is_db_verified_closed "${DB_SESSION_STATUS}"; then
    docker exec "${API_CONTAINER}" rm -rf "${CONTAINER_TOKEN_DIR}" "/tmp/manifest_${RUN_ID}.json" 2>/dev/null || true
    rm -rf "${WORK_DIR}" 2>/dev/null || true
    DIAGNOSTIC_ARTIFACTS_RETAINED=0
  else
    DIAGNOSTIC_ARTIFACTS_RETAINED=1
    final_exit=1
    echo "ERROR: Fail-closed cleanup triggered! Coordinator status=${HELPER_TERMINATION_STATUS}, DB session status=${DB_SESSION_STATUS}." >&2
    echo "Retaining diagnostic artifacts: container=${CONTAINER_TOKEN_DIR}, host=${WORK_DIR}" >&2
  fi

  echo "--------------------------------------------------------" >&2
  echo "[BACKUP_CLEANUP_SUMMARY]" >&2
  echo "ORIGINAL_EXIT_CODE=${original_exit}" >&2
  echo "FINAL_EXIT_CODE=${final_exit}" >&2
  echo "INPUT_VALIDATION_STATUS=${INPUT_VALIDATION_STATUS}" >&2
  echo "ORIGIN_PG_IMAGE=${ORIGIN_PG_IMAGE}" >&2
  echo "ORIGIN_PG_SERVER_VERSION=${ORIGIN_PG_SERVER_VERSION}" >&2
  echo "ORIGIN_PG_SERVER_VERSION_NUM=${ORIGIN_PG_SERVER_VERSION_NUM}" >&2
  echo "HELPER_TERMINATION_STATUS=${HELPER_TERMINATION_STATUS}" >&2
  echo "DB_SESSION_STATUS=${DB_SESSION_STATUS}" >&2
  echo "REMOTE_CLEANUP_STATUS=${REMOTE_CLEANUP_STATUS}" >&2
  echo "AMBIGUOUS_UPLOAD_COUNT=${AMBIGUOUS_UPLOAD_COUNT}" >&2
  echo "AMBIGUOUS_UPLOAD_OBJECTS=${AMBIGUOUS_UPLOAD_LIST:-NONE}" >&2
  echo "DIAGNOSTIC_ARTIFACTS_RETAINED=${DIAGNOSTIC_ARTIFACTS_RETAINED}" >&2
  echo "--------------------------------------------------------" >&2

  exit "${final_exit}"
}

trap cleanup_trap EXIT

ORIGIN_PG_IMAGE=$(docker inspect -f '{{.Config.Image}}' "${POSTGRES_CONTAINER}" 2>/dev/null || echo "UNKNOWN")

# Phase 1: Preflight with Structural JSON Validation
echo "===> Phase 1: Validating OCI Object Storage preflight..."
LIST_OUT=$(oci os object list -bn "${OCI_BUCKET_NAME}" --prefix "${PREFIX}/" --output json 2>&1) || {
  echo "ERROR: Failed to list objects in bucket. Details: ${LIST_OUT}" >&2
  exit 1
}

if ! echo "${LIST_OUT}" | jq -e '.data | type == "array"' >/dev/null 2>&1; then
  echo "ERROR: OCI list response was not valid JSON array structure. Aborting." >&2
  exit 1
fi

EXISTING_NAMES=$(echo "${LIST_OUT}" | jq -r '.data[].name // empty')
for intended in "${EXACT_OBJECTS[@]}"; do
  if echo "${EXISTING_NAMES}" | grep -Fxq "${intended}"; then
    echo "ERROR: Collision detected for '${intended}'. Aborting." >&2
    exit 1
  fi
done

PREFLIGHT_PASSED=1
echo "Preflight check passed. Zero collisions detected."

# Phase 2: Start Coordinator & Capture Early PID + Snapshot + Streaming Signatures
echo "===> Phase 2: Starting snapshot coordinator (Run ID: ${RUN_ID}, Token Dir: ${CONTAINER_TOKEN_DIR}, App Name: ${APP_NAME})..."
HELPER_LAUNCH_ATTEMPTED=1
HELPER_TERMINATION_STATUS="RUNNING"

docker exec "${API_CONTAINER}" mkdir -p "${CONTAINER_TOKEN_DIR}"
docker exec "${API_CONTAINER}" sh -c '
  if [ -n "$5" ]; then
    export PGTZ="$5"
  fi
  python docker/scripts/snapshot_manifest.py \
    --db-url "$1" \
    --token-dir "$2" \
    --manifest-out "$3" \
    --run-id "$4" >/dev/null 2>"$2/coordinator_stderr.log" &
  pid=$!
  starttime=$(python -c "
try:
    with open(\"/proc/${pid}/stat\", \"r\") as f:
        print(f.read().rsplit(\")\", 1)[1].split()[19])
except Exception:
    print(\"unknown\")
")
  printf "HELPER_PID=%s\nSTARTTIME=%s\nRUN_ID=%s\n" "${pid}" "${starttime}" "$4" > "$2/STARTED.launcher.tmp"
  mv "$2/STARTED.launcher.tmp" "$2/STARTED"
' _ "${DATABASE_URL}" "${CONTAINER_TOKEN_DIR}" "/tmp/manifest_${RUN_ID}.json" "${RUN_ID}" "${BACKUP_PGTZ:-}"

# Immediately read STARTED token so HELPER_PID and HELPER_STARTTIME are tracked before SNAPSHOT_READY
STARTED_HOST="${HOST_TOKEN_DIR}/STARTED"
docker exec "${API_CONTAINER}" cat "${CONTAINER_TOKEN_DIR}/STARTED" > "${STARTED_HOST}"
HELPER_PID=$(grep '^HELPER_PID=' "${STARTED_HOST}" | cut -d'=' -f2)
HELPER_STARTTIME=$(grep '^STARTTIME=' "${STARTED_HOST}" | cut -d'=' -f2)
echo "Tracked coordinator startup immediately (Helper PID: ${HELPER_PID}, Starttime: ${HELPER_STARTTIME})"

READY_HOST="${HOST_TOKEN_DIR}/SNAPSHOT_READY"
WAIT_COUNT=0
while [[ ! -f "${READY_HOST}" ]] && [[ ${WAIT_COUNT} -lt ${SNAPSHOT_READY_TIMEOUT} ]]; do
  if docker exec "${API_CONTAINER}" test -f "${CONTAINER_TOKEN_DIR}/ERROR" 2>/dev/null; then
    ERR_MSG=$(docker exec "${API_CONTAINER}" cat "${CONTAINER_TOKEN_DIR}/ERROR" 2>/dev/null || echo "Unknown error")
    echo "ERROR: Coordinator reported fatal startup/manifest error: ${ERR_MSG}" >&2
    for _ in 1 2 3; do
      ERR_RC=0
      check_helper_state "${HELPER_PID}" "${RUN_ID}" "${HELPER_STARTTIME}" || ERR_RC=$?
      if [[ ${ERR_RC} -eq 42 || ${ERR_RC} -eq 43 ]]; then
        HELPER_TERMINATION_STATUS="TERMINATED_BEFORE_READY"
        break
      fi
      sleep 0.2
    done
    exit 1
  fi

  if docker exec "${API_CONTAINER}" test -f "${CONTAINER_TOKEN_DIR}/SNAPSHOT_READY" 2>/dev/null; then
    docker exec "${API_CONTAINER}" cat "${CONTAINER_TOKEN_DIR}/SNAPSHOT_READY" > "${READY_HOST}"
    break
  fi

  EARLY_RC=0
  check_helper_state "${HELPER_PID}" "${RUN_ID}" "${HELPER_STARTTIME}" || EARLY_RC=$?
  if [[ ${EARLY_RC} -eq 42 || ${EARLY_RC} -eq 43 ]]; then
    if docker exec "${API_CONTAINER}" test -f "${CONTAINER_TOKEN_DIR}/SNAPSHOT_READY" 2>/dev/null; then
      docker exec "${API_CONTAINER}" cat "${CONTAINER_TOKEN_DIR}/SNAPSHOT_READY" > "${READY_HOST}"
      break
    fi
    STDERR_LOG=$(docker exec "${API_CONTAINER}" cat "${CONTAINER_TOKEN_DIR}/coordinator_stderr.log" 2>/dev/null || true)
    echo "ERROR: Coordinator exited prematurely before publishing SNAPSHOT_READY. Stderr: ${STDERR_LOG}" >&2
    HELPER_TERMINATION_STATUS="TERMINATED_BEFORE_READY"
    exit 1
  fi

  sleep 1
  WAIT_COUNT=$((WAIT_COUNT + 1))
done

if [[ ! -f "${READY_HOST}" ]]; then
  echo "ERROR: Timed out after ${SNAPSHOT_READY_TIMEOUT}s waiting for SNAPSHOT_READY token." >&2
  exit 1
fi

SNAPSHOT_ID=$(grep '^SNAPSHOT_ID=' "${READY_HOST}" | cut -d'=' -f2)
BACKEND_PID=$(grep '^BACKEND_PID=' "${READY_HOST}" | cut -d'=' -f2)
SNAPSHOT_DB=$(grep '^DATABASE=' "${READY_HOST}" | cut -d'=' -f2)
ORIGIN_PG_SERVER_VERSION=$(grep '^SERVER_VERSION=' "${READY_HOST}" | cut -d'=' -f2 || echo "UNKNOWN")
ORIGIN_PG_SERVER_VERSION_NUM=$(grep '^SERVER_VERSION_NUM=' "${READY_HOST}" | cut -d'=' -f2 || echo "UNKNOWN")

if [[ -z "${BACKEND_PID}" ]] || [[ ! "${BACKEND_PID}" =~ ^[0-9]+$ ]]; then
  echo "ERROR: Invalid BACKEND_PID '${BACKEND_PID}' in SNAPSHOT_READY token." >&2
  exit 1
fi

if [[ -z "${SNAPSHOT_DB}" ]] || [[ ! "${SNAPSHOT_DB}" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]] || [[ "${SNAPSHOT_DB}" == "postgres" || "${SNAPSHOT_DB}" == "template0" || "${SNAPSHOT_DB}" == "template1" ]]; then
  echo "ERROR: Invalid or reserved DATABASE '${SNAPSHOT_DB}' in SNAPSHOT_READY token." >&2
  exit 1
fi

TARGET_DUMP_DB="${SNAPSHOT_DB}"
echo "Acquired snapshot ${SNAPSHOT_ID} for database '${TARGET_DUMP_DB}' on PostgreSQL ${ORIGIN_PG_SERVER_VERSION} (${ORIGIN_PG_IMAGE}, server_version_num=${ORIGIN_PG_SERVER_VERSION_NUM}, Helper PID: ${HELPER_PID}, Backend PID: ${BACKEND_PID})"

# Read manifest from container via stream
docker exec "${API_CONTAINER}" cat "/tmp/manifest_${RUN_ID}.json" > "${LOCAL_MANIFEST}"

echo "Dumping database '${TARGET_DUMP_DB}' using snapshot ${SNAPSHOT_ID}..."
docker exec "${POSTGRES_CONTAINER}" pg_dump \
  -U "${POSTGRES_USER}" \
  --snapshot="${SNAPSHOT_ID}" \
  -Fc -d "${TARGET_DUMP_DB}" > "${LOCAL_DB_DUMP}"

# Signal Release and ACTIVELY VERIFY coordinator process exit via identity-safe check
echo "Signaling snapshot release..."
docker exec "${API_CONTAINER}" touch "${CONTAINER_TOKEN_DIR}/RELEASE"

echo "Actively verifying snapshot coordinator clean exit..."
WAIT_HELPER=0
HELPER_EXITED=0
while [[ ${WAIT_HELPER} -lt ${RELEASE_EXIT_TIMEOUT_ITERATIONS} ]]; do
  STATE_RC=0
  check_helper_state "${HELPER_PID}" "${RUN_ID}" "${HELPER_STARTTIME}" || STATE_RC=$?
  if [[ ${STATE_RC} -eq 42 ]]; then
    HELPER_EXITED=1
    HELPER_TERMINATION_STATUS="VERIFIED_CLEAN_EXIT"
    break
  elif [[ ${STATE_RC} -eq 43 ]]; then
    HELPER_EXITED=1
    HELPER_TERMINATION_STATUS="VERIFIED_PID_REUSED_AFTER_EXIT"
    break
  fi
  sleep 0.5
  WAIT_HELPER=$((WAIT_HELPER + 1))
done

if [[ ${HELPER_EXITED} -eq 1 ]]; then
  echo "Coordinator exited cleanly (${HELPER_TERMINATION_STATUS})."
else
  echo "ERROR: Coordinator (PID ${HELPER_PID}) did not exit within deadline after RELEASE. Attempting controlled termination..." >&2
  signal_helper "${HELPER_PID}" "${RUN_ID}" "${HELPER_STARTTIME}" "SIGTERM" || true
  sleep 1
  TERM_RC=0
  check_helper_state "${HELPER_PID}" "${RUN_ID}" "${HELPER_STARTTIME}" || TERM_RC=$?
  if [[ ${TERM_RC} -eq 42 || ${TERM_RC} -eq 43 ]]; then
    HELPER_TERMINATION_STATUS="FAILED_DEADLINE_TERMINATED_BY_SIGTERM"
  elif [[ ${ALLOW_FORCE_KILL} -eq 1 ]]; then
    signal_helper "${HELPER_PID}" "${RUN_ID}" "${HELPER_STARTTIME}" "SIGKILL" || true
    sleep 0.5
    KILL_RC=0
    check_helper_state "${HELPER_PID}" "${RUN_ID}" "${HELPER_STARTTIME}" || KILL_RC=$?
    if [[ ${KILL_RC} -eq 42 || ${KILL_RC} -eq 43 ]]; then
      HELPER_TERMINATION_STATUS="FAILED_DEADLINE_TERMINATED_BY_SIGKILL"
    elif [[ ${KILL_RC} -eq 0 ]]; then
      HELPER_TERMINATION_STATUS="UNVERIFIED_STILL_RUNNING"
    else
      HELPER_TERMINATION_STATUS="UNVERIFIED_INSPECTION_FAILED"
    fi
  else
    FINAL_RC=0
    check_helper_state "${HELPER_PID}" "${RUN_ID}" "${HELPER_STARTTIME}" || FINAL_RC=$?
    if [[ ${FINAL_RC} -eq 0 ]]; then
      HELPER_TERMINATION_STATUS="UNVERIFIED_STILL_RUNNING"
    else
      HELPER_TERMINATION_STATUS="UNVERIFIED_INSPECTION_FAILED"
    fi
  fi
  exit 1
fi

# Dump Cluster Globals
echo "Dumping cluster globals..."
docker exec "${POSTGRES_CONTAINER}" pg_dumpall -U "${POSTGRES_USER}" --globals-only > "${LOCAL_GLOBALS}"

# Embed canonical artifact names in manifest and validate self-consistency
jq --arg tag "${BACKUP_TAG}" \
   --arg prefix "${PREFIX}" \
   '.artifacts = {
     db_dump: ($prefix + "/" + $tag + "_db.dump"),
     db_dump_sha256: ($prefix + "/" + $tag + "_db.dump.sha256"),
     globals: ($prefix + "/" + $tag + "_globals.sql"),
     globals_sha256: ($prefix + "/" + $tag + "_globals.sql.sha256"),
     manifest: ($prefix + "/" + $tag + "_manifest.json"),
     manifest_sha256: ($prefix + "/" + $tag + "_manifest.json.sha256")
   }' "${LOCAL_MANIFEST}" > "${LOCAL_MANIFEST}.tmp" && mv "${LOCAL_MANIFEST}.tmp" "${LOCAL_MANIFEST}"

MANIFEST_SELF_CHECK=$(jq -r \
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

if [[ "${MANIFEST_SELF_CHECK}" != "VALID" ]]; then
  echo "ERROR: Local manifest artifact self-consistency validation failed: ${MANIFEST_SELF_CHECK}" >&2
  exit 1
fi

# Generate Checksums (using basenames)
(cd "${WORK_DIR}" && sha256sum "$(basename "${LOCAL_DB_DUMP}")" > "${LOCAL_DB_DUMP}.sha256")
(cd "${WORK_DIR}" && sha256sum "$(basename "${LOCAL_GLOBALS}")" > "${LOCAL_GLOBALS}.sha256")
(cd "${WORK_DIR}" && sha256sum "$(basename "${LOCAL_MANIFEST}")" > "${LOCAL_MANIFEST}.sha256")

# Phase 3: Server-Enforced Create-Only Uploads with Ambiguous-Outcome Tracking
echo "===> Phase 3: Uploading artifacts with --if-none-match '*'..."

upload_artifact() {
  local local_path="$1"
  local remote_name="$2"

  local upload_resp
  local upload_status=0
  upload_resp=$(oci os object put \
    -bn "${OCI_BUCKET_NAME}" \
    --name "${remote_name}" \
    --file "${local_path}" \
    --if-none-match "*" \
    --output json 2>&1) || upload_status=$?

  if [[ ${upload_status} -ne 0 ]]; then
    if echo "${upload_resp}" | grep -Eq '"code"[[:space:]]*:[[:space:]]*"(PreconditionFailed|IfNoneMatchFailed)"|"status"[[:space:]]*:[[:space:]]*412'; then
      echo "ERROR: Server rejected upload of ${remote_name} due to existing object collision (412 PreconditionFailed). Details: ${upload_resp}" >&2
    else
      AMBIGUOUS_UPLOAD_COUNT=$((AMBIGUOUS_UPLOAD_COUNT + 1))
      AMBIGUOUS_UPLOAD_LIST="${AMBIGUOUS_UPLOAD_LIST:+${AMBIGUOUS_UPLOAD_LIST},}${remote_name}"
      echo "ERROR: Upload of ${remote_name} failed with ambiguous remote outcome (Status ${upload_status}); ownership unconfirmed, cleanup will NOT delete ${remote_name}. Details: ${upload_resp}" >&2
    fi
    return 1
  fi

  local etag
  etag=$(echo "${upload_resp}" | jq -r '.etag // .ETag // .data.etag // .data.ETag // empty' 2>/dev/null || echo "")
  if [[ -z "${etag}" ]] || [[ "${etag}" =~ [[:cntrl:]] ]]; then
    AMBIGUOUS_UPLOAD_COUNT=$((AMBIGUOUS_UPLOAD_COUNT + 1))
    AMBIGUOUS_UPLOAD_LIST="${AMBIGUOUS_UPLOAD_LIST:+${AMBIGUOUS_UPLOAD_LIST},}${remote_name}"
    echo "ERROR: Missing or malformed ETag in upload response for ${remote_name}; ownership unconfirmed, cleanup will NOT delete ${remote_name}." >&2
    return 1
  fi

  printf '%s\t%s\n' "${remote_name}" "${etag}" >> "${WORK_DIR}/owned_objects.tsv"
  echo "Uploaded ${remote_name} [ETag: ${etag}]"
}

upload_artifact "${LOCAL_DB_DUMP}" "${REMOTE_DB_DUMP}"
upload_artifact "${LOCAL_DB_DUMP}.sha256" "${REMOTE_DB_DUMP}.sha256"
upload_artifact "${LOCAL_GLOBALS}" "${REMOTE_GLOBALS}"
upload_artifact "${LOCAL_GLOBALS}.sha256" "${REMOTE_GLOBALS}.sha256"
upload_artifact "${LOCAL_MANIFEST}" "${REMOTE_MANIFEST}"
upload_artifact "${LOCAL_MANIFEST}.sha256" "${REMOTE_MANIFEST}.sha256"

# Phase 4: Remote Round-Trip Verification
echo "===> Phase 4: Verifying remote artifacts..."
for obj in "${EXACT_OBJECTS[@]}"; do
  HEAD_OUT=$(oci os object head -bn "${OCI_BUCKET_NAME}" --name "${obj}" --output json 2>&1) || {
    echo "ERROR: Failed to head remote object ${obj}: ${HEAD_OUT}" >&2
    exit 1
  }
  REMOTE_ETAG=$(echo "${HEAD_OUT}" | jq -r '.etag // .ETag // .data.etag // .data.ETag // empty' 2>/dev/null || echo "")
  EXPECTED_ETAG=$(awk -v o="${obj}" -F$'\t' '$1==o {print $2}' "${WORK_DIR}/owned_objects.tsv")
  if [[ -z "${REMOTE_ETAG}" || -z "${EXPECTED_ETAG}" || "${REMOTE_ETAG}" != "${EXPECTED_ETAG}" ]]; then
    echo "ERROR: ETag mismatch or empty ETag for ${obj} (remote='${REMOTE_ETAG}', expected='${EXPECTED_ETAG}')." >&2
    exit 1
  fi
done

BACKUP_SUCCESS=1
echo "===> Backup completed successfully. All 6 canonical artifacts verified."
