#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.local"
MODE="run-once"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --daemon)
      MODE="daemon"
      shift
      ;;
    --)
      shift
      EXTRA_ARGS+=("$@")
      break
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

python3 -m venv --system-site-packages "$ROOT_DIR/.venv"
source "$ROOT_DIR/.venv/bin/activate"

REQUIRED_MODULES=("requests" "dotenv")
if [[ "$MODE" == "daemon" ]]; then
  REQUIRED_MODULES+=("apscheduler")
fi

if ! python - <<'PY' "${REQUIRED_MODULES[@]}"
import importlib
import sys

modules = sys.argv[1:]
missing = [name for name in modules if importlib.util.find_spec(name) is None]
if missing:
    print(",".join(missing))
    raise SystemExit(1)
PY
then
  python -m pip install --no-build-isolation -e "$ROOT_DIR"
fi

CLI_CMD=(python -m autopaper.cli)
export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

"${CLI_CMD[@]}" validate-config --env-file "$ENV_FILE"

if [[ "$MODE" == "daemon" ]]; then
  exec "${CLI_CMD[@]}" daemon --env-file "$ENV_FILE" --run-on-start "${EXTRA_ARGS[@]}"
fi

exec "${CLI_CMD[@]}" run-once --env-file "$ENV_FILE" "${EXTRA_ARGS[@]}"
