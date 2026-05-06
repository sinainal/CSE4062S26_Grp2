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
APP_URL="http://localhost:${PORT}"

open_browser() {
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "${APP_URL}" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "${APP_URL}" >/dev/null 2>&1 || true
  elif command -v cmd.exe >/dev/null 2>&1; then
    cmd.exe /c start "${APP_URL}" >/dev/null 2>&1 || true
  else
    echo "Open this URL in your browser: ${APP_URL}"
  fi
}

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]] && kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
  fi
}

wait_for_server() {
  for _ in {1..50}; do
    if "${PYTHON_BIN}" -c "import sys, urllib.request; urllib.request.urlopen('http://localhost:' + sys.argv[1], timeout=1)" "${PORT}" >/dev/null 2>&1
    then
      return 0
    fi
    sleep 0.2
  done
  return 1
}

trap cleanup EXIT

echo "Running preprocessing and report generation..."
"${PYTHON_BIN}" "${DATA_SCRIPT}"

echo "Starting the visualization tool at ${APP_URL}"
"${PYTHON_BIN}" -m http.server "${PORT}" --directory "${TOOL_DIR}" >/tmp/cse4062s26_webapp.log 2>&1 &
SERVER_PID=$!

if wait_for_server; then
  open_browser
  echo "Visualization tool is available at ${APP_URL}"
  echo "Press Ctrl+C to stop the server."
  wait "${SERVER_PID}"
else
  echo "Server started, but I could not verify it automatically."
  echo "Open this URL in your browser: ${APP_URL}"
  wait "${SERVER_PID}"
fi
