# Business Applications - Implementation Summary

## Overview

Comprehensive implementation of realistic business applications demonstrating near-real-time monitoring of multiprocess/multithread jobs processing file data across **Python, Java, C, and Perl**.

## Business Scenario

Each application simulates a production workload:
- **Parent job** spawns **20+ subjobs** (configurable)
- Each subjob processes **1MB file data**
- Tasks take **~1 minute average** (configurable: 1 second for testing, 60 seconds for production)
- Full monitoring with parent-child relationship tracking
- Performance metrics: CPU, memory, duration, throughput
- Progress reporting with incremental updates

## Files Created

### Application Implementations (4 files)

1. **`examples/business_apps/python_multiprocess_job.py`** (391 lines)
   - Python 3.10+ with `multiprocessing.Pool`
   - Full monitoring SDK integration
   - Parent-child job relationships
   - MD5/SHA256 hashing
   - File generation and processing
   - Comprehensive metrics and summary

2. **`examples/business_apps/java_multithread_job.java`** (344 lines)
   - Java 11+ with `ExecutorService`
   - HTTP-based monitoring (no SDK dependency)
   - Multi-threaded concurrent execution
   - JSON event serialization with Gson
   - Comprehensive error handling

3. **`examples/business_apps/c_multiprocess_job.c`** (414 lines)
   - C with `fork()` for true multiprocessing
   - libcurl for HTTP monitoring
   - OpenSSL for MD5/SHA256 hashing
   - Low-level system programming
   - Process forking and wait

4. **`examples/business_apps/perl_multiprocess_job.pl`** (267 lines)
   - Perl 5 with `Parallel::ForkManager`
   - LWP for HTTP requests
   - Digest::MD5 and Digest::SHA
   - Fork-based multiprocessing

### Testing & Documentation (4 files)

5. **`tests/integration/test_business_apps.py`** (556 lines)
   - Comprehensive integration tests
   - Mock sidecar testing
   - Parent-child relationship verification
   - Progress reporting tests
   - Error handling tests
   - Performance metrics validation
   - Scalability tests (50+ subjobs)

6. **`examples/business_apps/README.md`** (305 lines)
   - Complete usage documentation
   - Build and run instructions
   - Performance characteristics
   - Troubleshooting guide
   - Architecture diagrams

7. **`examples/business_apps/build.sh`** (71 lines)
   - Automated build script for all languages
   - Dependency checking
   - Compilation with proper flags

8. **`examples/business_apps/run_tests.py`** (159 lines)
   - Standalone test runner (no pytest required)
   - Tests all core functionality
   - Import testing
   - File generation/processing
   - Job execution

### Configuration

9. **Updated `pyproject.toml`**
   - Added `pytest-cov>=4.1.0` for coverage
   - New `test` optional dependency group

10. **Updated `apps/monitoring_sdk/monitoring_sdk/__init__.py`**
    - Added `__version__` attribute
    - Improved AWS helpers import handling

## Key Features

### 1. **Multiprocess/Multithread Execution**
- **Python**: `multiprocessing.Pool` for parallel processing (bypasses GIL)
- **Java**: `ExecutorService` with thread pool
- **C**: `fork()` for true process-level parallelism
- **Perl**: `Parallel::ForkManager` for process management

### 2. **File Data Processing**
- Generate 1MB test files with random data
- Compute MD5 and SHA256 hashes
- Simulate processing time (configurable)
- Calculate byte sums for verification
- Full error handling for I/O operations

### 3. **Comprehensive Monitoring**
- **Start events**: Job/subjob initiation with metadata
- **Progress events**: Incremental updates (25%, 50%, 75%, 100%)
- **Finish events**: Completion with full metrics
- **Error events**: Failures with exception details
- **Parent-child tracking**: Subjobs linked to parent job ID

### 4. **Performance Metrics**
- Duration (seconds)
- CPU time (user + system)
- Memory usage (peak MB)
- Throughput (MB/s)
- Parallel efficiency (%)
- Success/failure rates

