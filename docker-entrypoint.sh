#!/bin/sh
set -eu

state_dir="${PERSISTENT_DATA_DIR:-/app/state}"
mkdir -p "$state_dir"
chown -R appuser:appuser "$state_dir"

if [ "${RAG_BUILD_ON_START:-false}" = "true" ]; then
    if [ "${RETRIEVAL_MODE:-bm25}" != "hybrid" ]; then
        echo "RAG_BUILD_ON_START=true requires RETRIEVAL_MODE=hybrid" >&2
        exit 1
    fi
    su -s /bin/sh appuser -c "python -m scripts.build_rag_index --if-needed"
fi

exec su -s /bin/sh appuser -c "exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"
