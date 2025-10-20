package io.wafermonitor.monitoring;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.Map;

/**
 * Context for monitoring a specific job or task.
 * 
 * <p>Provides methods to report progress, add metrics/metadata, and finish the context.
 */
public class MonitoringContext {
    private static final Logger logger = LoggerFactory.getLogger(MonitoringContext.class);
    
    private final String name;
    private final String entityId;
    private final EntityType entityType;
    private final MonitoringConfig config;
    private final Backend backend;
    private final long startTime;
    private final Map<String, Double> metrics;
    private final Map<String, String> metadata;
    
    MonitoringContext(String name, String entityId, EntityType entityType, 
                     MonitoringConfig config, Backend backend) {
        this.name = name;
        this.entityId = entityId;
        this.entityType = entityType;
        this.config = config;
        this.backend = backend;
        this.startTime = System.currentTimeMillis();
        this.metrics = new HashMap<>();
        this.metadata = new HashMap<>();
    }
    
    void start() {
        MonitoringEvent event = MonitoringEvent.builder()
            .idempotencyKey(String.format("%s-start-%d", entityId, startTime))
            .siteId(config.getSiteId())
            .appName(config.getAppName())
            .appVersion(config.getAppVersion())
            .entityType(entityType)
            .entityId(entityId)
            .eventKind(EventKind.STARTED)
            .timestamp(startTime / 1000.0)
            .status("started")
            .build();
        
        backend.sendEvent(event);
    }
    
    /**
     * Report progress for this context.
     *
     * @param progress the progress percentage (0-100)
     * @param message optional status message
     */
    public void progress(int progress, String message) {
        MonitoringEvent event = MonitoringEvent.builder()
            .idempotencyKey(String.format("%s-progress-%d", entityId, System.currentTimeMillis()))
            .siteId(config.getSiteId())
            .appName(config.getAppName())
            .appVersion(config.getAppVersion())
            .entityType(entityType)
            .entityId(entityId)
            .eventKind(EventKind.PROGRESS)
            .timestamp(System.currentTimeMillis() / 1000.0)
            .status(message != null ? message : "in_progress")
            .addMetric("progress", (double) progress)
            .build();
        
        backend.sendEvent(event);
    }
    
    /**
     * Add a metric to this context.
     *
     * @param key the metric name
     * @param value the metric value
     */
    public void addMetric(String key, double value) {
        metrics.put(key, value);
    }
    
    /**
     * Add metadata to this context.
     *
     * @param key the metadata key
     * @param value the metadata value
     */
    public void addMetadata(String key, String value) {
        metadata.put(key, value);
    }
    
    /**
     * Finish this context successfully.
     */
    public void finish() {
        // Add duration metric
        double duration = (System.currentTimeMillis() - startTime) / 1000.0;
        metrics.put("duration_seconds", duration);
        
        MonitoringEvent.Builder eventBuilder = MonitoringEvent.builder()
            .idempotencyKey(String.format("%s-finish-%d", entityId, System.currentTimeMillis()))
            .siteId(config.getSiteId())
            .appName(config.getAppName())
            .appVersion(config.getAppVersion())
            .entityType(entityType)
            .entityId(entityId)
            .eventKind(EventKind.FINISHED)
            .timestamp(System.currentTimeMillis() / 1000.0)
            .status("success");
        
        for (Map.Entry<String, Double> entry : metrics.entrySet()) {
            eventBuilder.addMetric(entry.getKey(), entry.getValue());
        }
        
        for (Map.Entry<String, String> entry : metadata.entrySet()) {
            eventBuilder.addMetadata(entry.getKey(), entry.getValue());
        }
        
        backend.sendEvent(eventBuilder.build());
    }
    
    /**
     * Finish this context with an error.
     *
     * @param errorMessage the error message
     */
    public void error(String errorMessage) {
        if (errorMessage != null) {
            metadata.put("error", errorMessage);
        }
        
        MonitoringEvent.Builder eventBuilder = MonitoringEvent.builder()
            .idempotencyKey(String.format("%s-error-%d", entityId, System.currentTimeMillis()))
            .siteId(config.getSiteId())
            .appName(config.getAppName())
            .appVersion(config.getAppVersion())
            .entityType(entityType)
            .entityId(entityId)
            .eventKind(EventKind.ERROR)
            .timestamp(System.currentTimeMillis() / 1000.0)
            .status("error");
        
        for (Map.Entry<String, Double> entry : metrics.entrySet()) {
            eventBuilder.addMetric(entry.getKey(), entry.getValue());
        }
        
        for (Map.Entry<String, String> entry : metadata.entrySet()) {
            eventBuilder.addMetadata(entry.getKey(), entry.getValue());
        }
        
        backend.sendEvent(eventBuilder.build());
    }
    
    /**
     * Cancel this context.
     */
    public void cancel() {
        MonitoringEvent event = MonitoringEvent.builder()
            .idempotencyKey(String.format("%s-cancel-%d", entityId, System.currentTimeMillis()))
            .siteId(config.getSiteId())
            .appName(config.getAppName())
            .appVersion(config.getAppVersion())
            .entityType(entityType)
            .entityId(entityId)
            .eventKind(EventKind.CANCELED)
            .timestamp(System.currentTimeMillis() / 1000.0)
            .status("canceled")
            .build();
        
        backend.sendEvent(event);
    }
    
    public String getName() { return name; }
    public String getEntityId() { return entityId; }
    public EntityType getEntityType() { return entityType; }
}

