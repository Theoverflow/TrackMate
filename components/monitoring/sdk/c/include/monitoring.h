/**
 * @file monitoring.h
 * @brief Wafer Monitor C SDK - Public API
 * 
 * This is the main header file for the Wafer Monitor C SDK.
 * It provides a C interface for monitoring applications with support
 * for multiple backends (sidecar, filesystem, S3, ELK).
 * 
 * @version 0.3.0
 * @date 2025-10-20
 */

#ifndef MONITORING_H
#define MONITORING_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>
#include <time.h>

/* ========================================================================== */
/* Version Information                                                        */
/* ========================================================================== */

#define MONITORING_VERSION_MAJOR 0
#define MONITORING_VERSION_MINOR 3
#define MONITORING_VERSION_PATCH 0

/**
 * @brief Get SDK version string
 * @return Version string (e.g., "0.3.0")
 */
const char* monitoring_version(void);

/* ========================================================================== */
/* Error Codes                                                                */
/* ========================================================================== */

typedef enum {
    MONITORING_OK = 0,              /**< Success */
    MONITORING_ERROR = -1,          /**< Generic error */
    MONITORING_INVALID_PARAM = -2,  /**< Invalid parameter */
    MONITORING_NOT_INITIALIZED = -3, /**< SDK not initialized */
    MONITORING_ALREADY_INIT = -4,   /**< Already initialized */
    MONITORING_NO_MEMORY = -5,      /**< Out of memory */
    MONITORING_IO_ERROR = -6,       /**< I/O error */
    MONITORING_NETWORK_ERROR = -7,  /**< Network error */
    MONITORING_TIMEOUT = -8,        /**< Timeout */
    MONITORING_NOT_SUPPORTED = -9   /**< Operation not supported */
} monitoring_error_t;

/**
 * @brief Get error message for error code
 * @param error Error code
 * @return Error message string
 */
const char* monitoring_error_string(monitoring_error_t error);

/* ========================================================================== */
/* Configuration                                                              */
/* ========================================================================== */

/**
 * @brief SDK routing mode
 */
typedef enum {
    MONITORING_MODE_SIDECAR = 0,  /**< Route through sidecar agent */
    MONITORING_MODE_DIRECT = 1     /**< Direct to backends */
} monitoring_mode_t;

/**
 * @brief Backend types
 */
typedef enum {
    MONITORING_BACKEND_SIDECAR = 0,     /**< HTTP to sidecar */
    MONITORING_BACKEND_FILESYSTEM = 1,   /**< Write to filesystem */
    MONITORING_BACKEND_S3 = 2,          /**< Upload to S3 */
    MONITORING_BACKEND_ELK = 3,         /**< Index to Elasticsearch */
    MONITORING_BACKEND_WEBHOOK = 4      /**< POST to webhook */
} monitoring_backend_type_t;

/**
 * @brief Backend configuration
 */
typedef struct {
    monitoring_backend_type_t type;  /**< Backend type */
    bool enabled;                    /**< Is backend enabled */
    int priority;                    /**< Routing priority (lower = higher priority) */
    
    /* Backend-specific config (union for type safety) */
    union {
        struct {
            const char* url;         /**< Sidecar URL */
            int timeout_ms;          /**< Timeout in milliseconds */
            int retries;             /**< Number of retries */
        } sidecar;
        
        struct {
            const char* path;        /**< Directory path */
            const char* format;      /**< File format (jsonl, json) */
            int rotate_size_mb;      /**< File rotation size in MB */
        } filesystem;
        
        struct {
            const char* bucket;      /**< S3 bucket name */
            const char* region;      /**< AWS region */
            const char* prefix;      /**< Object key prefix */
            const char* access_key;  /**< AWS access key (optional) */
            const char* secret_key;  /**< AWS secret key (optional) */
        } s3;
        
        struct {
            const char* url;         /**< Elasticsearch URL */
            const char* index;       /**< Index name */
            const char* username;    /**< Username (optional) */
            const char* password;    /**< Password (optional) */
        } elk;
        
        struct {
            const char* url;         /**< Webhook URL */
            const char* method;      /**< HTTP method (POST, PUT) */
            int timeout_ms;          /**< Timeout in milliseconds */
        } webhook;
    } config;
} monitoring_backend_config_t;

/**
 * @brief SDK configuration
 */
typedef struct {
    monitoring_mode_t mode;                 /**< Routing mode */
    
    /* Application metadata */
    const char* app_name;                   /**< Application name */
    const char* app_version;                /**< Application version */
    const char* site_id;                    /**< Site identifier */
    const char* instance_id;                /**< Instance identifier (optional) */
    
    /* Backends (for direct mode) */
    monitoring_backend_config_t* backends;  /**< Array of backends */
    int num_backends;                       /**< Number of backends */
    
    /* Sidecar config (for sidecar mode) */
    const char* sidecar_url;                /**< Sidecar URL */
    int sidecar_timeout_ms;                 /**< Sidecar timeout */
    int sidecar_retries;                    /**< Sidecar retries */
} monitoring_config_t;

/**
 * @brief Initialize SDK with configuration
 * @param config Configuration structure
 * @return MONITORING_OK on success, error code otherwise
 */
monitoring_error_t monitoring_init(const monitoring_config_t* config);

/**
 * @brief Initialize SDK from JSON file
 * @param config_file Path to JSON configuration file
 * @return MONITORING_OK on success, error code otherwise
 */
