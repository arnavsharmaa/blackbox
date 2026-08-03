#!/usr/bin/env bash
# Run the BlackBox API and web app together; Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x .venv/bin/python ]; then
  echo "No .venv found — run 'make setup' first." >&2
  exit 1
fi

.venv/bin/python -m uvicorn blackbox_api.main:app \
  --app-dir apps/api --host 0.0.0.0 --port 8000 &
API_PID=$!

cleanup() {
  kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

npm run dev
