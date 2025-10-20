package io.wafermonitor.monitoring.examples;

import io.wafermonitor.monitoring.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.util.concurrent.TimeUnit;

/**
 * Runtime Configuration Example for Java SDK
 * 
 * Demonstrates:
 * - Loading config from YAML file
 * - Auto-detection of config changes
 * - Hot-reload without JVM restart
 * - Reload callbacks
 */
public class RuntimeConfigExample {
    private static final Logger logger = LoggerFactory.getLogger(RuntimeConfigExample.class);
    private static volatile boolean running = true;
    
    public static void main(String[] args) {
        System.out.println("=== Java SDK Runtime Configuration Example ===\n");
        
        // Config file path
        String configFile = args.length > 0 ? args[0] : "monitoring_config_java.yaml";
        System.out.println("Using config file: " + configFile + "\n");
        
        // Default configuration (fallback)
        MonitoringConfig defaultConfig = MonitoringConfig.builder()
            .mode(Mode.SIDECAR)
            .appName("runtime-config-java-example")
            .appVersion("1.0.0")
            .siteId("fab1")
            .instanceId("java-runtime-001")
            .sidecarUrl("http://localhost:17000")
            .build();
        
        // Reload callback
        RuntimeConfigManager manager = RuntimeConfigManager.getInstance();
        
        try {
            // Initialize with runtime config
            manager.initWithRuntimeConfig(
                configFile,
                defaultConfig,
                true,  // auto-reload
                10,    // check every 10 seconds
                (success, message) -> {
                    if (success) {
                        System.out.println("✓ Config reloaded: " + message);
                    } else {
                        System.err.println("✗ Config reload failed: " + message);
                    }
                },
                true   // use fallback
            );
            
            System.out.println("✓ SDK initialized with runtime config");
            System.out.println("✓ Config file: " + configFile);
            System.out.println("✓ Auto-reload: enabled (check every 10 seconds)\n");
            
            System.out.println("Running application...");
            System.out.println("Try editing '" + configFile + "' while this runs!");
            System.out.println("Add/remove backends and see them activated without restart.");
            System.out.println("Press Ctrl+C to stop.\n");
            
            // Setup shutdown hook
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                running = false;
                System.out.println("\n\nShutting down gracefully...");
                manager.shutdown();
            }));
            
            // Simulate long-running application
            int eventCount = 0;
            
            while (running) {
                // Send periodic events
                eventCount++;
                String entityId = "event-" + eventCount;
                
                try {
                    MonitoringContext ctx = MonitoringSDK.start("periodic-job", entityId);
                    if (ctx != null) {
                        ctx.progress(50, "processing");
                        ctx.addMetric("event_number", (double) eventCount);
                        ctx.finish();
                        
                        System.out.println("[" + eventCount + "] Sent event to active backends");
                    }
                } catch (Exception e) {
                    logger.error("Failed to send event", e);
                }
                
                // Display reload status
                RuntimeConfigManager.RuntimeStatus status = manager.getStatus();
                if (status.isInitialized() && status.getLastReloadTime() > 0) {
                    long elapsedSeconds = (System.currentTimeMillis() - status.getLastReloadTime()) / 1000;
                    System.out.printf("    Last reload: %d s ago (%s)%n",
                                    elapsedSeconds,
                                    status.isLastReloadSuccess() ? "success" : "failed");
                }
                
                try {
                    TimeUnit.SECONDS.sleep(5);  // Wait between events
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
            
            System.out.println("\n✓ Shutting down...");
            manager.shutdown();
            
            System.out.println("✓ Application stopped\n");
            System.out.println("Summary:");
            System.out.println("  - Events sent: " + eventCount);
            System.out.println("  - Config file: " + configFile);
            System.out.println("  - Final status: runtime config shut down\n");
            
        } catch (IOException e) {
            logger.error("Failed to initialize runtime config", e);
            System.exit(1);
        }
    }
}

