#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

POD=wm-local-data
if ! podman pod exists "$POD"; then
  podman pod create --name "$POD" -p 5432:5432 -p 18000:18000
fi

DBDIR="${REPO_ROOT}/deploy/podman/local-data/dbdata"
mkdir -p "$DBDIR"

if ! podman container exists wm-db; then
  podman run -d --name wm-db --pod "$POD"     -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres -e POSTGRES_DB=monitor     -v "$DBDIR":/var/lib/postgresql/data:Z     docker.io/timescale/timescaledb:latest-pg15
fi

if ! podman container exists wm-local-api; then
  podman run -d --name wm-local-api --pod "$POD"     -v "$REPO_ROOT":/workspace:Z -w /app     -e DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/monitor     docker.io/library/python:3.11-slim bash -lc "pip install -e /workspace && python -m uvicorn apps.local_api.main:app --host 0.0.0.0 --port 18000"
fi

if ! podman container exists wm-archiver; then
  podman run -d --name wm-archiver --pod "$POD"     -v "$REPO_ROOT":/workspace:Z -w /app     -e DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/monitor     -e S3_BUCKET=my-bucket -e S3_PREFIX=monitoring/ -e SITE_ID=fab1     docker.io/library/python:3.11-slim bash -lc "pip install -e /workspace && python apps/archiver/main.py"
fi

podman pod ps
podman ps --pod
