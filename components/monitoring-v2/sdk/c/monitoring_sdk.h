/**
 * MonitoringSDK - C
 * Lightweight TCP-based monitoring instrumentation
 * 
 * Version: 2.0.0
 */

#ifndef MONITORING_SDK_H
#define MONITORING_SDK_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Constants */
#define MONITORING_MAX_SOURCE_LEN   128
#define MONITORING_MAX_HOST_LEN     256
#define MONITORING_MAX_MESSAGE_LEN  512
#define MONITORING_MAX_BUFFER_SIZE  1000
#define MONITORING_MAX_ID_LEN       32

/* Error codes */
typedef enum {
    MONITORING_OK = 0,
    MONITORING_ERROR_CONNECTION = -1,
    MONITORING_ERROR_SEND = -2,
    MONITORING_ERROR_BUFFER_FULL = -3,
    MONITORING_ERROR_INVALID_PARAM = -4,
    MONITORING_ERROR_NOT_INITIALIZED = -5
} monitoring_error_t;

/* Connection states */
typedef enum {
    MONITORING_STATE_DISCONNECTED = 0,
    MONITORING_STATE_CONNECTED = 1,
    MONITORING_STATE_OVERFLOW = 2
} monitoring_state_t;

/* SDK handle (opaque) */
typedef struct monitoring_sdk monitoring_sdk_t;

/**
 * Create monitoring SDK instance
 * 
 * @param source Source identifier (service/script name)
 * @param tcp_host TCP host (default: "localhost")
 * @param tcp_port TCP port (default: 17000)
 * @return SDK handle or NULL on error
 */
monitoring_sdk_t* monitoring_sdk_create(const char* source, const char* tcp_host, int tcp_port);

/**
 * Destroy SDK instance and cleanup
 * 
 * @param sdk SDK handle
 */
void monitoring_sdk_destroy(monitoring_sdk_t* sdk);

/**
 * Log an event
 * 
 * @param sdk SDK handle
 * @param level Log level (debug, info, warn, error, fatal)
 * @param message Event message
 * @param context_json Optional context as JSON string (can be NULL)
 * @return MONITORING_OK on success
 */
monitoring_error_t monitoring_log_event(
    monitoring_sdk_t* sdk,
    const char* level,
    const char* message,
    const char* context_json
);

/**
 * Log a metric
 * 
 * @param sdk SDK handle
 * @param name Metric name
 * @param value Metric value
 * @param unit Unit of measurement
 * @param tags_json Optional tags as JSON string (can be NULL)
 * @return MONITORING_OK on success
 */
monitoring_error_t monitoring_log_metric(
    monitoring_sdk_t* sdk,
    const char* name,
    double value,
    const char* unit,
    const char* tags_json
);

/**
 * Log job progress
 * 
 * @param sdk SDK handle
 * @param job_id Job identifier
 * @param percent Completion percentage (0-100)
 * @param status Status description
 * @return MONITORING_OK on success
 */
monitoring_error_t monitoring_log_progress(
    monitoring_sdk_t* sdk,
    const char* job_id,
    int percent,
    const char* status
);

/**
 * Log resource usage
 * 
 * If values are negative, automatically collects current system metrics
 * 
 * @param sdk SDK handle
 * @param cpu_percent CPU usage percentage (-1 for auto)
 * @param memory_mb Memory usage in MB (-1 for auto)
 * @param disk_io_mb Disk I/O in MB (-1 for auto)
 * @param network_io_mb Network I/O in MB (-1 for auto)
 * @return MONITORING_OK on success
 */
monitoring_error_t monitoring_log_resource(
    monitoring_sdk_t* sdk,
    double cpu_percent,
    double memory_mb,
    double disk_io_mb,
    double network_io_mb
);

/**
 * Start job analysis for a business process
 * 
 * @param sdk SDK handle
 * @param job_name Name of the job/process
 * @param job_type Type of job (main, subjob, multiprocess)
 * @return Job ID string (caller must free) or NULL on error
 */
char* monitoring_start_job_analysis(monitoring_sdk_t* sdk, const char* job_name, const char* job_type);

/**
 * Track a subjob (child process, thread, or task)
 * 
 * @param sdk SDK handle
 * @param subjob_name Name of the subjob
 * @param subjob_type Type (process, thread, task)
 * @return Subjob ID string (caller must free) or NULL on error
 */
char* monitoring_track_subjob(monitoring_sdk_t* sdk, const char* subjob_name, const char* subjob_type);

/**
 * End tracking a subjob
 * 
 * @param sdk SDK handle
 * @param subjob_id Subjob ID returned by monitoring_track_subjob
 * @param status Completion status
 * @return MONITORING_OK on success
 */
monitoring_error_t monitoring_end_subjob(monitoring_sdk_t* sdk, const char* subjob_id, const char* status);

/**
 * End job analysis and log summary
 * 
 * @param sdk SDK handle
 * @param status Completion status
 * @return MONITORING_OK on success
 */
monitoring_error_t monitoring_end_job_analysis(monitoring_sdk_t* sdk, const char* status);

/**
 * Enable or disable automatic job analysis
 * 
 * @param sdk SDK handle
 * @param enabled 1 to enable, 0 to disable
 * @return MONITORING_OK on success
 */
monitoring_error_t monitoring_enable_job_analysis(monitoring_sdk_t* sdk, int enabled);

/**
 * Start a distributed trace span
 * 
 * @param sdk SDK handle
 * @param name Span name
 * @param trace_id Optional trace ID (can be NULL to generate)
 * @param span_id_out Output buffer for span ID (min MONITORING_MAX_ID_LEN)
 * @return MONITORING_OK on success
 */
monitoring_error_t monitoring_start_span(
    monitoring_sdk_t* sdk,
    const char* name,
    const char* trace_id,
    char* span_id_out
);

/**
 * End a distributed trace span
 * 
 * @param sdk SDK handle
 * @param span_id Span ID from start_span
 * @param status Span status (success, error, etc.)
 * @param tags_json Optional tags as JSON string (can be NULL)
 * @return MONITORING_OK on success
 */
monitoring_error_t monitoring_end_span(
    monitoring_sdk_t* sdk,
    const char* span_id,
    const char* status,
    const char* tags_json
);

/**
 * Set trace ID for correlation
 * 
 * @param sdk SDK handle
 * @param trace_id Trace ID
 * @return MONITORING_OK on success
 */
monitoring_error_t monitoring_set_trace_id(monitoring_sdk_t* sdk, const char* trace_id);

/**
 * Get SDK statistics
 * 
 * @param sdk SDK handle
 * @param messages_sent Output: number of messages sent
 * @param messages_buffered Output: number of messages buffered
 * @param messages_dropped Output: number of messages dropped
 * @return MONITORING_OK on success
 */
monitoring_error_t monitoring_get_stats(
    monitoring_sdk_t* sdk,
    uint64_t* messages_sent,
    uint64_t* messages_buffered,
    uint64_t* messages_dropped
);

/**
 * Get current connection state
 * 
 * @param sdk SDK handle
 * @return Current state
 */
monitoring_state_t monitoring_get_state(monitoring_sdk_t* sdk);

#ifdef __cplusplus
}
#endif

#endif /* MONITORING_SDK_H */

