package io.wafermonitor.monitoring;

/**
 * Type of backend for direct mode.
 */
public enum BackendType {
    FILESYSTEM,
    S3,
    ELK,
    ZABBIX,
    WEBHOOK
}

