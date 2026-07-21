#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
EXECUTABLE="$SCRIPT_DIR/export_nielsen/export_nielsen"
CONFIG_FILE="$SCRIPT_DIR/jobExportNielsen.properties"
OUTPUT_DIR="${EXPORT_NIELSEN_OUTPUT_DIR:-$SCRIPT_DIR/output}"
LOG_DIR="${EXPORT_NIELSEN_LOG_DIR:-$SCRIPT_DIR/logs}"
LOG_FILE="$LOG_DIR/export_nielsen_$(date +%Y%m).log"
MONTHLY_ONLY=0
APP_ARGS=()

for arg in "$@"; do
  if [[ "$arg" == "--monthly" ]]; then
    MONTHLY_ONLY=1
  else
    APP_ARGS+=("$arg")
  fi
done

if [[ ! -x "$EXECUTABLE" ]]; then
  echo "EROARE: Nu exista executabilul Linux: $EXECUTABLE" >&2
  exit 1
fi
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "EROARE: Nu exista configuratia: $CONFIG_FILE" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR" "$LOG_DIR"

if [[ "$MONTHLY_ONLY" -eq 1 ]]; then
  last_month_value="$(awk -F= '
    /^[[:space:]]*last_month[[:space:]]*=/ {
      value=$0
      sub(/^[^=]*=/, "", value)
    }
    END {
      gsub(/[[:space:]]/, "", value)
      print tolower(value)
    }
  ' "$CONFIG_FILE")"
  if [[ "$last_month_value" != "y" ]]; then
    printf '[%(%Y-%m-%d %H:%M:%S)T] Rulare lunara sarita: last_month nu este y\n' -1 |
      tee -a "$LOG_FILE"
    exit 0
  fi
fi

{
  printf '[%(%Y-%m-%d %H:%M:%S)T] Pornire export Nielsen\n' -1
  set +e
  "$EXECUTABLE" --properties "$CONFIG_FILE" --base-dir "$OUTPUT_DIR" "${APP_ARGS[@]}"
  exit_code=$?
  set -e
  printf '[%(%Y-%m-%d %H:%M:%S)T] Export Nielsen terminat cu exit code %d\n' -1 "$exit_code"
  exit "$exit_code"
} 2>&1 | tee -a "$LOG_FILE"

exit "${PIPESTATUS[0]}"
