#!/usr/bin/env python3
"""Local web server for the visualization app and live experiment runs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TOOL_DIR = Path(__file__).resolve().parent
MODEL_READY_PATH = ROOT / 'data/model_ready_diabetic_data.csv'

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_harness import run_single_model_lab_experiment  # noqa: E402


def load_model_ready_frame() -> pd.DataFrame:
    if not MODEL_READY_PATH.exists():
        raise FileNotFoundError(
            f'Model-ready data not found at {MODEL_READY_PATH}. '
            'Run start.sh with REFRESH_DATA=1 first.'
        )
    return pd.read_csv(MODEL_READY_PATH)


MODEL_READY_DF = load_model_ready_frame()
LIVE_RUN_HISTORY: dict[str, list[dict]] = {}


def run_signature(run: dict) -> str:
    params = run.get('params', {}) or {}
    parts = [f'{key}={params[key]}' for key in sorted(params)]
    return f"{run.get('model_name', '')}::{'|'.join(parts)}"


def store_live_run(algorithm_name: str, run: dict) -> list[dict]:
    history = LIVE_RUN_HISTORY.get(algorithm_name, [])
    signature = run_signature(run)
    history = [item for item in history if run_signature(item) != signature]
    run['source'] = 'live'
    run['timestamp'] = datetime.now(timezone.utc).isoformat()
    history.insert(0, run)
    LIVE_RUN_HISTORY[algorithm_name] = history[:12]
    return LIVE_RUN_HISTORY[algorithm_name]


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(TOOL_DIR), **kwargs)

    def log_message(self, format, *args):
        # Keep the console readable; requests are obvious enough during local use.
        return

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/health':
            self.send_json({'ok': True, 'message': 'Visualization server is running.'})
            return
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != '/api/run_experiment':
            self.send_error(404, 'Unknown API endpoint')
            return

        try:
            length = int(self.headers.get('Content-Length', '0'))
            raw = self.rfile.read(length) if length > 0 else b'{}'
            payload = json.loads(raw.decode('utf-8') or '{}')
        except Exception as exc:
            self.send_json({'error': f'Invalid JSON body: {exc}'}, status=400)
            return

        algorithm = payload.get('algorithm')
        params = payload.get('params') or {}
        if not algorithm:
            self.send_json({'error': 'Missing "algorithm" in request body.'}, status=400)
            return

        try:
            run = run_single_model_lab_experiment(MODEL_READY_DF, algorithm, params, verbose=False)
        except Exception as exc:
            self.send_json({'error': str(exc)}, status=400)
            return

        recent_runs = store_live_run(algorithm, run)
        self.send_json({
            'algorithm': algorithm,
            'run': run,
            'recent_runs': recent_runs,
            'sample': run.get('sample'),
            'message': f'Live experiment completed for {algorithm}.',
        })


def main():
    parser = argparse.ArgumentParser(description='Serve the visualization dashboard and live experiment API.')
    parser.add_argument('--port', type=int, default=8081)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    print(f'Serving visualization app on http://{args.host}:{args.port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
