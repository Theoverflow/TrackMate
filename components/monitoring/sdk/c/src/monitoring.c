/**
 * @file monitoring.c
 * @brief Wafer Monitor C SDK - Core Implementation
 */

#include "monitoring.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <pthread.h>

#ifdef __APPLE__
#include <uuid/uuid.h>
#else
#include <uuid.h>
#endif

/* ========================================================================== */
/* Internal Structures                                                        */
/* ========================================================================== */

typedef struct backend_s {
    monitoring_backend_type_t type;
    bool enabled;
    int priority;
    void* impl;  /* Backend-specific implementation */
} backend_t;

typedef struct {
    bool initialized;
    monitoring_config_t config;
    backend_t* backends;
    int num_backends;
    pthread_mutex_t lock;
} sdk_state_t;

typedef struct monitoring_context_s {
    char* name;
    char* entity_id;
    monitoring_entity_type_t entity_type;
    time_t start_time;
    
    /* Dynamic arrays */
    char** metric_keys;
    double* metric_values;
    int num_metrics;
    int metrics_capacity;
    
    char** metadata_keys;
    char** metadata_values;
    int num_metadata;
    int metadata_capacity;
} monitoring_context_s;

/* Global SDK state */
static sdk_state_t g_sdk = {
    .initialized = false,
    .backends = NULL,
    .num_backends = 0,
    .lock = PTHREAD_MUTEX_INITIALIZER
};

/* ========================================================================== */
/* Forward Declarations                                                       */
/* ========================================================================== */

static monitoring_error_t send_event_to_backends(const monitoring_event_t* event);
static void free_context_internal(monitoring_context_s* ctx);

/* ========================================================================== */
/* Version & Error Handling                                                   */
/* ========================================================================== */

const char* monitoring_version(void) {
    static char version[32];
    snprintf(version, sizeof(version), "%d.%d.%d",
             MONITORING_VERSION_MAJOR,
             MONITORING_VERSION_MINOR,
             MONITORING_VERSION_PATCH);
    return version;
}

const char* monitoring_error_string(monitoring_error_t error) {
    switch (error) {
        case MONITORING_OK: return "Success";
        case MONITORING_ERROR: return "Generic error";
        case MONITORING_INVALID_PARAM: return "Invalid parameter";
        case MONITORING_NOT_INITIALIZED: return "SDK not initialized";
        case MONITORING_ALREADY_INIT: return "Already initialized";
        case MONITORING_NO_MEMORY: return "Out of memory";
        case MONITORING_IO_ERROR: return "I/O error";
        case MONITORING_NETWORK_ERROR: return "Network error";
        case MONITORING_TIMEOUT: return "Timeout";
        case MONITORING_NOT_SUPPORTED: return "Operation not supported";
        default: return "Unknown error";
    }
}

/* ========================================================================== */
/* Configuration & Initialization                                             */
/* ========================================================================== */

monitoring_error_t monitoring_init(const monitoring_config_t* config) {
    if (!config) {
        return MONITORING_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&g_sdk.lock);
    
    if (g_sdk.initialized) {
        pthread_mutex_unlock(&g_sdk.lock);
        return MONITORING_ALREADY_INIT;
    }
    
    /* Copy configuration */
    memcpy(&g_sdk.config, config, sizeof(monitoring_config_t));
    
    /* Initialize backends based on mode */
    if (config->mode == MONITORING_MODE_SIDECAR) {
        /* Sidecar mode: single backend */
        g_sdk.num_backends = 1;
        g_sdk.backends = calloc(1, sizeof(backend_t));
        if (!g_sdk.backends) {
            pthread_mutex_unlock(&g_sdk.lock);
            return MONITORING_NO_MEMORY;
        }
        
        g_sdk.backends[0].type = MONITORING_BACKEND_SIDECAR;
        g_sdk.backends[0].enabled = true;
        g_sdk.backends[0].priority = 1;
        /* TODO: Initialize sidecar backend implementation */
        
    } else {
        /* Direct mode: multiple backends */
        if (config->num_backends > 0) {
            g_sdk.num_backends = config->num_backends;
            g_sdk.backends = calloc(config->num_backends, sizeof(backend_t));
            if (!g_sdk.backends) {
                pthread_mutex_unlock(&g_sdk.lock);
                return MONITORING_NO_MEMORY;
            }
            
            for (int i = 0; i < config->num_backends; i++) {
                g_sdk.backends[i].type = config->backends[i].type;
                g_sdk.backends[i].enabled = config->backends[i].enabled;
                g_sdk.backends[i].priority = config->backends[i].priority;
                /* TODO: Initialize backend implementations */
            }
        }
    }
    
    g_sdk.initialized = true;
    pthread_mutex_unlock(&g_sdk.lock);
    
    return MONITORING_OK;
}

