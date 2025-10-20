# Wafer Monitor R SDK

Production-ready R package for monitoring distributed applications and sending events to the Wafer Monitor system.

## Features

- ✅ **Simple API**: Familiar R function interface
- ✅ **R6 Classes**: Modern object-oriented design
- ✅ **Multiple Backends**: Sidecar, filesystem
- ✅ **Automatic Retries**: Built-in exponential backoff
- ✅ **Type Safety**: Input validation
- ✅ **Rich Documentation**: Full Roxygen2 documentation

## Installation

```r
# From source
install.packages("devtools")
devtools::install_local("path/to/monitoring")

# Or from GitHub (when published)
devtools::install_github("your-org/wafer-monitor/components/monitoring/sdk/r")
```

## Quick Start

```r
library(monitoring)

# Initialize SDK
monitoring_init(
  mode = "sidecar",
  app_name = "my-r-app",
  app_version = "1.0.0",
  site_id = "fab1",
  sidecar_url = "http://localhost:17000"
)

# Monitor a job
ctx <- monitoring_start("process-wafer", "W-12345")
monitoring_progress(ctx, 50, "halfway")
monitoring_add_metric(ctx, "temperature", 75.5)
monitoring_finish(ctx)

# Cleanup
monitoring_shutdown()
```

## API Reference

### Initialization

```r
monitoring_init(
  mode = "sidecar",              # or "direct"
  app_name = "my-app",
  app_version = "1.0.0",
  site_id = "fab1",
  sidecar_url = "http://localhost:17000"
)

monitoring_shutdown()
monitoring_is_initialized()
```

### Context API

```r
# Start monitoring
ctx <- monitoring_start(name, entity_id, entity_type = "job")

# Report progress
monitoring_progress(ctx, progress = 50, message = "halfway")

# Add metrics
monitoring_add_metric(ctx, "temperature", 75.5)

# Add metadata
monitoring_add_metadata(ctx, "operator", "john.doe")

# Finish
monitoring_finish(ctx)         # Success
monitoring_error(ctx, "error")  # Error
monitoring_cancel(ctx)          # Cancel
```

## Examples

Run the included examples:

```r
source("examples/simple_job.R")
source("examples/data_processing.R")
```

## Testing

```r
# Install test dependencies
install.packages(c("testthat", "mockery"))

# Run tests
devtools::test()
```

## Configuration

### Sidecar Mode (Recommended)

```r
monitoring_init(
  mode = "sidecar",
  app_name = "my-r-app",
  app_version = "1.0.0",
  site_id = "fab1",
  sidecar_url = "http://localhost:17000",
  timeout = 5.0,
  max_retries = 3
)
```

### Direct Mode (File Backend)

```r
monitoring_init(
  mode = "direct",
  app_name = "my-r-app",
  app_version = "1.0.0",
  site_id = "fab1",
  backend_type = "filesystem",
  backend_config = list(
    output_dir = "./monitoring_events",
    filename_prefix = "events"
  )
)
```

## Error Handling

```r
tryCatch({
  ctx <- monitoring_start("risky-job", "job-001")
  # ... do work ...
  monitoring_finish(ctx)
}, error = function(e) {
  monitoring_error(ctx, e$message)
  stop(e)
})
```

## Integration with Parallel Processing

### Using foreach

```r
library(foreach)
library(doParallel)

cl <- makeCluster(4)
registerDoParallel(cl)

foreach(i = 1:100) %dopar% {
  # Each worker initializes its own SDK
  monitoring_init(...)
  
  ctx <- monitoring_start("parallel-task", sprintf("task-%d", i))
  # ... do work ...
  monitoring_finish(ctx)
  
  monitoring_shutdown()
}

stopCluster(cl)
```

### Using mclapply

```r
library(parallel)

mclapply(1:100, function(i) {
  monitoring_init(...)
  
  ctx <- monitoring_start("parallel-task", sprintf("task-%d", i))
  # ... do work ...
  monitoring_finish(ctx)
  
  monitoring_shutdown()
}, mc.cores = 4)
```

## License

MIT License - See LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: https://github.com/your-org/wafer-monitor
- Documentation: https://docs.wafer-monitor.io

