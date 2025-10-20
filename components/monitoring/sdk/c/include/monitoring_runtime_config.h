/**
 * @file monitoring_runtime_config.h
 * @brief Runtime Configuration and Hot-Reloading for Monitoring SDK
 * 
 * Enables dynamic configuration updates without application restart:
 * - Load config from JSON files at runtime
 * - Monitor config file for changes
 * - Hot-swap backends without dropping events
 * - Fault-tolerant config reloading
 */

#ifndef MONITORING_RUNTIME_CONFIG_H
#define MONITORING_RUNTIME_CONFIG_H

#include "monitoring.h"
#include <pthread.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Runtime configuration options
 */
typedef struct {
    /** Path to configuration file (JSON format) */
    const char* config_file_path;
    
    /** Check interval for config file changes (seconds) */
    int check_interval_seconds;
    
    /** Enable automatic config reloading */
    bool auto_reload;
    
    /** Callback for config reload events */
    void (*on_config_reload)(bool success, const char* message);
    
    /** Keep default config as fallback */
    bool use_fallback;
} monitoring_runtime_config_options_t;

/**
 * Initialize SDK with runtime configuration support
 * 
 * @param default_config Default configuration (used at startup and as fallback)
 * @param runtime_options Runtime configuration options
 * @return MONITORING_OK on success, error code otherwise
 * 
 * Example:
 * @code
 * monitoring_config_t default_config = {...};
 * monitoring_runtime_config_options_t runtime_opts = {
 *     .config_file_path = "/etc/monitoring/config.json",
 *     .check_interval_seconds = 30,
 *     .auto_reload = true,
 *     .on_config_reload = my_reload_callback,
 *     .use_fallback = true
 * };
 * monitoring_init_with_runtime_config(&default_config, &runtime_opts);
 * @endcode
 */
monitoring_error_t monitoring_init_with_runtime_config(
    const monitoring_config_t* default_config,
    const monitoring_runtime_config_options_t* runtime_options
);

/**
 * Manually trigger configuration reload from file
 * 
 * @return MONITORING_OK on success, error code otherwise
 */
monitoring_error_t monitoring_reload_config(void);

/**
 * Get current configuration file path
 * 
 * @return Path to configuration file, or NULL if not using runtime config
 */
const char* monitoring_get_config_file_path(void);

/**
 * Enable/disable automatic configuration reloading
 * 
 * @param enabled true to enable, false to disable
 * @return MONITORING_OK on success, error code otherwise
 */
monitoring_error_t monitoring_set_auto_reload(bool enabled);

/**
 * Get last configuration reload status
 * 
 * @param timestamp Pointer to receive timestamp of last reload (optional)
 * @param success Pointer to receive success status of last reload (optional)
 * @return MONITORING_OK on success
 */
monitoring_error_t monitoring_get_reload_status(
    time_t* timestamp,
    bool* success
);

/**
 * Configuration file format (JSON):
 * 
 * {
 *   "mode": "direct",
 *   "app": {
 *     "name": "my-app",
 *     "version": "1.0.0",
 *     "site_id": "fab1"
 *   },
 *   "backends": [
 *     {
 *       "type": "s3",
 *       "name": "s3-backup",
 *       "enabled": true,
 *       "priority": 1,
 *       "config": {
 *         "bucket_name": "monitoring-events",
 *         "region": "us-east-1"
 *       }
 *     },
 *     {
 *       "type": "kafka",
 *       "name": "kafka-enterprise",
 *       "enabled": true,
 *       "priority": 2,
 *       "config": {
 *         "brokers": "kafka1:9092,kafka2:9092",
 *         "topic": "monitoring-events"
 *       }
 *     },
 *     {
 *       "type": "sidecar",
 *       "name": "local-sidecar",
 *       "enabled": true,
 *       "priority": 3,
 *       "config": {
 *         "url": "http://localhost:17000"
 *       }
 *     }
 *   ]
 * }
 * 
 * To add new backend at runtime, update the file:
 * - Add backend to "backends" array
 * - SDK will detect change and reload
 * - New backend activated without restart
 * - Existing events continue to all backends
 */

#ifdef __cplusplus
}
#endif

#endif /* MONITORING_RUNTIME_CONFIG_H */

