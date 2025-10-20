# Wafer Monitor C SDK

Production-ready C library for monitoring distributed applications and sending events to the Wafer Monitor system.

## Features

- ✅ **Simple Context API**: Start, progress, finish pattern
- ✅ **Low-Level Event API**: Full control over event emission
- ✅ **Multiple Backends**: Sidecar, filesystem, S3 (planned)
- ✅ **Thread-Safe**: Can be used from multi-threaded applications
- ✅ **Zero Dependencies**: Only requires libcurl and pthreads
- ✅ **Cross-Platform**: Linux, macOS, Windows (with MinGW)

## Quick Start

### Installation

```bash
# Build and install
mkdir build && cd build
cmake ..
make
sudo make install
```

### Basic Usage

```c
#include <monitoring.h>

int main() {
    /* Configure SDK */
    monitoring_config_t config = {
        .mode = MONITORING_MODE_SIDECAR,
        .app_name = "my-app",
        .app_version = "1.0.0",
        .site_id = "fab1",
        .sidecar_url = "http://localhost:17000"
    };
    
    /* Initialize */
    monitoring_init(&config);
    
    /* Monitor a job */
    monitoring_context_t ctx = monitoring_start("process-wafer", "W-12345");
    monitoring_progress(ctx, 50, "halfway");
    monitoring_add_metric(ctx, "temperature", 75.5);
    monitoring_finish(ctx);
    
    /* Cleanup */
    monitoring_shutdown();
    return 0;
}
```

### Compile Your Application

```bash
# Using pkg-config
gcc -o myapp myapp.c $(pkg-config --cflags --libs monitoring)

# Manual
gcc -o myapp myapp.c -lmonitoring -lcurl -lpthread
```

## API Reference

### Initialization

```c
monitoring_error_t monitoring_init(const monitoring_config_t* config);
monitoring_error_t monitoring_init_from_file(const char* config_file);
monitoring_error_t monitoring_shutdown(void);
bool monitoring_is_initialized(void);
```

### Context API (Recommended)

```c
monitoring_context_t monitoring_start(const char* name, const char* entity_id);
monitoring_error_t monitoring_progress(monitoring_context_t ctx, int progress, const char* message);
monitoring_error_t monitoring_add_metric(monitoring_context_t ctx, const char* key, double value);
monitoring_error_t monitoring_add_metadata(monitoring_context_t ctx, const char* key, const char* value);
monitoring_error_t monitoring_finish(monitoring_context_t ctx);
monitoring_error_t monitoring_error(monitoring_context_t ctx, const char* error_message);
monitoring_error_t monitoring_cancel(monitoring_context_t ctx);
```

### Event API (Low-Level)

```c
monitoring_error_t monitoring_send_event(const monitoring_event_t* event);
monitoring_error_t monitoring_send_batch(const monitoring_event_t* events, int count);
```

### Utilities

```c
const char* monitoring_version(void);
const char* monitoring_error_string(monitoring_error_t error);
char* monitoring_generate_id(char* buffer);
time_t monitoring_timestamp(void);
monitoring_error_t monitoring_health_check(void);
```

## Configuration

### Sidecar Mode

```c
monitoring_config_t config = {
    .mode = MONITORING_MODE_SIDECAR,
    .app_name = "my-app",
    .app_version = "1.0.0",
    .site_id = "fab1",
    .instance_id = "instance-001",
    .sidecar_url = "http://localhost:17000",
    .timeout = 5.0,
    .max_retries = 3
};
```

### Direct Mode (File Backend)

```c
monitoring_backend_config_t backends[] = {
    {
        .type = MONITORING_BACKEND_FILESYSTEM,
        .enabled = true,
        .priority = 1
    }
};

monitoring_config_t config = {
    .mode = MONITORING_MODE_DIRECT,
    .app_name = "my-app",
    .app_version = "1.0.0",
    .site_id = "fab1",
    .backends = backends,
    .num_backends = 1
};
```

## Examples

The SDK includes several example programs:

- `simple_job` - Basic usage
- `multiprocess_job` - Multi-process application
- `error_example` - Error handling
- `direct_mode` - Using direct file backend

Build and run examples:

```bash
cd build
./examples/simple_job
./examples/multiprocess_job
```

## Testing

```bash
cd build
make test

# Or run directly
./tests/test_monitoring
```

## Error Handling

All functions return `monitoring_error_t`:

```c
monitoring_error_t err = monitoring_init(&config);
if (err != MONITORING_OK) {
    fprintf(stderr, "Error: %s\n", monitoring_error_string(err));
    return 1;
}
```

Error codes:
- `MONITORING_OK` - Success
- `MONITORING_ERROR` - Generic error
- `MONITORING_INVALID_PARAM` - Invalid parameter
- `MONITORING_NOT_INITIALIZED` - SDK not initialized
- `MONITORING_ALREADY_INIT` - Already initialized
- `MONITORING_NO_MEMORY` - Out of memory
- `MONITORING_IO_ERROR` - I/O error
- `MONITORING_NETWORK_ERROR` - Network error
- `MONITORING_TIMEOUT` - Timeout
- `MONITORING_NOT_SUPPORTED` - Not supported

## Thread Safety

The SDK is thread-safe and can be used from multiple threads:

```c
void* worker_thread(void* arg) {
    monitoring_context_t ctx = monitoring_start("worker", "worker-1");
    /* ... do work ... */
    monitoring_finish(ctx);
    return NULL;
}
```

## Performance

- Zero-copy JSON serialization
- Connection pooling for HTTP
- Lock-free event queuing (planned)
- Batch event sending

## Requirements

- C11 compiler (GCC 4.9+, Clang 3.3+, MSVC 2015+)
- CMake 3.15+
- libcurl 7.x
- pthreads

## License

MIT License - See LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: https://github.com/your-org/wafer-monitor
- Documentation: https://docs.wafer-monitor.io

