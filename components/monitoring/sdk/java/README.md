# Wafer Monitor Java SDK

Production-ready Java library for monitoring distributed applications and sending events to the Wafer Monitor system.

## Features

- ✅ **Modern Java**: Built for Java 11+
- ✅ **Fluent API**: Builder pattern throughout
- ✅ **Type Safety**: Strong typing with enums
- ✅ **Thread Safe**: Can be used from multiple threads
- ✅ **SLF4J Logging**: Integrates with your logging framework
- ✅ **Maven/Gradle**: Easy dependency management

## Installation

### Maven

```xml
<dependency>
    <groupId>io.wafermonitor</groupId>
    <artifactId>monitoring-sdk</artifactId>
    <version>0.3.0</version>
</dependency>
```

### Gradle

```gradle
implementation 'io.wafermonitor:monitoring-sdk:0.3.0'
```

## Quick Start

```java
import io.wafermonitor.monitoring.*;

public class MyApplication {
    public static void main(String[] args) {
        // Initialize SDK
        MonitoringSDK.init(
            MonitoringConfig.builder()
                .mode(Mode.SIDECAR)
                .appName("my-java-app")
                .appVersion("1.0.0")
                .siteId("fab1")
                .sidecarUrl("http://localhost:17000")
                .build()
        );
        
        // Monitor a job
        MonitoringContext ctx = MonitoringSDK.start("process-wafer", "W-12345");
        ctx.progress(50, "halfway");
        ctx.addMetric("temperature", 75.5);
        ctx.finish();
        
        // Cleanup
        MonitoringSDK.shutdown();
    }
}
```

## API Reference

### Initialization

```java
MonitoringSDK.init(
    MonitoringConfig.builder()
        .mode(Mode.SIDECAR)         // or Mode.DIRECT
        .appName("my-app")
        .appVersion("1.0.0")
        .siteId("fab1")
        .instanceId("instance-001")  // optional
        .sidecarUrl("http://localhost:17000")
        .timeout(5.0f)               // optional
        .maxRetries(3)               // optional
        .build()
);

MonitoringSDK.shutdown();
MonitoringSDK.isInitialized();
String version = MonitoringSDK.getVersion();
```

### Context API

```java
// Start monitoring
MonitoringContext ctx = MonitoringSDK.start("job-name", "job-001");
MonitoringContext ctx = MonitoringSDK.start("job-name", "job-001", EntityType.TASK);

// Report progress
ctx.progress(50, "halfway");

// Add metrics
ctx.addMetric("temperature", 75.5);
ctx.addMetric("pressure", 1013.25);

// Add metadata
ctx.addMetadata("operator", "john.doe");
ctx.addMetadata("machine_id", "WFR-001");

// Finish
ctx.finish();         // Success
ctx.error("message"); // Error
ctx.cancel();         // Cancel
```

## Examples

### Basic Usage

```java
MonitoringContext ctx = MonitoringSDK.start("process-data", "DATA-001");
ctx.progress(25, "loading data");
ctx.progress(50, "processing");
ctx.progress(75, "saving results");
ctx.finish();
```

### Error Handling

```java
MonitoringContext ctx = MonitoringSDK.start("risky-job", "JOB-001");
try {
    // ... do work ...
    ctx.finish();
} catch (Exception e) {
    ctx.error(e.getMessage());
    throw e;
}
```

### Multi-threaded Application

```java
ExecutorService executor = Executors.newFixedThreadPool(4);

for (int i = 0; i < 100; i++) {
    final int taskId = i;
    executor.submit(() -> {
        MonitoringContext ctx = MonitoringSDK.start(
            "parallel-task",
            "task-" + taskId
        );
        // ... do work ...
        ctx.finish();
    });
}

executor.shutdown();
executor.awaitTermination(1, TimeUnit.HOURS);
```

## Configuration

### Sidecar Mode (Recommended)

```java
MonitoringConfig config = MonitoringConfig.builder()
    .mode(Mode.SIDECAR)
    .appName("my-java-app")
    .appVersion("1.0.0")
    .siteId("fab1")
    .sidecarUrl("http://localhost:17000")
    .timeout(5.0f)
    .maxRetries(3)
    .build();

MonitoringSDK.init(config);
```

### Direct Mode (File Backend)

```java
Map<String, Object> backendConfig = new HashMap<>();
backendConfig.put("output_dir", "./monitoring_events");
backendConfig.put("filename_prefix", "events");

MonitoringConfig config = MonitoringConfig.builder()
    .mode(Mode.DIRECT)
    .appName("my-java-app")
    .appVersion("1.0.0")
    .siteId("fab1")
    .backendType(BackendType.FILESYSTEM)
    .backendConfig(backendConfig)
    .build();

MonitoringSDK.init(config);
```

## Building from Source

```bash
# Clone repository
git clone https://github.com/your-org/wafer-monitor

# Build
cd components/monitoring/sdk/java
mvn clean install

# Run tests
mvn test

# Run example
mvn exec:java -Dexec.mainClass="io.wafermonitor.monitoring.examples.SimpleJob"
```

## Testing

```bash
# Run all tests
mvn test

# Run with coverage
mvn test jacoco:report

# Run specific test
mvn test -Dtest=MonitoringSDKTest
```

## Logging

The SDK uses SLF4J for logging. Configure your preferred logging framework:

### Logback

```xml
<logger name="io.wafermonitor.monitoring" level="INFO"/>
```

### Log4j2

```xml
<Logger name="io.wafermonitor.monitoring" level="info"/>
```

## Requirements

- Java 11 or later
- Maven 3.6+ or Gradle 7+ (for building)

## License

MIT License - See LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: https://github.com/your-org/wafer-monitor
- Documentation: https://docs.wafer-monitor.io
- Javadoc: https://javadoc.io/doc/io.wafermonitor/monitoring-sdk

