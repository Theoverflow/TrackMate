#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

POD=wm-local-web
if ! podman pod exists "$POD"; then
  podman pod create --name "$POD" -p 18501:18501
fi

if ! podman container exists wm-web-local; then
  podman run -d --name wm-web-local --pod "$POD"     -v "$REPO_ROOT":/workspace:Z -w /app     -e LOCAL_API=http://host.containers.internal:18000     docker.io/library/python:3.11-slim bash -lc "pip install -e /workspace && streamlit run apps/web_local/streamlit_app.py --server.port 18501 --server.address 0.0.0.0"
fi

podman pod ps
podman ps --pod
