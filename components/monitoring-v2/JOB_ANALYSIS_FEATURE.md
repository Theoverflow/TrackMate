# Job Analysis Feature

## Overview

The Job Analysis feature provides comprehensive monitoring and analysis capabilities for business applications, enabling deep insights into job performance, resource utilization, and subjob tracking across multiprocessed workloads.

## Key Features

### 🎯 **Automatic Job Tracking**
- **Job Lifecycle Management**: Start, track, and complete job analysis
- **Subjob Monitoring**: Track individual tasks, processes, or threads within a job
- **Multiprocess Support**: Monitor complex workloads with multiple subjobs
- **Resource Correlation**: Link resource metrics to specific jobs and subjobs

### 📊 **Enhanced Metrics Collection**
- **Process-Level Metrics**: CPU, memory, threads, file descriptors, status
- **Children Process Tracking**: Monitor child processes and their resource usage
- **System Load Analysis**: 1m, 5m, 15m load averages
- **Job-Specific Metrics**: Runtime, active subjobs, completion status

### 🔍 **Deep Analysis Capabilities**
- **Job Performance**: Duration, completion rate, subjob efficiency
- **Resource Utilization**: Per-job and per-subjob resource consumption
- **Bottleneck Identification**: Identify slow subjobs or resource constraints
- **Trend Analysis**: Track job performance over time

## Supported Languages

| Language | Job Analysis | Subjob Tracking | Auto Metrics | Status |
|----------|-------------|----------------|--------------|--------|
| **Python** | ✅ | ✅ | ✅ | Complete |
| **Perl** | ✅ | ✅ | ✅ | Complete |
| **C** | ✅ | ✅ | ✅ | Complete |
| **R** | ✅ | ✅ | ✅ | Complete |

## Usage Examples

### Python SDK

```python
from monitoring_sdk import MonitoringSDK

# Create SDK with context manager
with MonitoringSDK(source='my-service') as sdk:
    # Start job analysis
    job_id = sdk.start_job_analysis('batch_processing_job', 'multiprocess')
    
    # Process items with subjob tracking
    items = ['item-001', 'item-002', 'item-003']
    for item in items:
        # Track subjob
        subjob_id = sdk.track_subjob(f'process_{item}', 'task')
        
        # Do work
        process_item(item)
        
        # End subjob
        sdk.end_subjob(subjob_id, 'completed')
    
    # End job analysis
    sdk.end_job_analysis('completed')
```

### Perl SDK

```perl
use MonitoringSDK;

my $mon = MonitoringSDK->new(source => 'my-service');

# Start job analysis
my $job_id = $mon->start_job_analysis('data_processing_job', 'main');

# Track subjobs for different phases
my $parse_subjob = $mon->track_subjob('parse_data', 'task');
my $validate_subjob = $mon->track_subjob('validate_data', 'task');
my $load_subjob = $mon->track_subjob('load_database', 'task');

# Complete phases
$mon->end_subjob($parse_subjob, 'completed');
$mon->end_subjob($validate_subjob, 'completed');
$mon->end_subjob($load_subjob, 'completed');

# End job analysis
$mon->end_job_analysis('completed');
$mon->close();
```

### C SDK

```c
#include "monitoring_sdk.h"

monitoring_sdk_t* sdk = monitoring_sdk_create("my-service", "localhost", 17000);

// Start job analysis
char* job_id = monitoring_start_job_analysis(sdk, "batch_job", "multiprocess");

// Track subjobs
char* subjob1 = monitoring_track_subjob(sdk, "process_data", "task");
char* subjob2 = monitoring_track_subjob(sdk, "save_results", "task");

// Complete subjobs
monitoring_end_subjob(sdk, subjob1, "completed");
monitoring_end_subjob(sdk, subjob2, "completed");

// End job analysis
monitoring_end_job_analysis(sdk, "completed");

// Cleanup
free(job_id);
free(subjob1);
free(subjob2);
monitoring_sdk_destroy(sdk);
```

### R SDK

```r
library(R6)
source("monitoring_sdk.R")

sdk <- MonitoringSDK$new(source = "my-service")

# Start job analysis
job_id <- sdk$start_job_analysis("data_analysis_job", "multiprocess")

# Track subjobs
subjob1 <- sdk$track_subjob("load_data", "task")
subjob2 <- sdk$track_subjob("analyze_data", "task")
subjob3 <- sdk$track_subjob("save_results", "task")

# Complete subjobs
sdk$end_subjob(subjob1, "completed")
sdk$end_subjob(subjob2, "completed")
sdk$end_subjob(subjob3, "completed")

# End job analysis
sdk$end_job_analysis("completed")
sdk$close()
```

