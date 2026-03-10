#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if [[ -x "/opt/homebrew/bin/python3" ]]; then
    PYTHON_BIN="/opt/homebrew/bin/python3"
  else
    PYTHON_BIN="python3"
  fi
fi
STAMP_FILE="${VENV_DIR}/.bootstrap_stamp"
REQ_FILE="${PROJECT_ROOT}/requirements.txt"
SETUP_FILE="${PROJECT_ROOT}/setup.py"

needs_install=0
recreate_venv=0
target_python_version="$("${PYTHON_BIN}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

if [[ ! -x "${VENV_DIR}/bin/python" ]] || ! "${VENV_DIR}/bin/python" -V >/dev/null 2>&1; then
  recreate_venv=1
else
  current_python_version="$("${VENV_DIR}/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
  if [[ "${current_python_version}" != "${target_python_version}" ]]; then
    recreate_venv=1
  fi
fi

if [[ "${recreate_venv}" -eq 1 ]]; then
  rm -rf "${VENV_DIR}"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
  needs_install=1
fi

if [[ ! -f "${STAMP_FILE}" || "${REQ_FILE}" -nt "${STAMP_FILE}" || "${SETUP_FILE}" -nt "${STAMP_FILE}" ]]; then
  needs_install=1
fi

if [[ "${needs_install}" -eq 1 ]]; then
  "${VENV_DIR}/bin/python" -m pip install --upgrade pip
  "${VENV_DIR}/bin/pip" install -r "${REQ_FILE}"
  "${VENV_DIR}/bin/pip" install -e "${PROJECT_ROOT}"
  date -u +"%Y-%m-%dT%H:%M:%SZ" > "${STAMP_FILE}"
fi
