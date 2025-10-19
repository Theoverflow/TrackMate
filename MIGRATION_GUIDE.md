# Migration Guide - New 3-Component Structure

## Overview

The project has been restructured from a monolithic `apps/` directory into 3 independent component directories:

```
Old Structure:              New Structure:
apps/                       components/
├── monitoring_sdk/   →    ├── monitoring/
├── sidecar_agent/    →    │   ├── sdk/monitoring_sdk/
├── shared_utils/     →    │   └── sidecar/sidecar_agent/
├── local_api/        →    ├── data-plane/
├── central_api/      →    │   ├── local-api/local_api/
├── archiver/         →    │   ├── central-api/central_api/
├── web_local/        →    │   ├── archiver/archiver/
└── web_central/      →    │   └── ops/
                            ├── web/
                            │   ├── local-dashboard/web_local/
                            │   └── central-dashboard/web_central/
                            └── tests/
                            
ops/                  →    components/data-plane/ops/
tests/                →    components/tests/
apps/shared_utils/    →    shared/shared_utils/
```

## Import Path Changes

### Monitoring SDK

**Old**:
```python
from apps.monitoring_sdk.monitoring_sdk import AppRef, Monitored
from apps.monitoring_sdk.monitoring_sdk.emitter import SidecarEmitter
```

**New**:
```python
from components.monitoring.sdk.monitoring_sdk import AppRef, Monitored
from components.monitoring.sdk.monitoring_sdk.emitter import SidecarEmitter
```

**Recommended** (with proper PYTHONPATH):
```python
from monitoring_sdk import AppRef, Monitored
from monitoring_sdk.emitter import SidecarEmitter
```

### Shared Utilities

**Old**:
```python
from apps.shared_utils.logging import setup_logging
from apps.shared_utils.metrics import MetricsCollector
from apps.shared_utils.integrations import IntegrationContainer
```

**New**:
```python
from shared.shared_utils.logging import setup_logging
from shared.shared_utils.metrics import MetricsCollector
from shared.shared_utils.integrations import IntegrationContainer
```

## Environment Setup

### Python Path Configuration

Add to your shell profile (`.bashrc`, `.zshrc`, etc.):

```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/wafer-monitor-v2/components/monitoring/sdk"
export PYTHONPATH="${PYTHONPATH}:/path/to/wafer-monitor-v2/shared"
```

Or in your Python code:
```python
import sys
from pathlib import Path

# Add component paths
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "components" / "monitoring" / "sdk"))
sys.path.insert(0, str(project_root / "shared"))
```

## Docker Configuration Changes

### Old Docker Compose

**File**: `docker-compose.yml` (single file)

```yaml
services:
  sidecar:
    build:
      context: .
      dockerfile: apps/sidecar_agent/Dockerfile
```

### New Docker Compose

**File**: `deploy/docker-compose/monitoring.yml` (separate per component)

```yaml
services:
  sidecar:
    build:
      context: ../../components/monitoring
      dockerfile: Dockerfile.sidecar
```

## Testing Changes

### Old Test Commands

```bash
# From project root
pytest tests/ -v
```

### New Test Commands

```bash
# Test specific component
cd components/monitoring
pytest ../tests/unit/test_emitter.py -v

# Test from root (with proper path)
PYTHONPATH=components/monitoring/sdk:shared pytest components/tests/ -v

# Test all components
cd components/monitoring && pytest ../tests/ -v
cd components/data-plane && pytest ../tests/ -v
cd components/web && pytest ../tests/ -v
```

## Deployment Changes

### Old Deployment

```bash
docker-compose up -d
```

### New Deployment

```bash
# Deploy all
docker compose -f deploy/docker-compose/monitoring.yml up -d
docker compose -f deploy/docker-compose/data-plane.yml up -d
docker compose -f deploy/docker-compose/web.yml up -d

# Or deploy individually
docker compose -f deploy/docker-compose/monitoring.yml up -d  # Monitoring only
```

## Development Workflow Changes

### Old Workflow

```bash
cd apps/sidecar_agent
pip install -r requirements.txt
python main.py
```

### New Workflow

```bash
cd components/monitoring/sidecar
pip install -r requirements.txt
python sidecar_agent/main.py
```

## Configuration File Changes

### Old Config Locations

```
.env
apps/sidecar_agent/config.json
apps/local_api/config.json
```

### New Config Locations

