#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv}"

log() {
  echo "[setup] $*"
}

log "Root: ${ROOT_DIR}"
log "Venv: ${VENV_DIR}"

cd "${ROOT_DIR}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[setup] python3 not found" >&2
  exit 1
fi

if [ ! -x "${VENV_DIR}/bin/python" ]; then
  log "Creating virtual environment..."
  python3 -m venv "${VENV_DIR}"
fi

PYTHON_BIN="${VENV_DIR}/bin/python"
PIP_BIN="${VENV_DIR}/bin/pip"

log "Installing dependencies..."
"${PYTHON_BIN}" -m pip install --upgrade pip
"${PIP_BIN}" install -r requirements.txt
"${PIP_BIN}" install -e .

log "Verifying uvicorn..."
"${PYTHON_BIN}" - <<'PY'
import travel_agent_service
import uvicorn
print(f"[setup] uvicorn OK: {uvicorn.__version__}")
print(f"[setup] package OK: {travel_agent_service.__name__}")
PY

log "Done"