monitoring_error_t monitoring_init_from_file(const char* config_file) {
    if (!config_file) {
        return MONITORING_INVALID_PARAM;
    }
    
    /* TODO: Parse JSON configuration file */
    return MONITORING_NOT_SUPPORTED;
}

monitoring_error_t monitoring_shutdown(void) {
    pthread_mutex_lock(&g_sdk.lock);
    
    if (!g_sdk.initialized) {
        pthread_mutex_unlock(&g_sdk.lock);
        return MONITORING_NOT_INITIALIZED;
    }
    
    /* Cleanup backends */
    if (g_sdk.backends) {
        /* TODO: Close backend implementations */
        free(g_sdk.backends);
        g_sdk.backends = NULL;
    }
    
    g_sdk.num_backends = 0;
    g_sdk.initialized = false;
    
    pthread_mutex_unlock(&g_sdk.lock);
    
    return MONITORING_OK;
}

bool monitoring_is_initialized(void) {
    bool result;
    pthread_mutex_lock(&g_sdk.lock);
    result = g_sdk.initialized;
    pthread_mutex_unlock(&g_sdk.lock);
    return result;
}

/* ========================================================================== */
/* Event API                                                                  */
/* ========================================================================== */

monitoring_error_t monitoring_send_event(const monitoring_event_t* event) {
    if (!event) {
        return MONITORING_INVALID_PARAM;
    }
    
    if (!monitoring_is_initialized()) {
        return MONITORING_NOT_INITIALIZED;
    }
    
    return send_event_to_backends(event);
}

monitoring_error_t monitoring_send_batch(const monitoring_event_t* events, int count) {
    if (!events || count <= 0) {
        return MONITORING_INVALID_PARAM;
    }
    
    if (!monitoring_is_initialized()) {
        return MONITORING_NOT_INITIALIZED;
    }
    
    /* Send each event individually for now */
    /* TODO: Implement true batch support */
    for (int i = 0; i < count; i++) {
        monitoring_error_t err = send_event_to_backends(&events[i]);
        if (err != MONITORING_OK) {
            return err;
        }
    }
    
    return MONITORING_OK;
}

static monitoring_error_t send_event_to_backends(const monitoring_event_t* event) {
    /* TODO: Send to all enabled backends */
    /* For now, just log */
    fprintf(stderr, "[monitoring] Event: %s (kind=%d)\n", 
            event->idempotency_key, event->event_kind);
    return MONITORING_OK;
}

/* ========================================================================== */
/* Context API                                                                */
/* ========================================================================== */

monitoring_context_t monitoring_start(const char* name, const char* entity_id) {
    if (!name || !entity_id) {
        return NULL;
    }
    
    if (!monitoring_is_initialized()) {
        return NULL;
    }
    
    monitoring_context_s* ctx = calloc(1, sizeof(monitoring_context_s));
    if (!ctx) {
        return NULL;
    }
    
    ctx->name = strdup(name);
    ctx->entity_id = strdup(entity_id);
    ctx->entity_type = MONITORING_ENTITY_JOB;
    ctx->start_time = time(NULL);
    
    /* Allocate initial capacity for metrics/metadata */
    ctx->metrics_capacity = 16;
    ctx->metric_keys = calloc(ctx->metrics_capacity, sizeof(char*));
    ctx->metric_values = calloc(ctx->metrics_capacity, sizeof(double));
    
    ctx->metadata_capacity = 16;
    ctx->metadata_keys = calloc(ctx->metadata_capacity, sizeof(char*));
    ctx->metadata_values = calloc(ctx->metadata_capacity, sizeof(char*));
    
    /* Send started event */
    char event_id[64];
    snprintf(event_id, sizeof(event_id), "%s-start-%ld", entity_id, ctx->start_time);
    
    monitoring_event_t event = {
        .idempotency_key = event_id,
        .site_id = g_sdk.config.site_id,
        .app_name = g_sdk.config.app_name,
        .app_version = g_sdk.config.app_version,
        .entity_type = ctx->entity_type,
        .entity_id = entity_id,
        .event_kind = MONITORING_EVENT_STARTED,
        .timestamp = ctx->start_time,
        .status = "started",
        .num_metrics = 0,
        .num_metadata = 0
    };
    
    monitoring_send_event(&event);
    
    return ctx;
}

