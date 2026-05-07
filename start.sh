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
PORT="${PORT:-8081}"
REFRESH_DATA="${REFRESH_DATA:-0}"
APP_URL="http://127.0.0.1:${PORT}"

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
    if "${PYTHON_BIN}" -c "import sys, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + sys.argv[1], timeout=1)" "${PORT}" >/dev/null 2>&1
    then
      return 0
    fi
    sleep 0.2
  done
  return 1
}

trap cleanup EXIT

REPORTS=(
  "${SCRIPT_DIR}/data/cleaned_diabetic_data.csv"
  "${SCRIPT_DIR}/data/model_ready_diabetic_data.csv"
  "${SCRIPT_DIR}/user_tools/visualisation_tool/model_ready_data.json"
  "${SCRIPT_DIR}/user_tools/visualisation_tool/baseline_model_report.json"
  "${SCRIPT_DIR}/user_tools/visualisation_tool/model_lab_report.json"
  "${SCRIPT_DIR}/user_tools/visualisation_tool/regression_report.json"
  "${SCRIPT_DIR}/user_tools/visualisation_tool/clustering_report.json"
  "${SCRIPT_DIR}/user_tools/visualisation_tool/association_rules_report.json"
  "${SCRIPT_DIR}/user_tools/visualisation_tool/feature_selection_report.json"
  "${SCRIPT_DIR}/user_tools/visualisation_tool/feature_subset_report.json"
  "${SCRIPT_DIR}/user_tools/visualisation_tool/nzv_report.json"
)

needs_refresh=0
if [[ "${REFRESH_DATA}" == "1" ]]; then
  needs_refresh=1
else
  for report in "${REPORTS[@]}"; do
    if [[ ! -f "${report}" ]]; then
      needs_refresh=1
      break
    fi
  done
fi

if [[ "${needs_refresh}" == "1" ]]; then
  echo "Refreshing preprocessing outputs..."
  "${PYTHON_BIN}" "${DATA_SCRIPT}"
else
  echo "Using existing preprocessing outputs. Set REFRESH_DATA=1 to regenerate them."
fi

echo "Starting the visualization tool at ${APP_URL}"
"${PYTHON_BIN}" "${TOOL_DIR}/server.py" --port "${PORT}" --host "127.0.0.1" >/tmp/cse4062s26_webapp.log 2>&1 &
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
