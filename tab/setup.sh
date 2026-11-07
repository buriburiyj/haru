#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

REPOSITORY_URL="https://github.com/buriburiyj/haru.git"
WORKER_DIR="$HOME/haru-worker"
ENV_FILE="$WORKER_DIR/worker.env"

missing_packages=""
for package in git python tmux termux-api; do
  if ! dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null | grep -qx installed; then
    missing_packages="$missing_packages $package"
  fi
done

if [ -n "$missing_packages" ]; then
  pkg install -y $missing_packages
fi

if [ -d "$WORKER_DIR/.git" ]; then
  echo "Existing worker repository left unchanged: $WORKER_DIR" >&2
  exit 1
elif [ -e "$WORKER_DIR" ]; then
  echo "Refusing to replace existing non-git directory: $WORKER_DIR" >&2
  exit 1
else
  git clone "$REPOSITORY_URL" "$WORKER_DIR"
fi

# haru_worker.py currently uses only Python's standard library. Keep pip cache
# disabled for future dependency installation on this storage-constrained device.
export PIP_NO_CACHE_DIR=1

if [ ! -e "$ENV_FILE" ]; then
  umask 077
  cat > "$ENV_FILE" <<'EOF'
HARU_SERVER_URL=
WORKER_TOKEN=
WORKER_ID=
HARU_WORK_DIR=
HARU_SOURCE_DIR=
EOF
fi
chmod 600 "$ENV_FILE"

echo "Setup complete. Add values to $ENV_FILE before starting the worker."
