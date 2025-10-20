package io.wafermonitor.monitoring;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.nio.file.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.BiConsumer;

/**
 * Runtime Configuration Manager with Hot-Reloading for Java SDK
 * 
 * Enables dynamic backend routing changes without restarting JVM.
 * 
 * Features:
 * - Load configuration from YAML/JSON/Properties files
 * - Auto-detection of file changes using WatchService
 * - Hot-reload backends without restart
 * - Callback support for reload events
 * - Fallback to default configuration
 * - Thread-safe operations
 * 
 * @author Wafer Monitor Team
 * @version 0.3.0
 * @since 0.3.0
 */
public class RuntimeConfigManager {
    private static final Logger logger = LoggerFactory.getLogger(RuntimeConfigManager.class);
    
    private final AtomicBoolean initialized = new AtomicBoolean(false);
    private final AtomicReference<File> configFile = new AtomicReference<>();
    private final AtomicLong checkInterval = new AtomicLong(30000); // milliseconds
    private final AtomicBoolean autoReload = new AtomicBoolean(false);
    private final AtomicReference<BiConsumer<Boolean, String>> onReload = new AtomicReference<>();
    private final AtomicLong lastMtime = new AtomicLong(0);
    private final AtomicLong lastReloadTime = new AtomicLong(0);
    private final AtomicBoolean lastReloadSuccess = new AtomicBoolean(false);
    private final AtomicReference<MonitoringConfig> defaultConfig = new AtomicReference<>();
    private final AtomicBoolean useFallback = new AtomicBoolean(true);
    
    private WatchService watchService;
    private ExecutorService watcherExecutor;
    private Future<?> watcherFuture;
    
    private static final RuntimeConfigManager INSTANCE = new RuntimeConfigManager();
    
    private RuntimeConfigManager() {}
    
    /**
     * Get the singleton instance
     * 
     * @return RuntimeConfigManager instance
     */
    public static RuntimeConfigManager getInstance() {
        return INSTANCE;
    }
    
    /**
     * Initialize SDK with runtime configuration
     * 
     * @param configFilePath Path to configuration file
     * @param defaultConfig Default configuration (fallback)
     * @param autoReload Enable automatic reloading
     * @param checkIntervalSeconds Check interval in seconds
     * @param onReloadCallback Callback for reload events
     * @param useFallback Use default config if file not found
     * @throws IOException if initialization fails
     */
    public synchronized void initWithRuntimeConfig(
        String configFilePath,
        MonitoringConfig defaultConfig,
        boolean autoReload,
        long checkIntervalSeconds,
        BiConsumer<Boolean, String> onReloadCallback,
        boolean useFallback
    ) throws IOException {
        if (initialized.get()) {
            throw new IllegalStateException("Runtime config already initialized. Call shutdown() first.");
        }
        
        // Store runtime options
        this.configFile.set(new File(configFilePath));
        this.checkInterval.set(checkIntervalSeconds * 1000);
        this.autoReload.set(autoReload);
        this.onReload.set(onReloadCallback);
        this.defaultConfig.set(defaultConfig);
        this.useFallback.set(useFallback);
        
        // Try to load config from file
        MonitoringConfig config = loadConfigFromFile(configFilePath);
        
        if (config == null && useFallback && defaultConfig != null) {
            config = defaultConfig;
            logger.info("Using default config as fallback");
        } else if (config == null) {
            throw new IOException("Failed to load config and no fallback available");
        }
        
        // Initialize SDK with loaded config
        try {
            MonitoringSDK.initialize(config);
            lastReloadTime.set(System.currentTimeMillis());
            lastReloadSuccess.set(true);
            logger.info("✓ SDK initialized with runtime config from: {}", configFilePath);
        } catch (Exception e) {
            if (onReloadCallback != null) {
                onReloadCallback.accept(false, "Init failed: " + e.getMessage());
            }
            throw new IOException("Failed to initialize SDK", e);
        }
        
        // Get initial file mtime
        File file = this.configFile.get();
        if (file.exists()) {
            lastMtime.set(file.lastModified());
        }
        
        // Start auto-reload watcher if enabled
        if (autoReload) {
            startFileWatcher();
        }
        
        initialized.set(true);
        
        if (onReloadCallback != null) {
            onReloadCallback.accept(true, "Initial configuration loaded");
        }
    }
    
