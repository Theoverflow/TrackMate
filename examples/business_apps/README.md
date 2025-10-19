# Realistic Business Applications with Monitoring

This directory contains realistic business applications demonstrating near-real-time monitoring of multiprocess/multithread jobs processing file data.

## Business Scenario

Each application simulates a production workload:
- **Parent job** spawns **20+ subjobs** (configurable)
- Each subjob processes **1MB file data**
- Tasks take **~1 minute average** (configurable for testing: 1 second)
- Full monitoring with parent-child relationship tracking
- Performance metrics: CPU, memory, duration
- Progress reporting

## Applications

### 1. Python Multiprocess Job (`python_multiprocess_job.py`)

**Technology**: Python 3.10+ with multiprocessing

**Features**:
- Uses `multiprocessing.Pool` for parallel execution
- Full monitoring SDK integration
- Parent-child job relationships
- Progress reporting
- MD5/SHA256 hashing
- Comprehensive metrics

**Run**:
```bash
python examples/business_apps/python_multiprocess_job.py \
    --num-subjobs 20 \
    --site-id site1 \
    --data-dir /tmp/test-data
```

### 2. Java Multithreaded Job (`java_multithread_job.java`)

**Technology**: Java 11+ with ExecutorService

**Features**:
- ThreadPoolExecutor for concurrent execution
- HTTP-based monitoring (no SDK dependency)
- Comprehensive error handling
- JSON event serialization

**Compile & Run**:
```bash
# Requires gson library
javac -cp gson-2.8.9.jar java_multithread_job.java

java -cp .:gson-2.8.9.jar JavaMultithreadJob \
    --num-subjobs 20 \
    --site-id site1
```

### 3. C Multiprocess Job (`c_multiprocess_job.c`)

**Technology**: C with fork() for multiprocessing

**Features**:
- Process forking for true parallelism
- libcurl for HTTP monitoring
- OpenSSL for MD5/SHA256
- Low-level system programming

**Compile & Run**:
```bash
gcc -o c_multiprocess_job c_multiprocess_job.c \
    -lcurl -lssl -lcrypto -lpthread

./c_multiprocess_job --num-subjobs 20 --site-id site1
```

### 4. Perl Multiprocess Job (`perl_multiprocess_job.pl`)

**Technology**: Perl 5 with Parallel::ForkManager

**Features**:
- Fork-based multiprocessing
- LWP for HTTP requests
- Digest::MD5 and Digest::SHA
- Comprehensive monitoring

**Run**:
```bash
chmod +x perl_multiprocess_job.pl

# Install dependencies
cpanm Parallel::ForkManager LWP::UserAgent JSON

./perl_multiprocess_job.pl \
    --num-subjobs 20 \
    --site-id site1
```

## Prerequisites

### Common
- Running sidecar agent on `http://localhost:17000`
- Or set `SIDECAR_URL` environment variable

### Python
```bash
pip install -e ../monitoring_sdk
```

### Java
```bash
# Download gson
wget https://repo1.maven.org/maven2/com/google/code/gson/gson/2.8.9/gson-2.8.9.jar
```

### C
```bash
# Ubuntu/Debian
sudo apt-install libcurl4-openssl-dev libssl-dev

# macOS
brew install curl openssl
```

### Perl
```bash
cpanm Parallel::ForkManager LWP::UserAgent JSON Digest::MD5 Digest::SHA
```

## Build All

Use the provided build script:

```bash
./build.sh
```

## Run All Tests

```bash
./run_all_tests.sh
```

## Testing

Comprehensive integration tests are provided in `tests/integration/test_business_apps.py`:

```bash
# Run all tests
pytest tests/integration/test_business_apps.py -v

# Run only fast tests
pytest tests/integration/test_business_apps.py -v -m "not slow"

# Run with coverage
pytest tests/integration/test_business_apps.py --cov=monitoring_sdk --cov-report=html
```

## Performance Characteristics

### Expected Metrics (20 subjobs, 1MB each)

