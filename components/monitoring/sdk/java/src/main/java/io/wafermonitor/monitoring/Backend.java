package io.wafermonitor.monitoring;

/**
 * Interface for monitoring backends.
 */
public interface Backend {
    /**
     * Send a monitoring event.
     *
     * @param event the event to send
     */
    void sendEvent(MonitoringEvent event);
    
    /**
     * Close the backend and release resources.
     */
    void close();
}

