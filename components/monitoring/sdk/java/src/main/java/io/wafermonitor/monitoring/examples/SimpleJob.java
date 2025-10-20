package io.wafermonitor.monitoring.examples;

import io.wafermonitor.monitoring.*;

/**
 * Simple example of using the Java monitoring SDK.
 */
public class SimpleJob {
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Java SDK Simple Job Example ===\n");
        
        // Initialize SDK
        MonitoringSDK.init(
            MonitoringConfig.builder()
                .mode(Mode.SIDECAR)
                .appName("example-java-job")
                .appVersion("1.0.0")
                .siteId("fab1")
                .sidecarUrl("http://localhost:17000")
                .build()
        );
        
        System.out.println("✓ SDK initialized");
        System.out.println("✓ Version: " + MonitoringSDK.getVersion());
        System.out.println();
        
        // Start monitored job
        System.out.println("Starting monitored job...");
        MonitoringContext ctx = MonitoringSDK.start("process-wafer", "JAVA-12345");
        
        // Simulate work with progress updates
        for (int i = 1; i <= 5; i++) {
            Thread.sleep(1000);
            int progress = i * 20;
            String message = String.format("Processing step %d/5", i);
            
            ctx.progress(progress, message);
            System.out.printf("  [%3d%%] %s%n", progress, message);
            
            // Add some metrics
            ctx.addMetric("temperature", 75.5 + i);
            ctx.addMetric("pressure", 1013.25 - i * 0.5);
        }
        
        // Add final metadata
        ctx.addMetadata("operator", "john.doe");
        ctx.addMetadata("machine_id", "WFR-001");
        
        // Finish successfully
        System.out.println("\n✓ Job completed successfully");
        ctx.finish();
        
        // Cleanup
        MonitoringSDK.shutdown();
        System.out.println("✓ SDK shut down\n");
    }
}

