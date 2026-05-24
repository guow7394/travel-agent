#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-5000}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    -p|--port)
      PORT="${2:-5000}"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

find_python() {
  for candidate in \
    "${VENV_DIR:-}/bin/python" \
    "${ROOT_DIR}/.venv/bin/python" \
    "/workspace/projects/.venv/bin/python" \
    "/tmp/workdir/.venv/bin/python"; do
    if [ -n "${candidate}" ] && [ -x "${candidate}" ]; then
      echo "${candidate}"
      return 0
    fi
  done
  command -v python3 || command -v python
}

PYTHON_BIN="$(find_python)"

echo "[run] Starting service..."
echo "[run] Root: ${ROOT_DIR}"
echo "[run] Python: ${PYTHON_BIN}"
echo "[run] Port: ${PORT}"

cd "${ROOT_DIR}"
exec "${PYTHON_BIN}" -m uvicorn travel_agent_service.app:app --host 0.0.0.0 --port "${PORT}"