### 5. **Comprehensive Tests**
All tests validate:
- Module imports
- File generation (correct size)
- File processing (hashing, timing)
- Monitoring SDK integration
- Parent-child relationships
- Progress reporting
- Error handling
- Performance metrics collection
- Scalability (50+ concurrent subjobs)

## Usage

### Prerequisites

```bash
# Install Python dependencies
pip install httpx tenacity psutil pydantic

# Install Java dependencies (if using Java)
wget https://repo1.maven.org/maven2/com/google/code/gson/gson/2.8.9/gson-2.8.9.jar

# Install C dependencies (if using C)
# Ubuntu/Debian:
sudo apt-get install libcurl4-openssl-dev libssl-dev

# macOS:
brew install curl openssl

# Install Perl dependencies (if using Perl)
cpanm Parallel::ForkManager LWP::UserAgent JSON Digest::MD5 Digest::SHA
```

### Build All Applications

```bash
cd examples/business_apps
./build.sh
```

### Run Applications

#### Python
```bash
python examples/business_apps/python_multiprocess_job.py \
    --num-subjobs 20 \
    --site-id site1 \
    --data-dir /tmp/test-data
```

#### Java
```bash
java -cp examples/business_apps:examples/business_apps/gson-2.8.9.jar JavaMultithreadJob \
    --num-subjobs 20 \
    --site-id site1
```

#### C
```bash
./examples/business_apps/c_multiprocess_job \
    --num-subjobs 20 \
    --site-id site1
```

#### Perl
```bash
./examples/business_apps/perl_multiprocess_job.pl \
    --num-subjobs 20 \
    --site-id site1
```

### Run Tests

#### Option 1: Standalone Test Runner (No pytest required)
```bash
cd examples/business_apps
python3 run_tests.py
```

#### Option 2: Full pytest Suite
```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest tests/integration/test_business_apps.py -v

# Run fast tests only
pytest tests/integration/test_business_apps.py -v -m "not slow"

# Run with coverage
pytest tests/integration/test_business_apps.py --cov=monitoring_sdk --cov-report=html
```

## Test Results

### Unit Tests (5 tests)
- ✅ Python job import
- ✅ File generation (1MB ±5%)
- ✅ File processing (MD5/SHA256 hashing)
- ✅ Monitoring SDK integration
- ✅ Python job execution (3 subjobs)

### Integration Tests (12 tests)
- ✅ Python multiprocess job with mock sidecar
- ✅ Parent-child relationship tracking
- ✅ Progress reporting (4 milestones)
- ✅ Error handling and status tracking
- ✅ CPU metrics collection
- ✅ Memory metrics collection
- ✅ Scalability (50+ concurrent subjobs)
- ✅ Import testing
- ✅ File operations
- ✅ End-to-end execution
- ✅ Event validation
- ✅ Metrics validation

## Performance Characteristics

### Expected Metrics (20 subjobs, 1MB each, 1 second processing)

| Language | Total Time | Throughput | Parallel Efficiency | Comments |
|----------|-----------|------------|-------------------|-----------|
| **Python** | 4-6s | 3-5 MB/s | 75-85% | GIL limits CPU-bound parallelism |
| **Java** | 3-5s | 4-6 MB/s | 80-90% | Excellent thread scaling |
| **C** | 2-4s | 5-10 MB/s | 85-95% | True multiprocessing, best performance |
| **Perl** | 4-7s | 3-5 MB/s | 70-80% | Good forking performance |

### Scaling Characteristics

- **Python**: Scales well up to CPU count (8-16 cores typical)
- **Java**: Excellent scaling up to 100+ threads
- **C**: Near-linear scaling with process count
- **Perl**: Good scaling up to 50+ processes

## Architecture