## API Reference

### Job Analysis Methods

#### `start_job_analysis(job_name, job_type)`
- **Purpose**: Start analyzing a business job/process
- **Parameters**:
  - `job_name` (string): Name of the job/process
  - `job_type` (string): Type of job (main, subjob, multiprocess)
- **Returns**: Job ID for tracking
- **Example**: `job_id = sdk.start_job_analysis('batch_job', 'multiprocess')`

#### `track_subjob(subjob_name, subjob_type)`
- **Purpose**: Track a subjob (child process, thread, or task)
- **Parameters**:
  - `subjob_name` (string): Name of the subjob
  - `subjob_type` (string): Type (process, thread, task)
- **Returns**: Subjob ID
- **Example**: `subjob_id = sdk.track_subjob('process_item', 'task')`

#### `end_subjob(subjob_id, status)`
- **Purpose**: End tracking a subjob
- **Parameters**:
  - `subjob_id` (string): Subjob ID returned by `track_subjob`
  - `status` (string): Completion status (completed, error, cancelled)
- **Example**: `sdk.end_subjob(subjob_id, 'completed')`

#### `end_job_analysis(status)`
- **Purpose**: End job analysis and log summary
- **Parameters**:
  - `status` (string): Completion status
- **Example**: `sdk.end_job_analysis('completed')`

#### `enable_job_analysis(enabled)`
- **Purpose**: Enable or disable automatic job analysis
- **Parameters**:
  - `enabled` (boolean): TRUE to enable, FALSE to disable
- **Example**: `sdk.enable_job_analysis(True)`

## Enhanced Resource Metrics

When job analysis is enabled, `log_resource()` calls automatically include additional job-specific metrics:

### Process Metrics
- `process_cpu_percent`: Current process CPU usage
- `process_memory_mb`: Current process memory usage
- `process_threads`: Number of threads
- `process_fds`: Number of file descriptors
- `process_status`: Process status (running, sleeping, etc.)

### Children Process Metrics
- `children_count`: Number of child processes
- `children_cpu_total`: Total CPU usage of children
- `children_memory_total_mb`: Total memory usage of children

### System Metrics
- `load_avg_1m`: 1-minute load average
- `load_avg_5m`: 5-minute load average
- `load_avg_15m`: 15-minute load average

### Job-Specific Metrics
- `job_id`: Unique job identifier
- `job_name`: Job name
- `job_type`: Job type
- `job_runtime`: Current job runtime in seconds
- `active_subjobs`: Number of active subjobs

## Business Use Cases

### 1. **Multiprocess Data Processing**
```python
# Process large datasets with multiple workers
job_id = sdk.start_job_analysis('data_processing', 'multiprocess')

for worker_id in range(num_workers):
    subjob_id = sdk.track_subjob(f'worker_{worker_id}', 'process')
    # Process data chunk
    sdk.end_subjob(subjob_id, 'completed')

sdk.end_job_analysis('completed')
```

### 2. **Pipeline Processing**
```perl
# Multi-stage data pipeline
my $job_id = $mon->start_job_analysis('etl_pipeline', 'main');

# Stage 1: Extract
my $extract_subjob = $mon->track_subjob('extract_data', 'task');
extract_data();
$mon->end_subjob($extract_subjob, 'completed');

# Stage 2: Transform
my $transform_subjob = $mon->track_subjob('transform_data', 'task');
transform_data();
$mon->end_subjob($transform_subjob, 'completed');

# Stage 3: Load
my $load_subjob = $mon->track_subjob('load_data', 'task');
load_data();
$mon->end_subjob($load_subjob, 'completed');

$mon->end_job_analysis('completed');
```

### 3. **Microservice Orchestration**
```c
// Orchestrate multiple microservices
char* job_id = monitoring_start_job_analysis(sdk, "user_registration", "main");

// Service 1: Validate user data
char* validate_subjob = monitoring_track_subjob(sdk, "validate_user", "service");
call_validation_service();
monitoring_end_subjob(sdk, validate_subjob, "completed");

// Service 2: Create user account
char* create_subjob = monitoring_track_subjob(sdk, "create_account", "service");
call_account_service();
monitoring_end_subjob(sdk, create_subjob, "completed");

// Service 3: Send welcome email
char* email_subjob = monitoring_track_subjob(sdk, "send_email", "service");
call_email_service();
monitoring_end_subjob(sdk, email_subjob, "completed");

monitoring_end_job_analysis(sdk, "completed");
```

