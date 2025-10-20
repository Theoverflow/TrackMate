package io.wafermonitor.monitoring;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.hc.client5.http.classic.methods.HttpPost;
import org.apache.hc.client5.http.impl.classic.CloseableHttpClient;
import org.apache.hc.client5.http.impl.classic.HttpClients;
import org.apache.hc.core5.http.io.entity.StringEntity;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;

/**
 * Backend that sends events to a sidecar agent via HTTP.
 */
class SidecarBackend implements Backend {
    private static final Logger logger = LoggerFactory.getLogger(SidecarBackend.class);
    
    private final String url;
    private final float timeout;
    private final int maxRetries;
    private final CloseableHttpClient httpClient;
    private final ObjectMapper objectMapper;
    
    public SidecarBackend(String url, float timeout, int maxRetries) {
        this.url = url;
        this.timeout = timeout;
        this.maxRetries = maxRetries;
        this.httpClient = HttpClients.createDefault();
        this.objectMapper = new ObjectMapper();
    }
    
    @Override
    public void sendEvent(MonitoringEvent event) {
        String endpoint = url + "/v1/ingest/events";
        
        try {
            String jsonData = objectMapper.writeValueAsString(event);
            
            for (int attempt = 1; attempt <= maxRetries; attempt++) {
                try {
                    HttpPost post = new HttpPost(endpoint);
                    post.setEntity(new StringEntity(jsonData));
                    post.setHeader("Content-Type", "application/json");
                    
                    httpClient.execute(post, response -> {
                        int statusCode = response.getCode();
                        if (statusCode >= 200 && statusCode < 300) {
                            logger.debug("Event sent successfully");
                        } else if (statusCode >= 400 && statusCode < 500) {
                            logger.warn("Client error {}: not retrying", statusCode);
                        } else {
                            logger.warn("Server error {}: retry {} of {}", statusCode, attempt, maxRetries);
                            if (attempt < maxRetries) {
                                Thread.sleep((long) (100 * Math.pow(2, attempt)));
                            }
                        }
                        return null;
                    });
                    
                    return; // Success
                    
                } catch (Exception e) {
                    logger.error("Error sending event (attempt {} of {}): {}", attempt, maxRetries, e.getMessage());
                    if (attempt < maxRetries) {
                        Thread.sleep((long) (100 * Math.pow(2, attempt)));
                    }
                }
            }
            
            logger.error("Failed to send event after {} attempts", maxRetries);
            
        } catch (Exception e) {
            logger.error("Failed to serialize event", e);
        }
    }
    
    @Override
    public void close() {
        try {
            httpClient.close();
        } catch (IOException e) {
            logger.error("Error closing HTTP client", e);
        }
    }
}

