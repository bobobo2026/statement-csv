#!/usr/bin/env bash
# Start gunicorn + Cloudflare quick tunnel. Prints public HTTPS URL.
# Quick tunnels need no Cloudflare account; URL changes if restarted.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p tmp
PORT="${PORT:-8765}"
export PORT HOST=127.0.0.1

CF="${ROOT}/bin/cloudflared"
if [[ ! -x "$CF" ]]; then
  curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o "$CF"
  chmod +x "$CF"
fi

# shellcheck disable=SC1091
[[ -f .env ]] && set -a && source .env && set +a
[[ -d .venv ]] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

pkill -f "gunicorn.*app:app" 2>/dev/null || true
pkill -f "cloudflared tunnel --url" 2>/dev/null || true
sleep 1

nohup gunicorn -b "127.0.0.1:${PORT}" -w 2 --timeout 120 --access-logfile "$ROOT/tmp/gunicorn-access.log" --error-logfile "$ROOT/tmp/gunicorn-error.log" app:app \
  > "$ROOT/tmp/gunicorn-stdout.log" 2>&1 &
echo $! > "$ROOT/tmp/gunicorn.pid"

nohup "$CF" tunnel --url "http://127.0.0.1:${PORT}" \
  > "$ROOT/tmp/cloudflared.log" 2>&1 &
echo $! > "$ROOT/tmp/cloudflared.pid"

echo "Waiting for tunnel URL..."
URL=""
for i in $(seq 1 40); do
  URL=$(grep -oE 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "$ROOT/tmp/cloudflared.log" 2>/dev/null | head -1 || true)
  if [[ -n "$URL" ]]; then
    echo "$URL" | tee "$ROOT/tmp/live-url.txt"
    echo "Health: $URL/health"
    exit 0
  fi
  sleep 1
done
echo "Tunnel URL not found yet; see tmp/cloudflared.log" >&2
tail -50 "$ROOT/tmp/cloudflared.log" >&2 || true
exit 1