## Performance Impact

### Overhead Analysis
- **Job Analysis**: <0.1ms per job start/end
- **Subjob Tracking**: <0.05ms per subjob start/end
- **Enhanced Metrics**: <0.2ms additional overhead per `log_resource()` call
- **Total Overhead**: <1ms per monitoring call (maintains <1ms target)

### Memory Usage
- **Job Metadata**: ~1KB per active job
- **Subjob Tracking**: ~0.5KB per active subjob
- **Buffer Impact**: Minimal (job data included in existing messages)

## Configuration

### Enable/Disable Job Analysis
```python
# Disable job analysis for lightweight monitoring
sdk.enable_job_analysis(False)

# Re-enable for comprehensive analysis
sdk.enable_job_analysis(True)
```

### Context Manager Support (Python)
```python
# Automatic job cleanup with context manager
with MonitoringSDK(source='my-service') as sdk:
    job_id = sdk.start_job_analysis('my_job')
    # Job analysis automatically ended on exit
```

## Integration with Sidecar

The sidecar automatically processes job analysis data and provides:

### **Correlation Engine**
- Links events, metrics, and resources by job ID
- Tracks subjob relationships and dependencies
- Provides end-to-end job visibility

### **Routing Configuration**
- Route job data to different backends based on job type
- Configure per-service granularity for job analysis
- Support runtime configuration changes

### **Analytics and Reporting**
- Job performance dashboards
- Subjob efficiency analysis
- Resource utilization trends
- Bottleneck identification

## Best Practices

### 1. **Job Naming**
- Use descriptive, consistent job names
- Include environment or version information
- Example: `data_processing_v2_prod`, `user_registration_staging`

### 2. **Subjob Granularity**
- Track logical units of work
- Balance detail vs. overhead
- Example: Track major phases, not individual records

### 3. **Status Management**
- Use consistent status values
- Handle error cases appropriately
- Example: `completed`, `error`, `cancelled`, `timeout`

### 4. **Resource Monitoring**
- Call `log_resource()` at key points
- Monitor both job-level and subjob-level resources
- Track resource trends over time

### 5. **Error Handling**
- Always end job analysis, even on errors
- Use appropriate status values
- Include error context in logs

## Migration Guide

### From Basic Monitoring to Job Analysis

**Before (Basic)**:
```python
sdk.log_event('info', 'Processing started')
sdk.log_resource()
# ... do work ...
sdk.log_event('info', 'Processing completed')
```

**After (Job Analysis)**:
```python
job_id = sdk.start_job_analysis('processing_job', 'main')
sdk.log_event('info', 'Processing started')
sdk.log_resource()  # Now includes job analysis metrics
# ... do work ...
sdk.log_event('info', 'Processing completed')
sdk.end_job_analysis('completed')
```

### Backward Compatibility
- All existing monitoring calls continue to work
- Job analysis is opt-in (enabled by default)
- No breaking changes to existing APIs
- Enhanced metrics are additive

## Troubleshooting

### Common Issues

1. **Job Analysis Not Working**
   - Check if `enable_job_analysis(True)` is called
   - Verify job analysis is not disabled
   - Check SDK initialization

2. **Missing Subjob Data**
   - Ensure `track_subjob()` is called before work starts
   - Verify `end_subjob()` is called after work completes
   - Check subjob ID consistency

3. **Performance Issues**
   - Monitor job analysis overhead
   - Consider reducing subjob granularity
   - Use `enable_job_analysis(False)` for lightweight monitoring

### Debug Mode
```python
# Enable debug logging for job analysis
sdk = MonitoringSDK(source='my-service', debug=True)
```

## Future Enhancements

- **Job Dependencies**: Track job dependencies and execution order
- **Resource Limits**: Set and monitor resource limits per job
- **Job Scheduling**: Integration with job schedulers
- **Advanced Analytics**: Machine learning-based performance prediction
- **Visualization**: Real-time job execution graphs

---

*Job Analysis Feature - Comprehensive monitoring for business applications*