monitoring_error_t monitoring_progress(monitoring_context_t ctx, int progress, const char* message) {
    if (!ctx) {
        return MONITORING_INVALID_PARAM;
    }
    
    monitoring_context_s* context = (monitoring_context_s*)ctx;
    
    char event_id[64];
    snprintf(event_id, sizeof(event_id), "%s-progress-%ld", 
             context->entity_id, time(NULL));
    
    /* Create progress metric */
    const char* keys[] = {"progress"};
    double values[] = {(double)progress};
    
    monitoring_event_t event = {
        .idempotency_key = event_id,
        .site_id = g_sdk.config.site_id,
        .app_name = g_sdk.config.app_name,
        .app_version = g_sdk.config.app_version,
        .entity_type = context->entity_type,
        .entity_id = context->entity_id,
        .event_kind = MONITORING_EVENT_PROGRESS,
        .timestamp = time(NULL),
        .status = message ? message : "in_progress",
        .metric_keys = keys,
        .metric_values = values,
        .num_metrics = 1,
        .num_metadata = 0
    };
    
    return monitoring_send_event(&event);
}

monitoring_error_t monitoring_add_metric(monitoring_context_t ctx, const char* key, double value) {
    if (!ctx || !key) {
        return MONITORING_INVALID_PARAM;
    }
    
    monitoring_context_s* context = (monitoring_context_s*)ctx;
    
    /* Grow array if needed */
    if (context->num_metrics >= context->metrics_capacity) {
        context->metrics_capacity *= 2;
        context->metric_keys = realloc(context->metric_keys, 
                                      context->metrics_capacity * sizeof(char*));
        context->metric_values = realloc(context->metric_values,
                                        context->metrics_capacity * sizeof(double));
    }
    
    context->metric_keys[context->num_metrics] = strdup(key);
    context->metric_values[context->num_metrics] = value;
    context->num_metrics++;
    
    return MONITORING_OK;
}

monitoring_error_t monitoring_add_metadata(monitoring_context_t ctx, const char* key, const char* value) {
    if (!ctx || !key || !value) {
        return MONITORING_INVALID_PARAM;
    }
    
    monitoring_context_s* context = (monitoring_context_s*)ctx;
    
    /* Grow array if needed */
    if (context->num_metadata >= context->metadata_capacity) {
        context->metadata_capacity *= 2;
        context->metadata_keys = realloc(context->metadata_keys,
                                        context->metadata_capacity * sizeof(char*));
        context->metadata_values = realloc(context->metadata_values,
                                          context->metadata_capacity * sizeof(char*));
    }
    
    context->metadata_keys[context->num_metadata] = strdup(key);
    context->metadata_values[context->num_metadata] = strdup(value);
    context->num_metadata++;
    
    return MONITORING_OK;
}

monitoring_error_t monitoring_finish(monitoring_context_t ctx) {
    if (!ctx) {
        return MONITORING_INVALID_PARAM;
    }
    
    monitoring_context_s* context = (monitoring_context_s*)ctx;
    
    char event_id[64];
    time_t now = time(NULL);
    snprintf(event_id, sizeof(event_id), "%s-finish-%ld", context->entity_id, now);
    
    /* Add duration metric */
    double duration = difftime(now, context->start_time);
    monitoring_add_metric(ctx, "duration_seconds", duration);
    
    monitoring_event_t event = {
        .idempotency_key = event_id,
        .site_id = g_sdk.config.site_id,
        .app_name = g_sdk.config.app_name,
        .app_version = g_sdk.config.app_version,
        .entity_type = context->entity_type,
        .entity_id = context->entity_id,
        .event_kind = MONITORING_EVENT_FINISHED,
        .timestamp = now,
        .status = "success",
        .metric_keys = (const char**)context->metric_keys,
        .metric_values = context->metric_values,
        .num_metrics = context->num_metrics,
        .metadata_keys = (const char**)context->metadata_keys,
        .metadata_values = (const char**)context->metadata_values,
        .num_metadata = context->num_metadata
    };
    
    monitoring_error_t err = monitoring_send_event(&event);
    free_context_internal(context);
    
    return err;
}

