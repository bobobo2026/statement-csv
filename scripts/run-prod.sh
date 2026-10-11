#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
[[ -f .env ]] && set -a && source .env && set +a
[[ -d .venv ]] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8765}"
exec gunicorn -b "${HOST}:${PORT}" -w 2 --timeout 120 --access-logfile - app:app
