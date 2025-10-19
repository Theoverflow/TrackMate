#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

set -x
podman cp "${REPO_ROOT}/ops/sql/schema.sql" wm-db:/tmp/schema.sql
podman exec -e PGPASSWORD=postgres wm-db psql -U postgres -d monitor -v ON_ERROR_STOP=1 -f /tmp/schema.sql
echo "Schema initialized."
