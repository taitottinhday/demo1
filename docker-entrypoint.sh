#!/bin/sh
set -eu

state_dir="${PERSISTENT_DATA_DIR:-/app/state}"
mkdir -p "$state_dir"
chown -R appuser:appuser "$state_dir"

exec su -s /bin/sh appuser -c "exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"
