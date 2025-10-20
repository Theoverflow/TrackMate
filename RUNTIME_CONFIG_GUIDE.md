# Runtime Configuration & Hot-Reloading Guide

**Version:** 0.3.0+  
**Date:** 2025-10-20  
**Status:** Implemented for All SDKs (C, Python, R, Perl, Java)

---

## 🎯 Overview

Runtime configuration enables **dynamic backend routing** without recompiling or restarting applications. This feature allows you to:

- ✅ Add new backends (S3, Kafka, ELK) without restart
- ✅ Remove backends on-the-fly
- ✅ Change backend priorities
- ✅ Update backend configurations
- ✅ Integrate new monitoring flows seamlessly

### Use Case Example

**Scenario:** You have a C application sending events to S3 and Kafka enterprise cluster. You need to add local environment monitoring without downtime.

**Solution:** 
1. Edit the configuration file
2. Add local sidecar backend
3. Save file
4. SDK auto-detects change and activates new backend
5. **No compilation, no restart, no downtime!**

---

## 📋 Table of Contents

1. [C SDK Runtime Config](#c-sdk-runtime-config)
2. [Python SDK Runtime Config](#python-sdk-runtime-config)
3. [R SDK Runtime Config](#r-sdk-runtime-config)
4. [Perl SDK Runtime Config](#perl-sdk-runtime-config)
5. [Java SDK Runtime Config](#java-sdk-runtime-config)
6. [Configuration File Format](#configuration-file-format)
7. [Examples](#examples)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

---

## 🔧 C SDK Runtime Config

### Basic Usage

```c
#include "monitoring.h"
#include "monitoring_runtime_config.h"

/* Default configuration (compile-time fallback) */
monitoring_config_t default_config = {
    .mode = MONITORING_MODE_SIDECAR,
    .app_name = "my-c-app",
    .app_version = "1.0.0",
    .site_id = "fab1",
    .sidecar_url = "http://localhost:17000"
};

/* Runtime configuration options */
monitoring_runtime_config_options_t runtime_opts = {
    .config_file_path = "/etc/monitoring/config.json",
    .check_interval_seconds = 30,  /* Check every 30 seconds */
    .auto_reload = true,
    .on_config_reload = my_reload_callback,
    .use_fallback = true  /* Use default if file not found */
};

/* Initialize with runtime config */
monitoring_init_with_runtime_config(&default_config, &runtime_opts);

/* Application runs... config changes are auto-detected */

/* Manual reload if needed */
monitoring_reload_config();

/* Query reload status */
time_t last_reload;
bool success;
monitoring_get_reload_status(&last_reload, &success);

/* Cleanup */
monitoring_shutdown();
```

### Reload Callback

```c
void my_reload_callback(bool success, const char* message) {
    if (success) {
        printf("✓ Config reloaded: %s\n", message);
        /* Update application state if needed */
    } else {
        fprintf(stderr, "✗ Config reload failed: %s\n", message);
        /* Handle error, maybe alert operations */
    }
}
```

### Building

```bash
# Update CMakeLists.txt to include runtime_config.c
# Link with cJSON library for JSON parsing
gcc -o myapp myapp.c -lmonitoring -lcjson -lpthread
```

---

## 🐍 Python SDK Runtime Config

### Basic Usage

```python
from monitoring_sdk import init_with_runtime_config

# Default configuration (fallback)
default_config = {
    "mode": "sidecar",
    "app": {
        "name": "my-python-app",
        "version": "1.0.0",
        "site_id": "fab1"
    },
    "sidecar": {
        "url": "http://localhost:17000"
    }
}

# Initialize with runtime config
manager = init_with_runtime_config(
    config_file_path="monitoring_config.yaml",
    default_config=default_config,
    auto_reload=True,
    on_reload=lambda success, msg: print(f"Reload: {msg}")
)

# Application runs... config changes are auto-detected

# Manual reload if needed
manager.reload()

# Query status
status = manager.get_reload_status()
print(f"Last reload: {status['last_reload_time']}")

# Enable/disable auto-reload
manager.set_auto_reload(False)

# Cleanup
manager.shutdown()
```

### Advanced Example

```python
from monitoring_sdk.runtime_config import RuntimeConfigManager

class MyApplication:
    def __init__(self):
        self.config_manager = RuntimeConfigManager(
            config_file_path="monitoring.yaml",
            default_config=get_default_config(),
            auto_reload=True,
            on_reload=self.handle_config_reload,
            use_fallback=True
        )
    
    def handle_config_reload(self, success: bool, message: str):
        if success:
            self.logger.info(f"Config reloaded: {message}")
            # Maybe reconfigure application components
            self.update_metrics_collectors()
        else:
            self.logger.error(f"Config reload failed: {message}")
            # Alert operations team
            self.send_alert("config_reload_failed", message)
    
    def run(self):
        self.config_manager.initialize()
        # Application logic...
        while self.running:
            self.process_events()
    
    def shutdown(self):
        self.config_manager.shutdown()
```

---

## 📝 Configuration File Format

### JSON Format (C SDK)

```json
{
  "mode": "direct",
  "app": {
    "name": "my-app",
    "version": "1.0.0",
    "site_id": "fab1",
    "instance_id": "app-001"
  },
  "backends": [
    {
      "type": "s3",
      "name": "s3-backup",
      "enabled": true,
      "priority": 1,
      "config": {
        "bucket_name": "monitoring-events",
        "region": "us-east-1"
      }
    },
    {
      "type": "kafka",
      "name": "kafka-enterprise",
      "enabled": true,
      "priority": 2,
      "config": {
        "brokers": "kafka1:9092,kafka2:9092,kafka3:9092",
        "topic": "monitoring-events",
        "compression": "snappy"
      }
    },
    {
      "type": "sidecar",
      "name": "local-sidecar",
      "enabled": true,
      "priority": 3,
      "config": {
        "url": "http://localhost:17000"
      }
    }
  ]
}
```

### YAML Format (Python SDK)

```yaml
mode: "direct"

app:
  name: "my-app"
  version: "1.0.0"
  site_id: "fab1"
  instance_id: "app-001"

backends:
  - type: "s3"
    name: "s3-backup"
    enabled: true
    priority: 1
    config:
      bucket_name: "monitoring-events"
      region_name: "us-east-1"
  
  - type: "elk"
    name: "elasticsearch"
    enabled: true
    priority: 2
    config:
      hosts: ["http://localhost:9200"]
      index_name: "monitoring-events-{now/d}"
  
  - type: "sidecar"
    name: "local-sidecar"
    enabled: true
    priority: 3
    config:
      url: "http://localhost:17000"
      timeout: 5.0
```

---

## 💡 Examples

### Example 1: Add S3 Backup Without Restart

**Initial config.json:**
```json
{
  "backends": [
    {
      "type": "sidecar",
      "name": "local",
      "enabled": true,
      "priority": 1
    }
  ]
}
```

**Updated config.json (add S3):**
```json
{
  "backends": [
    {
      "type": "sidecar",
      "name": "local",
      "enabled": true,
      "priority": 1
    },
    {
      "type": "s3",
      "name": "s3-backup",
      "enabled": true,
      "priority": 2,
      "config": {
        "bucket_name": "monitoring-backup",
        "region": "us-east-1"
      }
    }
  ]
}
```

**Result:** S3 backend activated automatically, events now sent to both sidecar and S3.

### Example 2: Disable Backend Temporarily

**Disable Kafka without removing config:**
```yaml
backends:
  - type: "kafka"
    name: "kafka-enterprise"
    enabled: false  # ← Set to false
    priority: 2
```

**Result:** Kafka backend stops receiving events. Re-enable by setting `enabled: true`.

### Example 3: Change Backend Priority

**Reorder backends to prioritize S3:**
```yaml
backends:
  - type: "s3"
    name: "s3-backup"
    enabled: true
    priority: 1  # ← Highest priority
  
  - type: "sidecar"
    name: "local-sidecar"
    enabled: true
    priority: 2  # ← Lower priority
```

**Result:** Events sent to S3 first, then sidecar.

### Example 4: Integrate New Local Environment

**Scenario:** Running in production (S3 + Kafka), need to add local development monitoring.

**Add to config:**
```yaml
backends:
  # Existing production backends
  - type: "s3"
    name: "s3-production"
    enabled: true
    priority: 1
  
  - type: "kafka"
    name: "kafka-production"
    enabled: true
    priority: 2
  
  # NEW: Local development monitoring
  - type: "sidecar"
    name: "dev-local"
    enabled: true
    priority: 3
    config:
      url: "http://localhost:17000"
```

**Result:** Events now flow to S3, Kafka, AND local development environment simultaneously.

---

## ✅ Best Practices

### 1. **Always Use Fallback Configuration**

```c
runtime_opts.use_fallback = true;
```

This ensures your application continues running even if the config file is temporarily unavailable.

### 2. **Set Appropriate Check Intervals**

```c
/* Production: check every 30-60 seconds */
runtime_opts.check_interval_seconds = 30;

/* Development: check every 5-10 seconds */
runtime_opts.check_interval_seconds = 5;
```

Balance between responsiveness and file I/O overhead.

### 3. **Implement Reload Callbacks**

Always monitor config reload status:

```python
def on_reload(success: bool, message: str):
    if success:
        logger.info(f"Config reloaded successfully: {message}")
        metrics.increment("config_reload_success")
    else:
        logger.error(f"Config reload failed: {message}")
        metrics.increment("config_reload_failure")
        alert_ops_team(f"Config reload failed: {message}")
```

### 4. **Version Your Config Files**

```yaml
# monitoring_config_v2.yaml
version: "2.0"  # Track config version
last_updated: "2025-10-20T10:30:00Z"
updated_by: "ops-team"

app:
  name: "my-app"
  # ...
```

### 5. **Use Atomic File Updates**

When updating config files:

```bash
# Write to temporary file
cat > config.json.tmp << EOF
{config content}
EOF

# Atomic move
mv config.json.tmp config.json
```

This prevents the SDK from reading partial/corrupt config.

### 6. **Test Config Changes in Staging First**

```bash
# Staging
cp config.production.json config.staging.json
# Edit config.staging.json
# Test with staging application
# If successful, apply to production
```

### 7. **Monitor Backend Health**

```python
# Regularly check backend status
status = manager.get_reload_status()
if not status['last_reload_success']:
    alert_team("Config reload failing")
```

---

## 🔷 R SDK Runtime Config

### Basic Usage

```r
library(monitoring)

# Default configuration (fallback)
default_config <- list(
  mode = "sidecar",
  app_name = "my-r-app",
  app_version = "1.0.0",
  site_id = "fab1",
  sidecar_url = "http://localhost:17000"
)

# Reload callback
on_reload <- function(success, message) {
  if (success) {
    message("✓ Config reloaded: ", message)
  } else {
    warning("✗ Config reload failed: ", message)
  }
}

# Initialize with runtime config
monitoring_init_with_runtime_config(
  config_file = "monitoring_config.yaml",
  default_config = default_config,
  auto_reload = TRUE,
  check_interval = 30,  # seconds
  on_reload = on_reload,
  use_fallback = TRUE
)

# Application runs... config changes are auto-detected

# Manual reload if needed
monitoring_reload_runtime_config()

# Query status
status <- monitoring_get_runtime_status()
print(status)

# Cleanup
monitoring_shutdown_runtime_config()
```

### Dependencies

```r
# Install required packages
install.packages("yaml")      # For YAML config files
install.packages("later")     # For auto-reload (optional but recommended)
```

### File Watching

R SDK uses the `later` package to schedule periodic checks for file changes. If `later` is not installed, auto-reload will be disabled and you'll need to use manual reload.

---

## 🔶 Perl SDK Runtime Config

### Basic Usage

```perl
use Monitoring::RuntimeConfig;

# Default configuration (fallback)
my $default_config = {
    mode => 'sidecar',
    app_name => 'my-perl-app',
    app_version => '1.0.0',
    site_id => 'fab1',
    sidecar_url => 'http://localhost:17000'
};

# Reload callback
my $on_reload = sub {
    my ($success, $message) = @_;
    if ($success) {
        print "✓ Config reloaded: $message\n";
    } else {
        warn "✗ Config reload failed: $message\n";
    }
};

# Initialize with runtime config
Monitoring::RuntimeConfig->init_with_runtime_config(
    config_file => 'monitoring_config.yaml',
    default_config => $default_config,
    auto_reload => 1,
    check_interval => 30,  # seconds
    on_reload => $on_reload,
    use_fallback => 1
);

# Application runs... config changes are auto-detected

# Manual reload if needed
Monitoring::RuntimeConfig->reload_runtime_config();

# Query status
my $status = Monitoring::RuntimeConfig->get_runtime_status();
print "Last reload: ", $status->{last_reload_time}, "\n";

# Cleanup
Monitoring::RuntimeConfig->shutdown_runtime_config();
```

### Dependencies

```bash
# Install required CPAN modules
cpanm YAML::XS
cpanm JSON::PP
```

### File Watching

Perl SDK uses a forked background process to monitor file changes. The watcher runs independently and notifies the main process when the config file is modified.

---

## ☕ Java SDK Runtime Config

### Basic Usage

```java
import io.wafermonitor.monitoring.*;

// Default configuration (fallback)
MonitoringConfig defaultConfig = MonitoringConfig.builder()
    .mode(Mode.SIDECAR)
    .appName("my-java-app")
    .appVersion("1.0.0")
    .siteId("fab1")
    .sidecarUrl("http://localhost:17000")
    .build();

// Reload callback
BiConsumer<Boolean, String> onReload = (success, message) -> {
    if (success) {
        System.out.println("✓ Config reloaded: " + message);
    } else {
        System.err.println("✗ Config reload failed: " + message);
    }
};

// Initialize with runtime config
RuntimeConfigManager manager = RuntimeConfigManager.getInstance();
manager.initWithRuntimeConfig(
    "monitoring_config.yaml",  // config file
    defaultConfig,             // fallback
    true,                      // auto-reload
    30,                        // check interval (seconds)
    onReload,                  // callback
    true                       // use fallback
);

// Application runs... config changes are auto-detected

// Manual reload if needed
manager.reloadConfig();

// Query status
RuntimeConfigManager.RuntimeStatus status = manager.getStatus();
System.out.println("Auto-reload: " + status.isAutoReload());

// Cleanup
manager.shutdown();
```

### Dependencies

```xml
<!-- Add to pom.xml -->
<dependency>
    <groupId>com.fasterxml.jackson.core</groupId>
    <artifactId>jackson-databind</artifactId>
    <version>2.15.0</version>
</dependency>
<dependency>
    <groupId>com.fasterxml.jackson.dataformat</groupId>
    <artifactId>jackson-dataformat-yaml</artifactId>
    <version>2.15.0</version>
</dependency>
```

### File Watching

Java SDK uses the NIO.2 `WatchService` API to efficiently monitor file changes. This provides native OS-level file system notifications without polling.

---

## 🔍 Troubleshooting

### Problem: Config Not Reloading

**Symptoms:** File changes not detected

**Solutions:**
1. Check file permissions
   ```bash
   ls -l /etc/monitoring/config.json
   chmod 644 /etc/monitoring/config.json
   ```

2. Verify auto-reload enabled
   ```c
   runtime_opts.auto_reload = true;
   ```

3. Check file watcher is running
   ```python
   status = manager.get_reload_status()
   print(status)  # auto_reload should be True
   ```

4. Verify check interval isn't too long
   ```c
   runtime_opts.check_interval_seconds = 10;  // Reduce for testing
   ```

### Problem: Config Parse Errors

**Symptoms:** "Failed to load config file" errors

**Solutions:**
1. Validate JSON/YAML syntax
   ```bash
   # JSON
   cat config.json | python -m json.tool
   
   # YAML
   python -c "import yaml; yaml.safe_load(open('config.yaml'))"
   ```

2. Check for required fields
   ```yaml
   app:
     name: "required"
     version: "required"
     site_id: "required"
   ```

3. Enable debug logging
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

### Problem: Backend Not Activating

**Symptoms:** New backend in config but not receiving events

**Solutions:**
1. Check `enabled` field
   ```json
   {"enabled": true}  // Must be true
   ```

2. Verify backend type is supported
   ```c
   // Check if backend implementation exists
   ```

3. Check backend-specific config
   ```yaml
   config:
     bucket_name: "required-for-s3"
     url: "required-for-sidecar"
   ```

4. Review reload callback messages
   ```python
   # Should show "Configuration reloaded successfully"
   ```

### Problem: Events Being Dropped

**Symptoms:** Some events not reaching backends

**Solutions:**
1. Check backend priority and ordering
2. Verify all backends are healthy
3. Review backend timeout settings
4. Check for network/connectivity issues
5. Monitor backend logs for errors

---

## 📚 Additional Resources

### SDK Documentation
- [C SDK API Reference](components/monitoring/sdk/c/README.md)
- [Python SDK API Reference](components/monitoring/sdk/python/README.md)
- [R SDK Documentation](components/monitoring/sdk/r/README.md)
- [Perl SDK Documentation](components/monitoring/sdk/perl/README.md)
- [Java SDK JavaDoc](components/monitoring/sdk/java/README.md)

### Examples
- [C Examples](components/monitoring/sdk/c/examples/)
- [Python Examples](components/monitoring/sdk/python/examples/)
- [R Examples](components/monitoring/sdk/r/examples/)
- [Perl Examples](components/monitoring/sdk/perl/examples/)
- [Java Examples](components/monitoring/sdk/java/src/main/java/io/wafermonitor/monitoring/examples/)

### Other
- [Runtime Config Summary](RUNTIME_CONFIG_SUMMARY.md)
- [Configuration Schema](docs/config-schema.md)

---

## 🎯 Summary

Runtime configuration enables:
- ✅ **Zero-downtime** backend changes
- ✅ **Fault-tolerant** config updates
- ✅ **Flexible** routing strategies
- ✅ **Easy** integration of new flows
- ✅ **Production-ready** with fallbacks

**Key Features:**
- File-based configuration (JSON/YAML)
- Automatic change detection
- Hot-swapping backends
- Graceful error handling
- Thread-safe operations
- Comprehensive status monitoring

---

**Version:** 0.3.0+  
**Last Updated:** 2025-10-20  
**Maintained By:** Wafer Monitor Team

