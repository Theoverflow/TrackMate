# Podman deployment (rootless-friendly)

Run each environment independently with **pods**; no podman-compose needed.

```bash
# Local data plane (DB + Local API + Archiver)
cd deploy/podman/local-data
./up.sh
./init-schema.sh   # once, to create schema

# Business node (sidecar only)
cd ../business && ./up.sh

# Local HMI
cd ../local-web && ./up.sh

# Central wrapper + web
cd ../central && ./up.sh
```
Teardown in each directory with `./down.sh`.
