#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$HOME/computer-use/.env"
if [[ ! -r "$ENV_FILE" ]]; then
  echo "Cannot read $ENV_FILE" >&2
  exit 1
fi

# Load credentials into this process environment only; never print or trace them.
set +x
set -a
. "$ENV_FILE" >/dev/null 2>&1
set +a
if python3 -c 'import socket,sys; s=socket.socket(); s.settimeout(.2); sys.exit(0 if s.connect_ex(("127.0.0.1",8000)) == 0 else 1)' ; then
  echo "Port 8000 is already in use; stop the existing local server first" >&2
  exit 1
fi

export WORKER_TOKEN="${WORKER_TOKEN:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')}"
export HARU_DEV=1
export HARU_DEV_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export HARU_SERVER_URL="http://127.0.0.1:8000"
export HARU_SOURCE_DIR="${HARU_SOURCE_DIR:-$ROOT_DIR}"
export HARU_WORK_DIR="${HARU_WORK_DIR:-$HOME/haru-work}"
export WORKER_ID="mac"

# Vite reads this file at startup. It contains only the short-lived local dev token.
umask 077
printf 'VITE_DEV_TOKEN=%s\n' "$HARU_DEV_TOKEN" > "$ROOT_DIR/web/.env.local"

server_pid=""
worker_pid=""
cleanup() {
  trap - EXIT INT TERM
  [[ -z "$worker_pid" ]] || pkill -TERM -P "$worker_pid" 2>/dev/null || true
  [[ -z "$worker_pid" ]] || kill "$worker_pid" 2>/dev/null || true
  [[ -z "$server_pid" ]] || kill "$server_pid" 2>/dev/null || true
  [[ -z "$worker_pid" ]] || wait "$worker_pid" 2>/dev/null || true
  [[ -z "$server_pid" ]] || wait "$server_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(
  cd "$ROOT_DIR/server"
  exec uv --cache-dir "${UV_CACHE_DIR:-/tmp/haru-uv}" run --with-requirements requirements.txt \
    uvicorn main:app --host 127.0.0.1 --port 8000 --no-access-log --log-level warning
) >/dev/null 2>&1 &
server_pid=$!

ready=0
for _ in {1..80}; do
  if python3 -c 'import os,urllib.request; r=urllib.request.Request("http://127.0.0.1:8000/auth/me",headers={"Authorization":"Bearer "+os.environ["HARU_DEV_TOKEN"]}); urllib.request.urlopen(r,timeout=1)' >/dev/null 2>&1; then
    ready=1
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    break
  fi
  sleep 0.25
done
if [[ "$ready" != 1 ]]; then
  echo "Local Haru server did not start on port 8000" >&2
  exit 1
fi

start_worker() {
  exec uv --cache-dir "${UV_CACHE_DIR:-/tmp/haru-uv}" run --with-requirements "$ROOT_DIR/server/requirements.txt" \
    python "$ROOT_DIR/worker/haru_worker.py" >/dev/null 2>&1 &
  worker_pid=$!
}
start_worker
while kill -0 "$server_pid" 2>/dev/null; do
  if ! kill -0 "$worker_pid" 2>/dev/null; then
    wait "$worker_pid" 2>/dev/null || true
    sleep 1
    start_worker
  fi
  sleep 0.5
done
