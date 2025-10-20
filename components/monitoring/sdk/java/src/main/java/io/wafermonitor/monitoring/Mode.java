package io.wafermonitor.monitoring;

/**
 * SDK operation mode.
 */
public enum Mode {
    /** Send events to a sidecar agent via HTTP */
    SIDECAR,
    
    /** Send events directly to backends (filesystem, S3, etc.) */
    DIRECT
}