monitoring_error_t monitoring_error(monitoring_context_t ctx, const char* error_message) {
    if (!ctx) {
        return MONITORING_INVALID_PARAM;
    }
    
    monitoring_context_s* context = (monitoring_context_s*)ctx;
    
    /* Add error as metadata */
    if (error_message) {
        monitoring_add_metadata(ctx, "error", error_message);
    }
    
    char event_id[64];
    snprintf(event_id, sizeof(event_id), "%s-error-%ld", 
             context->entity_id, time(NULL));
    
    monitoring_event_t event = {
        .idempotency_key = event_id,
        .site_id = g_sdk.config.site_id,
        .app_name = g_sdk.config.app_name,
        .app_version = g_sdk.config.app_version,
        .entity_type = context->entity_type,
        .entity_id = context->entity_id,
        .event_kind = MONITORING_EVENT_ERROR,
        .timestamp = time(NULL),
        .status = "error",
        .metric_keys = (const char**)context->metric_keys,
        .metric_values = context->metric_values,
        .num_metrics = context->num_metrics,
        .metadata_keys = (const char**)context->metadata_keys,
        .metadata_values = (const char**)context->metadata_values,
        .num_metadata = context->num_metadata
    };
    
    monitoring_error_t err = monitoring_send_event(&event);
    free_context_internal(context);
    
    return err;
}

monitoring_error_t monitoring_cancel(monitoring_context_t ctx) {
    if (!ctx) {
        return MONITORING_INVALID_PARAM;
    }
    
    monitoring_context_s* context = (monitoring_context_s*)ctx;
    
    char event_id[64];
    snprintf(event_id, sizeof(event_id), "%s-cancel-%ld",
             context->entity_id, time(NULL));
    
    monitoring_event_t event = {
        .idempotency_key = event_id,
        .site_id = g_sdk.config.site_id,
        .app_name = g_sdk.config.app_name,
        .app_version = g_sdk.config.app_version,
        .entity_type = context->entity_type,
        .entity_id = context->entity_id,
        .event_kind = MONITORING_EVENT_CANCELED,
        .timestamp = time(NULL),
        .status = "canceled",
        .num_metrics = 0,
        .num_metadata = 0
    };
    
    monitoring_error_t err = monitoring_send_event(&event);
    free_context_internal(context);
    
    return err;
}

static void free_context_internal(monitoring_context_s* ctx) {
    if (!ctx) return;
    
    free(ctx->name);
    free(ctx->entity_id);
    
    /* Free metrics */
    for (int i = 0; i < ctx->num_metrics; i++) {
        free(ctx->metric_keys[i]);
    }
    free(ctx->metric_keys);
    free(ctx->metric_values);
    
    /* Free metadata */
    for (int i = 0; i < ctx->num_metadata; i++) {
        free(ctx->metadata_keys[i]);
        free(ctx->metadata_values[i]);
    }
    free(ctx->metadata_keys);
    free(ctx->metadata_values);
    
    free(ctx);
}

/* ========================================================================== */
/* Utilities                                                                  */
/* ========================================================================== */

char* monitoring_generate_id(char* buffer) {
    if (!buffer) {
        return NULL;
    }
    
#ifdef __APPLE__
    uuid_t uuid;
    uuid_generate(uuid);
    uuid_unparse(uuid, buffer);
#else
    /* Fallback: use timestamp + random */
    snprintf(buffer, 37, "%08x-%04x-%04x-%04x-%012lx",
             (unsigned int)time(NULL),
             rand() % 0xFFFF,
             rand() % 0xFFFF,
             rand() % 0xFFFF,
             (unsigned long)rand() % 0xFFFFFFFFFFFF);
#endif
    
    return buffer;
}

time_t monitoring_timestamp(void) {
    return time(NULL);
}

monitoring_error_t monitoring_health_check(void) {
    if (!monitoring_is_initialized()) {
        return MONITORING_NOT_INITIALIZED;
    }
    
    /* TODO: Check backend health */
    return MONITORING_OK;
}