    /**
     * Manually reload configuration from file
     * 
     * @return true if reload successful, false otherwise
     */
    public boolean reloadConfig() {
        if (!initialized.get()) {
            logger.warn("Runtime config not initialized");
            return false;
        }
        
        logger.info("Manually reloading configuration...");
        return reloadConfigInternal();
    }
    
    /**
     * Get runtime configuration status
     * 
     * @return RuntimeStatus object with status information
     */
    public RuntimeStatus getStatus() {
        if (!initialized.get()) {
            return new RuntimeStatus(false, null, false, 0, 0, false);
        }
        
        return new RuntimeStatus(
            initialized.get(),
            configFile.get().getPath(),
            autoReload.get(),
            checkInterval.get() / 1000,
            lastReloadTime.get(),
            lastReloadSuccess.get()
        );
    }
    
    /**
     * Enable or disable auto-reload
     * 
     * @param enabled true to enable, false to disable
     */
    public synchronized void setAutoReload(boolean enabled) {
        if (!initialized.get()) {
            logger.warn("Runtime config not initialized");
            return;
        }
        
        if (enabled && !autoReload.get()) {
            try {
                startFileWatcher();
                autoReload.set(true);
                logger.info("Auto-reload enabled");
            } catch (IOException e) {
                logger.error("Failed to start file watcher", e);
            }
        } else if (!enabled && autoReload.get()) {
            stopFileWatcher();
            autoReload.set(false);
            logger.info("Auto-reload disabled");
        }
    }
    
    /**
     * Shutdown runtime configuration system
     */
    public synchronized void shutdown() {
        if (!initialized.get()) {
            return;
        }
        
        stopFileWatcher();
        MonitoringSDK.shutdown();
        
        initialized.set(false);
        configFile.set(null);
        
        logger.info("✓ Runtime config shut down");
    }
    
    // ========================================================================
    // Internal Methods
    // ========================================================================
    
    private MonitoringConfig loadConfigFromFile(String filePath) {
        File file = new File(filePath);
        
        if (!file.exists()) {
            logger.warn("Config file not found: {}", filePath);
            return null;
        }
        
        try {
            ObjectMapper mapper;
            if (filePath.toLowerCase().endsWith(".yaml") || filePath.toLowerCase().endsWith(".yml")) {
                mapper = new ObjectMapper(new YAMLFactory());
            } else {
                mapper = new ObjectMapper();
            }
            
            MonitoringConfig config = mapper.readValue(file, MonitoringConfig.class);
            logger.info("Config loaded from: {}", filePath);
            return config;
            
        } catch (IOException e) {
            logger.error("Failed to load config file: {}", e.getMessage());
            return null;
        }
    }
    
    private boolean reloadConfigInternal() {
        MonitoringConfig config = loadConfigFromFile(configFile.get().getPath());
        
        if (config == null) {
            lastReloadSuccess.set(false);
            lastReloadTime.set(System.currentTimeMillis());
            
            String msg = "Failed to load config file";
            logger.error(msg);
            BiConsumer<Boolean, String> callback = onReload.get();
            if (callback != null) {
                callback.accept(false, msg);
            }
            return false;
        }
        
        try {
            // Shutdown current SDK
            MonitoringSDK.shutdown();
            
            // Re-initialize with new config
            MonitoringSDK.initialize(config);
            
            lastReloadSuccess.set(true);
            lastReloadTime.set(System.currentTimeMillis());
            
            String msg = "Configuration reloaded successfully";
            logger.info("✓ {}", msg);
            BiConsumer<Boolean, String> callback = onReload.get();
            if (callback != null) {
                callback.accept(true, msg);
            }
            
            return true;
            
        } catch (Exception e) {
            lastReloadSuccess.set(false);
            lastReloadTime.set(System.currentTimeMillis());
            
            String msg = "Failed to apply new config: " + e.getMessage();
            logger.error(msg);
            BiConsumer<Boolean, String> callback = onReload.get();
            if (callback != null) {
                callback.accept(false, msg);
            }
            
            return false;
        }
    }
    
