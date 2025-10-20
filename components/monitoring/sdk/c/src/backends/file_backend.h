/**
 * @file file_backend.h
 * @brief File System Backend Interface
 */

#ifndef FILE_BACKEND_H
#define FILE_BACKEND_H

#include "../monitoring.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Opaque handle for file backend */
typedef struct file_backend_s file_backend_t;

/**
 * Initialize file backend
 * @param backend Pointer to receive backend handle
 * @param config Backend configuration
 * @return 0 on success, -1 on error
 */
int file_backend_init(file_backend_t** backend, const monitoring_backend_config_t* config);

/**
 * Close and cleanup file backend
 * @param backend Backend handle
 */
void file_backend_close(file_backend_t* backend);

/**
 * Write a single event to file
 * @param backend Backend handle
 * @param event Event to write
 * @return 0 on success, -1 on error
 */
int file_backend_send_event(file_backend_t* backend, const monitoring_event_t* event);

/**
 * Write a batch of events to file
 * @param backend Backend handle
 * @param events Array of events
 * @param count Number of events
 * @return 0 on success, -1 on error
 */
int file_backend_send_batch(file_backend_t* backend, const monitoring_event_t* events, int count);

/**
 * Perform health check on file backend
 * @param backend Backend handle
 * @return 0 if healthy, -1 if unhealthy
 */
int file_backend_health_check(file_backend_t* backend);

#ifdef __cplusplus
}
#endif

#endif /* FILE_BACKEND_H */

