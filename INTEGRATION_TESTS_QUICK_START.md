# Integration Tests Quick Start Guide

## 🚀 5-Minute Quick Start

### 1. Run All Tests Locally
```bash
cd components/tests
docker compose -f docker-compose.integration-tests.yml up --build
```

### 2. Run Single Language
```bash
# Python
docker compose -f docker-compose.integration-tests.yml up test-python

# Java
docker compose -f docker-compose.integration-tests.yml up test-java

# C
docker compose -f docker-compose.integration-tests.yml up test-c

# Perl
docker compose -f docker-compose.integration-tests.yml up test-perl
```

### 3. View Results
```bash
# Check container logs
docker compose -f docker-compose.integration-tests.yml logs

# Check exit codes
docker compose -f docker-compose.integration-tests.yml ps
```

## 🔧 Common Commands

### Build Containers
```bash
# Build all
docker compose -f docker-compose.integration-tests.yml build

# Build specific language
docker compose -f docker-compose.integration-tests.yml build test-python
```

### Run Tests
```bash
# Run all and exit
docker compose -f docker-compose.integration-tests.yml up --abort-on-container-exit

# Run in background
docker compose -f docker-compose.integration-tests.yml up -d

# Run with rebuild
docker compose -f docker-compose.integration-tests.yml up --build --force-recreate
```

### Debug Tests
```bash
# Interactive shell
docker compose -f docker-compose.integration-tests.yml run --rm test-python bash

# Run single test
docker compose -f docker-compose.integration-tests.yml run --rm test-python pytest -k "test_name" -vv

# Check environment
docker compose -f docker-compose.integration-tests.yml run --rm test-python env
```

### Cleanup
```bash
# Stop containers
docker compose -f docker-compose.integration-tests.yml down

# Remove volumes
docker compose -f docker-compose.integration-tests.yml down -v

# Full cleanup
docker compose -f docker-compose.integration-tests.yml down -v --rmi all
```

## 📊 Expected Output

### ✅ Success
```
test-python    | ===== 8 passed in 12.34s =====
test-java      | === All Java Integration Tests Complete ===
test-c         | === All C Integration Tests Complete ===
test-perl      | All tests successful.
```

### ❌ Failure
```
test-python    | FAILED test_python_integration.py::test_name - AssertionError
```

## 🐛 Troubleshooting

### Container Build Fails
```bash
# Clear cache
docker system prune -af

# Rebuild without cache
docker compose -f docker-compose.integration-tests.yml build --no-cache
```

### Tests Timeout
```bash
# Increase timeout in docker-compose.yml
timeout: 120  # Increase from default
```

### Permission Errors
```bash
# Make scripts executable
chmod +x components/tests/integration/*/test_*.sh
chmod +x components/tests/integration/*/test_*.pl
```

## 📚 More Information

- Full documentation: `INTEGRATION_TESTS_ARCHITECTURE.md`
- Test details: `components/tests/integration/README.md`
- CI/CD workflow: `.github/workflows/integration-tests.yml`

---

**Need help?** Check the main documentation or open an issue.