monitoring_error_t monitoring_init_from_file(const char* config_file);

/**
 * @brief Shutdown SDK and cleanup resources
 * @return MONITORING_OK on success, error code otherwise
 */
monitoring_error_t monitoring_shutdown(void);

/**
 * @brief Check if SDK is initialized
 * @return true if initialized, false otherwise
 */
bool monitoring_is_initialized(void);

/* ========================================================================== */
/* Events                                                                     */
/* ========================================================================== */

/**
 * @brief Event kind
 */
typedef enum {
    MONITORING_EVENT_STARTED = 0,
    MONITORING_EVENT_PROGRESS = 1,
    MONITORING_EVENT_METRIC = 2,
    MONITORING_EVENT_FINISHED = 3,
    MONITORING_EVENT_ERROR = 4,
    MONITORING_EVENT_CANCELED = 5
} monitoring_event_kind_t;

/**
 * @brief Entity type
 */
typedef enum {
    MONITORING_ENTITY_JOB = 0,
    MONITORING_ENTITY_SUBJOB = 1
} monitoring_entity_type_t;

/**
 * @brief Event structure
 */
typedef struct {
    /* Identifiers */
    const char* idempotency_key;     /**< Unique event ID */
    const char* site_id;             /**< Site identifier */
    
    /* App info */
    const char* app_name;            /**< Application name */
    const char* app_version;         /**< Application version */
    
    /* Entity info */
    monitoring_entity_type_t entity_type;  /**< Entity type */
    const char* entity_id;           /**< Entity ID */
    const char* entity_sub_key;      /**< Entity sub-key (optional) */
    
    /* Event info */
    monitoring_event_kind_t event_kind;    /**< Event kind */
    time_t timestamp;                /**< Event timestamp (Unix epoch) */
    const char* status;              /**< Status string */
    
    /* Metrics (key-value pairs) */
    const char** metric_keys;        /**< Metric keys array */
    double* metric_values;           /**< Metric values array */
    int num_metrics;                 /**< Number of metrics */
    
    /* Metadata (key-value pairs) */
    const char** metadata_keys;      /**< Metadata keys array */
    const char** metadata_values;    /**< Metadata values array */
    int num_metadata;                /**< Number of metadata entries */
} monitoring_event_t;

/**
 * @brief Send a single event
 * @param event Event structure
 * @return MONITORING_OK on success, error code otherwise
 */
monitoring_error_t monitoring_send_event(const monitoring_event_t* event);

/**
 * @brief Send a batch of events
 * @param events Array of events
 * @param count Number of events
 * @return MONITORING_OK on success, error code otherwise
 */
monitoring_error_t monitoring_send_batch(const monitoring_event_t* events, int count);

/* ========================================================================== */
/* Context API (High-Level)                                                  */
/* ========================================================================== */

/**
 * @brief Monitoring context (opaque handle)
 */
typedef struct monitoring_context_s* monitoring_context_t;

/**
 * @brief Start a monitored context
 * @param name Context name (e.g., "process-wafer")
 * @param entity_id Entity ID (e.g., "job-123")
 * @return Context handle, or NULL on error
 */
monitoring_context_t monitoring_start(const char* name, const char* entity_id);

/**
 * @brief Report progress within a context
 * @param ctx Context handle
 * @param progress Progress percentage (0-100)
 * @param message Progress message (optional)
 * @return MONITORING_OK on success, error code otherwise
 */
monitoring_error_t monitoring_progress(monitoring_context_t ctx, int progress, const char* message);

/**
 * @brief Add a metric to context
 * @param ctx Context handle
 * @param key Metric key
 * @param value Metric value
 * @return MONITORING_OK on success, error code otherwise
 */
monitoring_error_t monitoring_add_metric(monitoring_context_t ctx, const char* key, double value);

/**
 * @brief Add metadata to context
 * @param ctx Context handle
 * @param key Metadata key
 * @param value Metadata value
 * @return MONITORING_OK on success, error code otherwise
 */
monitoring_error_t monitoring_add_metadata(monitoring_context_t ctx, const char* key, const char* value);

/**
 * @brief Finish context successfully
 * @param ctx Context handle
 * @return MONITORING_OK on success, error code otherwise
 */
monitoring_error_t monitoring_finish(monitoring_context_t ctx);

/**
 * @brief Finish context with error
 * @param ctx Context handle
 * @param error_message Error message
 * @return MONITORING_OK on success, error code otherwise
 */
monitoring_error_t monitoring_error(monitoring_context_t ctx, const char* error_message);

/**
 * @brief Cancel context
 * @param ctx Context handle
 * @return MONITORING_OK on success, error code otherwise
 */
monitoring_error_t monitoring_cancel(monitoring_context_t ctx);

/* ========================================================================== */
/* Utilities                                                                  */
/* ========================================================================== */

/**
 * @brief Generate a unique ID (UUID v4)
 * @param buffer Buffer to store ID (must be at least 37 bytes)
 * @return Pointer to buffer on success, NULL on error
 */
char* monitoring_generate_id(char* buffer);

/**
 * @brief Get current timestamp (Unix epoch)
 * @return Current timestamp in seconds since epoch
 */
time_t monitoring_timestamp(void);

/**
 * @brief Health check - test if backends are reachable
 * @return MONITORING_OK if healthy, error code otherwise
 */
monitoring_error_t monitoring_health_check(void);

#ifdef __cplusplus
}
#endif

#endif /* MONITORING_H */

