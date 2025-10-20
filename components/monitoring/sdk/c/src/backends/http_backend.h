/**
 * @file http_backend.h
 * @brief HTTP Backend Interface for Sidecar Communication
 */

#ifndef HTTP_BACKEND_H
#define HTTP_BACKEND_H

#include "../monitoring.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Opaque handle for HTTP backend */
typedef struct http_backend_s http_backend_t;

/**
 * Initialize HTTP backend
 * @param backend Pointer to receive backend handle
 * @param config Backend configuration
 * @return 0 on success, -1 on error
 */
int http_backend_init(http_backend_t** backend, const monitoring_backend_config_t* config);

/**
 * Close and cleanup HTTP backend
 * @param backend Backend handle
 */
void http_backend_close(http_backend_t* backend);

/**
 * Send a single event via HTTP
 * @param backend Backend handle
 * @param event Event to send
 * @return 0 on success, -1 on error
 */
int http_backend_send_event(http_backend_t* backend, const monitoring_event_t* event);

/**
 * Send a batch of events via HTTP
 * @param backend Backend handle
 * @param events Array of events
 * @param count Number of events
 * @return 0 on success, -1 on error
 */
int http_backend_send_batch(http_backend_t* backend, const monitoring_event_t* events, int count);

/**
 * Perform health check on HTTP backend
 * @param backend Backend handle
 * @return 0 if healthy, -1 if unhealthy
 */
int http_backend_health_check(http_backend_t* backend);

#ifdef __cplusplus
}
#endif

#endif /* HTTP_BACKEND_H */

