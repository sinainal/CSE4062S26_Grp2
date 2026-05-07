#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSTEM_PYTHON="${PYTHON_BIN:-python3}"
VENV_DIR="${SCRIPT_DIR}/.venv"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
REQ_STAMP="${VENV_DIR}/.requirements.sha256"
PYTHON_BIN=""
DEFAULT_PORT="${PORT:-8081}"
PORT=""

DATA_SCRIPT="${SCRIPT_DIR}/data_harness.py"
TOOL_DIR="${SCRIPT_DIR}/user_tools/visualisation_tool"
ANALYZER_SCRIPT="${TOOL_DIR}/analyzer.py"
REFRESH_DATA="${REFRESH_DATA:-0}"
APP_URL="http://127.0.0.1:${PORT}"
OPEN_BROWSER="${OPEN_BROWSER:-1}"

port_in_use() {
  local port="$1"
  (exec 3<>"/dev/tcp/127.0.0.1/${port}") >/dev/null 2>&1
}

choose_port() {
  local start_port="$1"
  local candidate
  for candidate in $(seq "${start_port}" $((start_port + 24))); do
    if ! port_in_use "${candidate}"; then
      echo "${candidate}"
      return 0
    fi
  done
  echo "${start_port}"
}

ensure_system_python() {
  if ! command -v "${SYSTEM_PYTHON}" >/dev/null 2>&1; then
    echo "Python 3 is required but was not found on PATH."
    exit 1
  fi
}

bootstrap_venv() {
  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    echo "Creating local virtual environment..."
    "${SYSTEM_PYTHON}" -m venv "${VENV_DIR}"
  fi

  PYTHON_BIN="${VENV_DIR}/bin/python"
  if ! "${PYTHON_BIN}" -m pip --version >/dev/null 2>&1; then
    "${PYTHON_BIN}" -m ensurepip --upgrade >/dev/null 2>&1 || true
  fi

  local req_hash current_hash
  req_hash="$(sha256sum "${REQ_FILE}" | awk '{print $1}')"
  current_hash="$(cat "${REQ_STAMP}" 2>/dev/null || true)"

  if [[ "${current_hash}" != "${req_hash}" ]]; then
    echo "Installing Python dependencies into .venv..."
    "${PYTHON_BIN}" -m pip install --upgrade pip setuptools wheel

    mapfile -t requirements < <(grep -vE '^\s*#|^\s*$' "${REQ_FILE}")
    local core_requirements=()
    local optional_requirements=()
    local requirement
    for requirement in "${requirements[@]}"; do
      if [[ "${requirement}" =~ ^xgboost([<>=!].*)?$ ]]; then
        optional_requirements+=("${requirement}")
      else
        core_requirements+=("${requirement}")
      fi
    done

    if [[ ${#core_requirements[@]} -gt 0 ]]; then
      "${PYTHON_BIN}" -m pip install "${core_requirements[@]}"
    fi

    for requirement in "${optional_requirements[@]}"; do
      if ! "${PYTHON_BIN}" -m pip install "${requirement}"; then
        echo "Optional dependency ${requirement} could not be installed; continuing without it."
      fi
    done

    printf '%s\n' "${req_hash}" > "${REQ_STAMP}"
  else
    echo "Python dependencies already installed in .venv."
  fi
}

open_browser() {
  if [[ "${OPEN_BROWSER}" == "0" ]]; then
    echo "Open this URL in your browser: ${APP_URL}"
    return 0
  fi
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

ensure_system_python
bootstrap_venv

PORT="${DEFAULT_PORT}"
if port_in_use "${PORT}"; then
  echo "Port ${PORT} is busy. Searching for a free port..."
  PORT="$(choose_port "${PORT}")"
fi
APP_URL="http://127.0.0.1:${PORT}"

REPORTS=(
  "${SCRIPT_DIR}/data/cleaned_diabetic_data.csv"
  "${SCRIPT_DIR}/data/model_ready_diabetic_data.csv"
  "${SCRIPT_DIR}/user_tools/visualisation_tool/academic_data.json"
  "${SCRIPT_DIR}/user_tools/visualisation_tool/cleaning_data.json"
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
  "${PYTHON_BIN}" "${ANALYZER_SCRIPT}"
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
