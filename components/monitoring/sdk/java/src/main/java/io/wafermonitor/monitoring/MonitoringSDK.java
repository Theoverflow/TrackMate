package io.wafermonitor.monitoring;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Main entry point for the Wafer Monitor Java SDK.
 * 
 * <p>Example usage:
 * <pre>{@code
 * MonitoringSDK.init(
 *     MonitoringConfig.builder()
 *         .mode(Mode.SIDECAR)
 *         .appName("my-java-app")
 *         .appVersion("1.0.0")
 *         .siteId("fab1")
 *         .sidecarUrl("http://localhost:17000")
 *         .build()
 * );
 * 
 * MonitoringContext ctx = MonitoringSDK.start("process-wafer", "W-12345");
 * ctx.progress(50, "halfway");
 * ctx.addMetric("temperature", 75.5);
 * ctx.finish();
 * 
 * MonitoringSDK.shutdown();
 * }</pre>
 *
 * @since 0.3.0
 */
public class MonitoringSDK {
    private static final Logger logger = LoggerFactory.getLogger(MonitoringSDK.class);
    private static final String VERSION = "0.3.0";
    
    private static volatile boolean initialized = false;
    private static MonitoringConfig config;
    private static Backend backend;
    
    /**
     * Initialize the monitoring SDK with the given configuration.
     *
     * @param config the configuration to use
     * @throws IllegalStateException if already initialized
     */
    public static synchronized void init(MonitoringConfig config) {
        if (initialized) {
            throw new IllegalStateException("SDK already initialized. Call shutdown() first.");
        }
        
        if (config == null) {
            throw new IllegalArgumentException("config cannot be null");
        }
        
        MonitoringSDK.config = config;
        
        // Initialize backend
        if (config.getMode() == Mode.SIDECAR) {
            backend = new SidecarBackend(
                config.getSidecarUrl(),
                config.getTimeout(),
                config.getMaxRetries()
            );
        } else {
            BackendType backendType = config.getBackendType();
            if (backendType == BackendType.FILESYSTEM) {
                backend = new FilesystemBackend(config.getBackendConfig());
            } else {
                throw new UnsupportedOperationException("Backend type not supported: " + backendType);
            }
        }
        
        initialized = true;
        logger.info("✓ Monitoring SDK initialized (mode={}, version={})", config.getMode(), VERSION);
    }
    
    /**
     * Shutdown the monitoring SDK and release resources.
     */
    public static synchronized void shutdown() {
        if (!initialized) {
            logger.warn("SDK not initialized");
            return;
        }
        
        if (backend != null) {
            backend.close();
        }
        
        initialized = false;
        config = null;
        backend = null;
        
        logger.info("✓ Monitoring SDK shut down");
    }
    
    /**
     * Check if the SDK is initialized.
     *
     * @return true if initialized, false otherwise
     */
    public static boolean isInitialized() {
        return initialized;
    }
    
    /**
     * Get the SDK version.
     *
     * @return the version string
     */
    public static String getVersion() {
        return VERSION;
    }
    
    /**
     * Start a monitored context.
     *
     * @param name the name of the job/task
     * @param entityId the unique entity identifier
     * @return a new monitoring context
     * @throws IllegalStateException if SDK is not initialized
     */
    public static MonitoringContext start(String name, String entityId) {
        return start(name, entityId, EntityType.JOB);
    }
    
    /**
     * Start a monitored context with a specific entity type.
     *
     * @param name the name of the job/task
     * @param entityId the unique entity identifier
     * @param entityType the type of entity
     * @return a new monitoring context
     * @throws IllegalStateException if SDK is not initialized
     */
    public static MonitoringContext start(String name, String entityId, EntityType entityType) {
        if (!initialized) {
            throw new IllegalStateException("SDK not initialized. Call init() first.");
        }
        
        if (name == null || name.isEmpty()) {
            throw new IllegalArgumentException("name cannot be null or empty");
        }
        
        if (entityId == null || entityId.isEmpty()) {
            throw new IllegalArgumentException("entityId cannot be null or empty");
        }
        
        MonitoringContext context = new MonitoringContext(name, entityId, entityType, config, backend);
        context.start();
        
        return context;
    }
    
    /**
     * Get the current configuration.
     *
     * @return the configuration, or null if not initialized
     */
    static MonitoringConfig getConfig() {
        return config;
    }
    
    /**
     * Get the current backend.
     *
     * @return the backend, or null if not initialized
     */
    static Backend getBackend() {
        return backend;
    }
}

