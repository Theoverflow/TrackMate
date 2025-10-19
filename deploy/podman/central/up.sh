#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

POD=wm-central
if ! podman pod exists "$POD"; then
  podman pod create --name "$POD" -p 19000:19000 -p 19501:19501
fi

if ! podman container exists wm-central-api; then
  podman run -d --name wm-central-api --pod "$POD"     -v "$REPO_ROOT":/workspace:Z -w /app     -e SITES=fab1=http://host.containers.internal:18000     docker.io/library/python:3.11-slim bash -lc "pip install -e /workspace && python -m uvicorn apps.central_api.main:app --host 0.0.0.0 --port 19000"
fi

if ! podman container exists wm-web-central; then
  podman run -d --name wm-web-central --pod "$POD"     -v "$REPO_ROOT":/workspace:Z -w /app     -e CENTRAL_API=http://wm-central-api:19000     -e DEFAULT_SITE=fab1     docker.io/library/python:3.11-slim bash -lc "pip install -e /workspace && streamlit run apps/web_central/streamlit_app.py --server.port 19501 --server.address 0.0.0.0"
fi

podman pod ps
podman ps --pod