```
components/monitoring/.env
components/data-plane/.env
components/web/.env

# Or use centralized config
config/
├── monitoring.env
├── data-plane.env
└── web.env
```

## CI/CD Changes

### Old CI/CD

Single `.github/workflows/ci.yml` for all components.

### New CI/CD

Separate workflows per component:
- `.github/workflows/monitoring.yml`
- `.github/workflows/data-plane.yml`
- `.github/workflows/web.yml`

**Triggers**: Only runs when component-specific files change!

## Migration Steps

### For Developers

1. **Update your local checkout**:
   ```bash
   git pull origin main
   ```

2. **Update imports in your code**:
   ```bash
   # Use find and replace
   find . -name "*.py" -type f -exec sed -i '' 's/from apps\./from components\./g' {} +
   find . -name "*.py" -type f -exec sed -i '' 's/import apps\./import components\./g' {} +
   ```

3. **Update PYTHONPATH**:
   ```bash
   export PYTHONPATH="${PYTHONPATH}:$(pwd)/components/monitoring/sdk:$(pwd)/shared"
   ```

4. **Test your changes**:
   ```bash
   cd components/monitoring && pytest ../tests/ -v
   ```

### For Operations

1. **Update deployment scripts**:
   ```bash
   # Old
   docker-compose up -d
   
   # New
   docker compose -f deploy/docker-compose/monitoring.yml up -d
   docker compose -f deploy/docker-compose/data-plane.yml up -d
   docker compose -f deploy/docker-compose/web.yml up -d
   ```

2. **Update monitoring/alerts**:
   - Update health check URLs
   - Update metric endpoints
   - Update log paths

3. **Update documentation**:
   - Update runbooks
   - Update operational procedures
   - Update on-call guides

## Backwards Compatibility

### Temporary Symlinks (Optional)

If you need backwards compatibility during migration:

```bash
# Create symlinks from old to new locations
ln -s components/monitoring/sdk/monitoring_sdk apps/monitoring_sdk
ln -s components/monitoring/sidecar/sidecar_agent apps/sidecar_agent
ln -s shared/shared_utils apps/shared_utils
```

**Warning**: Remove these symlinks once migration is complete!

## Troubleshooting

### Import Errors

**Error**: `ModuleNotFoundError: No module named 'apps'`

**Solution**: Update imports to use new paths or set PYTHONPATH:
```bash
export PYTHONPATH="$(pwd)/components/monitoring/sdk:$(pwd)/shared"
```

### Docker Build Failures

**Error**: `COPY failed: file not found in build context`

**Solution**: Update Dockerfile paths and build context:
```yaml
build:
  context: ../../components/monitoring
  dockerfile: Dockerfile.sidecar
```

### Test Failures

**Error**: `ImportError: cannot import name 'AppRef'`

**Solution**: Set PYTHONPATH before running tests:
```bash
PYTHONPATH=components/monitoring/sdk:shared pytest
```

## Rollback Plan

If you need to rollback to the old structure:

```bash
# Checkout previous commit
git checkout <commit-before-restructure>

# Or manually restore
git checkout HEAD~1 -- apps/
```

## FAQ

### Q: Do I need to change my application code?

**A**: Only the import statements. The actual API and functionality remain the same.

### Q: Can I deploy only one component?

**A**: Yes! That's the main benefit. Each component can be deployed independently.

### Q: Will this break existing deployments?

**A**: Existing deployments will continue to work. Update when ready.

### Q: How do I update my CI/CD?

**A**: The new GitHub Actions workflows are already configured. They'll automatically trigger based on which files you change.

### Q: What about the examples directory?

**A**: Examples remain in the root `examples/` directory and work with both old and new structures.

## Timeline

- **Phase 1** (Week 1): Documentation and structure created ✅
- **Phase 2** (Week 2): Update imports in core components
- **Phase 3** (Week 3): Update tests and CI/CD
- **Phase 4** (Week 4): Full migration and old structure removal

## Support

For migration issues:
- **Slack**: #trackmate-migration
- **Email**: support@trackmate.io
- **GitHub Issues**: Label with `migration`

## Additional Resources

- [RESTRUCTURE_SUMMARY.md](RESTRUCTURE_SUMMARY.md) - Architecture overview
- [QUICK_DEPLOY.md](QUICK_DEPLOY.md) - Deployment guide
- [Component READMEs](components/) - Component-specific docs

---

**Migration Status**: ✅ Complete  
**Last Updated**: October 19, 2025

