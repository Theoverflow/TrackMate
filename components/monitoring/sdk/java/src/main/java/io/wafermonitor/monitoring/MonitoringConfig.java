package io.wafermonitor.monitoring;

import java.net.InetAddress;
import java.net.UnknownHostException;
import java.util.HashMap;
import java.util.Map;

/**
 * Configuration for the monitoring SDK.
 */
public class MonitoringConfig {
    private final Mode mode;
    private final String appName;
    private final String appVersion;
    private final String siteId;
    private final String instanceId;
    private final String sidecarUrl;
    private final float timeout;
    private final int maxRetries;
    private final BackendType backendType;
    private final Map<String, Object> backendConfig;
    
    private MonitoringConfig(Builder builder) {
        this.mode = builder.mode;
        this.appName = builder.appName;
        this.appVersion = builder.appVersion;
        this.siteId = builder.siteId;
        this.instanceId = builder.instanceId != null ? builder.instanceId : getDefaultInstanceId();
        this.sidecarUrl = builder.sidecarUrl;
        this.timeout = builder.timeout;
        this.maxRetries = builder.maxRetries;
        this.backendType = builder.backendType;
        this.backendConfig = builder.backendConfig;
    }
    
    private static String getDefaultInstanceId() {
        try {
            return InetAddress.getLocalHost().getHostName();
        } catch (UnknownHostException e) {
            return "unknown-host";
        }
    }
    
    public Mode getMode() { return mode; }
    public String getAppName() { return appName; }
    public String getAppVersion() { return appVersion; }
    public String getSiteId() { return siteId; }
    public String getInstanceId() { return instanceId; }
    public String getSidecarUrl() { return sidecarUrl; }
    public float getTimeout() { return timeout; }
    public int getMaxRetries() { return maxRetries; }
    public BackendType getBackendType() { return backendType; }
    public Map<String, Object> getBackendConfig() { return backendConfig; }
    
    public static Builder builder() {
        return new Builder();
    }
    
    public static class Builder {
        private Mode mode = Mode.SIDECAR;
        private String appName;
        private String appVersion;
        private String siteId;
        private String instanceId;
        private String sidecarUrl = "http://localhost:17000";
        private float timeout = 5.0f;
        private int maxRetries = 3;
        private BackendType backendType = BackendType.FILESYSTEM;
        private Map<String, Object> backendConfig = new HashMap<>();
        
        public Builder mode(Mode mode) {
            this.mode = mode;
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
        
        public Builder siteId(String siteId) {
            this.siteId = siteId;
            return this;
        }
        
        public Builder instanceId(String instanceId) {
            this.instanceId = instanceId;
            return this;
        }
        
        public Builder sidecarUrl(String sidecarUrl) {
            this.sidecarUrl = sidecarUrl;
            return this;
        }
        
        public Builder timeout(float timeout) {
            this.timeout = timeout;
            return this;
        }
        
        public Builder maxRetries(int maxRetries) {
            this.maxRetries = maxRetries;
            return this;
        }
        
        public Builder backendType(BackendType backendType) {
            this.backendType = backendType;
            return this;
        }
        
        public Builder backendConfig(Map<String, Object> backendConfig) {
            this.backendConfig = backendConfig;
            return this;
        }
        
        public MonitoringConfig build() {
            if (appName == null || appName.isEmpty()) {
                throw new IllegalArgumentException("appName is required");
            }
            if (appVersion == null || appVersion.isEmpty()) {
                throw new IllegalArgumentException("appVersion is required");
            }
            if (siteId == null || siteId.isEmpty()) {
                throw new IllegalArgumentException("siteId is required");
            }
            
            return new MonitoringConfig(this);
        }
    }
}

