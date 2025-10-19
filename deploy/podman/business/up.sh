#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

POD=wm-business
if ! podman pod exists "$POD"; then
  podman pod create --name "$POD" -p 8000:8000
fi

SPOOLDIR="${REPO_ROOT}/deploy/podman/business/spool"
mkdir -p "$SPOOLDIR"

if ! podman container exists wm-sidecar; then
  podman run -d --name wm-sidecar --pod "$POD"     -v "$REPO_ROOT":/workspace:Z -w /app     -e LOCAL_API_BASE=http://host.containers.internal:18000     -e SPOOL_DIR=/tmp/sidecar-spool     -v "$SPOOLDIR":/tmp/sidecar-spool:Z     docker.io/library/python:3.11-slim bash -lc "pip install -e /workspace && python -m uvicorn apps.sidecar_agent.main:app --host 0.0.0.0 --port 8000"
fi

podman pod ps
podman ps --pod
