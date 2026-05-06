#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-}"

if [[ -z "${PYTHON_BIN}" ]]; then
  if [[ -x "${SCRIPT_DIR}/.venv/bin/python" ]]; then
    PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

DATA_SCRIPT="${SCRIPT_DIR}/data_harness.py"
TOOL_DIR="${SCRIPT_DIR}/user_tools/visualisation_tool"
PORT="${PORT:-8000}"

echo "Running preprocessing and report generation..."
"${PYTHON_BIN}" "${DATA_SCRIPT}"

echo "Serving the visualization tool at http://localhost:${PORT}"
echo "Press Ctrl+C to stop."
"${PYTHON_BIN}" -m http.server "${PORT}" --directory "${TOOL_DIR}"