```
┌─────────────────────────────────────────────┐
│       Business Application (any language)   │
│  ┌──────────────────────────────────────┐  │
│  │     Parent Job (coordinator)         │  │
│  └──────┬───────────────────────────────┘  │
│         │                                   │
│    ┌────┴─────┬────────┬────────┬─────┐   │
│    │          │        │        │     │   │
│  ┌─▼──┐    ┌─▼──┐  ┌─▼──┐  ┌─▼──┐  ...   │
│  │Sub1│    │Sub2│  │Sub3│  │SubN│        │
│  │1MB │    │1MB │  │1MB │  │1MB │        │
│  │~1m │    │~1m │  │~1m │  │~1m │        │
│  └──┬─┘    └──┬─┘  └──┬─┘  └──┬─┘        │
│     │         │       │       │           │
│     └─────────┴───┬───┴───────┘           │
│                   │                       │
│         ┌─────────▼────────┐             │
│         │ Monitoring Events│             │
│         └─────────┬────────┘             │
└───────────────────┼──────────────────────┘
                    │ HTTP
      ┌─────────────▼────────────┐
      │    Sidecar Agent         │
      │ (Multi-Integration)      │
      └─────────────┬────────────┘
                    │
       ┌────────────┴─────────────┐
       │                          │
  ┌────▼────┐              ┌──────▼─────┐
  │Local API│              │    AWS     │
  │   +     │              │CloudWatch  │
  │TimescaleDB             │  X-Ray     │
  └─────────┘              └────────────┘
```

## Monitoring Events

### Event Types

1. **Started Event**
   ```json
   {
     "kind": "started",
     "status": "running",
     "at": "2024-01-15T10:30:00Z",
     "metrics": {},
     "metadata": {"num_subjobs": 20, "language": "python"}
   }
   ```

2. **Progress Event**
   ```json
   {
     "kind": "progress",
     "status": "running",
     "at": "2024-01-15T10:30:30Z",
     "metrics": {"progress_pct": 50, "current": 10, "total": 20},
     "metadata": {"message": "50% complete"}
   }
   ```

3. **Finished Event**
   ```json
   {
     "kind": "finished",
     "status": "succeeded",
     "at": "2024-01-15T10:31:00Z",
     "metrics": {
       "duration_s": 60.5,
       "cpu_user_s": 45.2,
       "cpu_system_s": 5.1,
       "mem_max_mb": 512.3
     },
     "metadata": {"subjobs_successful": 20, "subjobs_failed": 0}
   }
   ```

## Production Configuration

### Change Processing Time

Edit the constant in each file:

```python
# Python
PROCESSING_TIME_S = 60.0  # Change from 1.0 to 60.0

# Java
private static final long PROCESSING_TIME_MS = 60000;  // Change from 1000

# C
#define PROCESSING_TIME_S 60  // Change from 1

# Perl
use constant PROCESSING_TIME_S => 60;  // Change from 1
```

### Recommended Settings

- **Development**: 1 second (fast testing)
- **Integration Testing**: 1-5 seconds
- **Production**: 60 seconds (realistic workload)

### Resource Limits

Set `num_subjobs` based on available resources:
- CPU cores: `num_subjobs <= cpu_count * 2`
- Memory: Ensure `num_subjobs * 50MB < available_memory`
- I/O: Consider disk throughput for file operations

## Best Practices

1. **Error Handling**: All apps handle I/O errors, timeout errors, and monitoring failures gracefully
2. **Cleanup**: Temporary files are always removed
3. **Logging**: Comprehensive logging to stdout for debugging
4. **Monitoring**: Full integration with monitoring SDK/API
5. **Testing**: Comprehensive test coverage for all scenarios
6. **Documentation**: Inline comments and external docs

## Next Steps

1. **Add More Languages**: Consider adding Go, Rust, or Node.js examples
2. **Database Integration**: Add direct database writes for comparison
3. **Cloud Integration**: Extend AWS examples to other cloud providers
4. **Performance Tuning**: Optimize for specific hardware configurations
5. **Advanced Monitoring**: Add custom business metrics

## Troubleshooting

See `examples/business_apps/README.md` for detailed troubleshooting guide.

## License

MIT License - See LICENSE file

---

**Total Implementation**: ~2,500 lines of code across 10 files  
**Languages**: Python, Java, C, Perl  
**Test Coverage**: 17 comprehensive tests  
**Documentation**: Complete with examples and troubleshooting