    private boolean checkFileChanged() {
        File file = configFile.get();
        if (!file.exists()) {
            return false;
        }
        
        long currentMtime = file.lastModified();
        
        if (currentMtime > lastMtime.get()) {
            // File was modified
            lastMtime.set(currentMtime);
            
            // Small delay to ensure file write is complete
            try {
                Thread.sleep(100);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            
            logger.info("Config file changed, reloading...");
            reloadConfigInternal();
            
            return true;
        }
        
        return false;
    }
    
    private void startFileWatcher() throws IOException {
        if (watchService != null) {
            return; // Already running
        }
        
        File file = configFile.get();
        Path dir = file.toPath().getParent();
        
        watchService = FileSystems.getDefault().newWatchService();
        dir.register(watchService, StandardWatchEventKinds.ENTRY_MODIFY);
        
        watcherExecutor = Executors.newSingleThreadExecutor(r -> {
            Thread t = new Thread(r, "RuntimeConfigWatcher");
            t.setDaemon(true);
            return t;
        });
        
        watcherFuture = watcherExecutor.submit(() -> {
            try {
                while (!Thread.currentThread().isInterrupted()) {
                    WatchKey key = watchService.poll(checkInterval.get(), TimeUnit.MILLISECONDS);
                    
                    if (key != null) {
                        for (WatchEvent<?> event : key.pollEvents()) {
                            Path changed = (Path) event.context();
                            if (changed.toString().equals(configFile.get().getName())) {
                                checkFileChanged();
                            }
                        }
                        key.reset();
                    }
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                logger.debug("File watcher interrupted");
            }
        });
        
        logger.info("File watcher started (check interval: {}s)", checkInterval.get() / 1000);
    }
    
    private void stopFileWatcher() {
        if (watcherFuture != null) {
            watcherFuture.cancel(true);
            watcherFuture = null;
        }
        
        if (watcherExecutor != null) {
            watcherExecutor.shutdownNow();
            try {
                watcherExecutor.awaitTermination(5, TimeUnit.SECONDS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            watcherExecutor = null;
        }
        
        if (watchService != null) {
            try {
                watchService.close();
            } catch (IOException e) {
                logger.warn("Error closing watch service", e);
            }
            watchService = null;
        }
        
        logger.info("File watcher stopped");
    }
    
    /**
     * Runtime status information
     */
    public static class RuntimeStatus {
        private final boolean initialized;
        private final String configFile;
        private final boolean autoReload;
        private final long checkIntervalSeconds;
        private final long lastReloadTime;
        private final boolean lastReloadSuccess;
        
        public RuntimeStatus(boolean initialized, String configFile, boolean autoReload,
                           long checkIntervalSeconds, long lastReloadTime, boolean lastReloadSuccess) {
            this.initialized = initialized;
            this.configFile = configFile;
            this.autoReload = autoReload;
            this.checkIntervalSeconds = checkIntervalSeconds;
            this.lastReloadTime = lastReloadTime;
            this.lastReloadSuccess = lastReloadSuccess;
        }
        
        public boolean isInitialized() { return initialized; }
        public String getConfigFile() { return configFile; }
        public boolean isAutoReload() { return autoReload; }
        public long getCheckIntervalSeconds() { return checkIntervalSeconds; }
        public long getLastReloadTime() { return lastReloadTime; }
        public boolean isLastReloadSuccess() { return lastReloadSuccess; }
        
        @Override
        public String toString() {
            return String.format("RuntimeStatus{initialized=%s, configFile='%s', autoReload=%s, " +
                               "checkInterval=%ds, lastReloadTime=%d, lastReloadSuccess=%s}",
                               initialized, configFile, autoReload, checkIntervalSeconds,
                               lastReloadTime, lastReloadSuccess);
        }
    }
}