| Language | Avg Time/Subjob | Total Time | Throughput | Parallel Efficiency |
|----------|----------------|------------|------------|-------------------|
| Python   | ~1.0s          | ~4-6s      | 3-5 MB/s   | 75-85%           |
| Java     | ~1.0s          | ~3-5s      | 4-6 MB/s   | 80-90%           |
| C        | ~1.0s          | ~2-4s      | 5-10 MB/s  | 85-95%           |
| Perl     | ~1.0s          | ~4-7s      | 3-5 MB/s   | 70-80%           |

*Note*: Times shown are for testing mode (1 second processing). Production mode uses 60 seconds per subjob.

### Scaling

All applications handle 50+ concurrent subjobs efficiently:
- **Python**: Limited by GIL, best with I/O-bound tasks
- **Java**: Excellent thread scaling (100+ threads)
- **C**: True multiprocessing, near-linear scaling
- **Perl**: Good forking performance (50+ processes)

## Monitoring Dashboard

View job execution in real-time:

```bash
# Local dashboard
open http://localhost:8501

# Check metrics
curl http://localhost:17000/metrics

# Check health
curl http://localhost:17000/v1/health
```

## Architecture

```
┌─────────────────────────────────────────────┐
│          Business Application               │
│  ┌─────────┬─────────┬─────────┬─────────┐ │
│  │ Subjob1 │ Subjob2 │ Subjob3 │ SubjobN │ │
│  │ 1MB file│ 1MB file│ 1MB file│ 1MB file│ │
│  │ ~1 min  │ ~1 min  │ ~1 min  │ ~1 min  │ │
│  └────┬────┴────┬────┴────┬────┴────┬────┘ │
│       │         │         │         │       │
│       └─────────┴────┬────┴─────────┘       │
│                      │                       │
│              ┌───────▼────────┐             │
│              │ Monitoring SDK │             │
│              └───────┬────────┘             │
└──────────────────────┼──────────────────────┘
                       │ HTTP
         ┌─────────────▼────────────┐
         │    Sidecar Agent         │
         │ (Multi-Integration)      │
         └─────────────┬────────────┘
                       │
         ┌─────────────┴────────────┐
         │                          │
    ┌────▼────┐              ┌──────▼─────┐
    │Local API│              │   AWS      │
    │   +     │              │CloudWatch  │
    │TimescaleDB             │  X-Ray     │
    └─────────┘              └────────────┘
```

## Troubleshooting

### Sidecar not responding
```bash
# Check if sidecar is running
curl http://localhost:17000/v1/health

# Start sidecar
cd apps/sidecar_agent
python main.py
```

### File permission errors
```bash
# Ensure data directory is writable
mkdir -p /tmp/wafer-test-data
chmod 777 /tmp/wafer-test-data
```

### Python import errors
```bash
# Install monitoring SDK
pip install -e apps/monitoring_sdk
```

### C compilation errors
```bash
# Install dependencies
sudo apt-get install libcurl4-openssl-dev libssl-dev

# Or macOS
brew install curl openssl
```

### Java missing gson
```bash
# Download gson JAR
wget https://repo1.maven.org/maven2/com/google/code/gson/gson/2.8.9/gson-2.8.9.jar
```

## Production Deployment

### Configuration

Change processing time in code:
```python
# Python: change PROCESSING_TIME_S
PROCESSING_TIME_S = 60.0  # 1 minute

# Java: change PROCESSING_TIME_MS
private static final long PROCESSING_TIME_MS = 60000;

# C: change PROCESSING_TIME_S
#define PROCESSING_TIME_S 60

# Perl: change PROCESSING_TIME_S
use constant PROCESSING_TIME_S => 60;
```

### Docker Deployment

See `Dockerfile.business-app` for containerized deployment.

### Monitoring

All applications send:
- **Start events**: Job/subjob initiation
- **Progress events**: Incremental updates
- **Finish events**: Completion with metrics
- **Error events**: Failures with details

## Best Practices

1. **Resource Limits**: Set max subjobs based on available CPU cores
2. **Error Handling**: All apps handle file I/O errors gracefully
3. **Cleanup**: Temporary files are removed after processing
4. **Logging**: Comprehensive logging to stdout
5. **Monitoring**: Full integration with monitoring SDK

## License

MIT License - See LICENSE file

## Support

For questions or issues, see main project README.md

