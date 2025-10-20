package io.wafermonitor.monitoring;

import java.util.HashMap;
import java.util.Map;

/**
 * Monitoring event structure.
 */
public class MonitoringEvent {
    private final String idempotencyKey;
    private final String siteId;
    private final String appName;
    private final String appVersion;
    private final EntityType entityType;
    private final String entityId;
    private final EventKind eventKind;
    private final double timestamp;
    private final String status;
    private final Map<String, Double> metrics;
    private final Map<String, String> metadata;
    
    private MonitoringEvent(Builder builder) {
        this.idempotencyKey = builder.idempotencyKey;
        this.siteId = builder.siteId;
        this.appName = builder.appName;
        this.appVersion = builder.appVersion;
        this.entityType = builder.entityType;
        this.entityId = builder.entityId;
        this.eventKind = builder.eventKind;
        this.timestamp = builder.timestamp;
        this.status = builder.status;
        this.metrics = builder.metrics;
        this.metadata = builder.metadata;
    }
    
    public String getIdempotencyKey() { return idempotencyKey; }
    public String getSiteId() { return siteId; }
    public String getAppName() { return appName; }
    public String getAppVersion() { return appVersion; }
    public EntityType getEntityType() { return entityType; }
    public String getEntityId() { return entityId; }
    public EventKind getEventKind() { return eventKind; }
    public double getTimestamp() { return timestamp; }
    public String getStatus() { return status; }
    public Map<String, Double> getMetrics() { return metrics; }
    public Map<String, String> getMetadata() { return metadata; }
    
    public static Builder builder() {
        return new Builder();
    }
    
    public static class Builder {
        private String idempotencyKey;
        private String siteId;
        private String appName;
        private String appVersion;
        private EntityType entityType;
        private String entityId;
        private EventKind eventKind;
        private double timestamp;
        private String status;
        private Map<String, Double> metrics = new HashMap<>();
        private Map<String, String> metadata = new HashMap<>();
        
        public Builder idempotencyKey(String idempotencyKey) {
            this.idempotencyKey = idempotencyKey;
            return this;
        }
        
        public Builder siteId(String siteId) {
            this.siteId = siteId;
            return this;
        }
        
        public Builder appName(String appName) {
            this.appName = appName;
            return this;
        }
        
        public Builder appVersion(String appVersion) {
            this.appVersion = appVersion;
            return this;
        }
        
        public Builder entityType(EntityType entityType) {
            this.entityType = entityType;
            return this;
        }
        
        public Builder entityId(String entityId) {
            this.entityId = entityId;
            return this;
        }
        
        public Builder eventKind(EventKind eventKind) {
            this.eventKind = eventKind;
            return this;
        }
        
        public Builder timestamp(double timestamp) {
            this.timestamp = timestamp;
            return this;
        }
        
        public Builder status(String status) {
            this.status = status;
            return this;
        }
        
        public Builder addMetric(String key, double value) {
            this.metrics.put(key, value);
            return this;
        }
        
        public Builder addMetadata(String key, String value) {
            this.metadata.put(key, value);
            return this;
        }
        
        public MonitoringEvent build() {
            return new MonitoringEvent(this);
        }
    }
}

