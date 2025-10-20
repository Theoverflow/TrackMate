/**
 * @file file_backend.c
 * @brief File System Backend Implementation
 */

#include "file_backend.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/stat.h>
#include <pthread.h>

/* ========================================================================== */
/* Internal Structures                                                        */
/* ========================================================================== */

typedef struct {
    char* output_dir;
    char* filename_prefix;
    size_t max_file_size;
    FILE* current_file;
    size_t current_size;
    pthread_mutex_t lock;
} file_backend_impl_t;

/* ========================================================================== */
/* Forward Declarations                                                       */
/* ========================================================================== */

static int ensure_directory(const char* path);
static int rotate_file(file_backend_impl_t* impl);
static char* event_to_json_line(const monitoring_event_t* event);

/* ========================================================================== */
/* Initialization & Cleanup                                                   */
/* ========================================================================== */

int file_backend_init(file_backend_t** backend, const monitoring_backend_config_t* config) {
    if (!backend || !config) {
        return -1;
    }
    
    file_backend_impl_t* impl = calloc(1, sizeof(file_backend_impl_t));
    if (!impl) {
        return -1;
    }
    
    /* Parse configuration */
    const char* output_dir = "./monitoring_events"; /* default */
    const char* prefix = "events"; /* default */
    size_t max_size = 100 * 1024 * 1024; /* 100MB default */
    
    /* TODO: Parse from config */
    
    impl->output_dir = strdup(output_dir);
    impl->filename_prefix = strdup(prefix);
    impl->max_file_size = max_size;
    impl->current_file = NULL;
    impl->current_size = 0;
    
    pthread_mutex_init(&impl->lock, NULL);
    
    /* Ensure output directory exists */
    if (ensure_directory(impl->output_dir) != 0) {
        free(impl->output_dir);
        free(impl->filename_prefix);
        pthread_mutex_destroy(&impl->lock);
        free(impl);
        return -1;
    }
    
    *backend = (file_backend_t*)impl;
    return 0;
}

void file_backend_close(file_backend_t* backend) {
    if (!backend) return;
    
    file_backend_impl_t* impl = (file_backend_impl_t*)backend;
    
    pthread_mutex_lock(&impl->lock);
    
    if (impl->current_file) {
        fclose(impl->current_file);
    }
    
    free(impl->output_dir);
    free(impl->filename_prefix);
    
    pthread_mutex_unlock(&impl->lock);
    pthread_mutex_destroy(&impl->lock);
    
    free(impl);
}

/* ========================================================================== */
/* Event Writing                                                              */
/* ========================================================================== */

int file_backend_send_event(file_backend_t* backend, const monitoring_event_t* event) {
    if (!backend || !event) {
        return -1;
    }
    
    file_backend_impl_t* impl = (file_backend_impl_t*)backend;
    
    /* Convert event to JSON line */
    char* json_line = event_to_json_line(event);
    if (!json_line) {
        return -1;
    }
    
    size_t line_size = strlen(json_line);
    
    pthread_mutex_lock(&impl->lock);
    
    /* Check if rotation is needed */
    if (!impl->current_file || impl->current_size + line_size > impl->max_file_size) {
        if (rotate_file(impl) != 0) {
            pthread_mutex_unlock(&impl->lock);
            free(json_line);
            return -1;
        }
    }
    
    /* Write to file */
    size_t written = fwrite(json_line, 1, line_size, impl->current_file);
    if (written != line_size) {
        pthread_mutex_unlock(&impl->lock);
        free(json_line);
        return -1;
    }
    
    fflush(impl->current_file);
    impl->current_size += line_size;
    
    pthread_mutex_unlock(&impl->lock);
    free(json_line);
    
    return 0;
}

int file_backend_send_batch(file_backend_t* backend, const monitoring_event_t* events, int count) {
    if (!backend || !events || count <= 0) {
        return -1;
    }
    
    /* Send events individually */
    for (int i = 0; i < count; i++) {
        if (file_backend_send_event(backend, &events[i]) != 0) {
            return -1;
        }
    }
    
    return 0;
}

int file_backend_health_check(file_backend_t* backend) {
    if (!backend) {
        return -1;
    }
    
    file_backend_impl_t* impl = (file_backend_impl_t*)backend;
    
    /* Check if output directory is writable */
    char test_file[512];
    snprintf(test_file, sizeof(test_file), "%s/.health_check", impl->output_dir);
    
    FILE* fp = fopen(test_file, "w");
    if (!fp) {
        return -1;
    }
    
    fclose(fp);
    remove(test_file);
    
    return 0;
}

/* ========================================================================== */
/* Helper Functions                                                           */
/* ========================================================================== */

static int ensure_directory(const char* path) {
    struct stat st = {0};
    
    if (stat(path, &st) == -1) {
#ifdef _WIN32
        return mkdir(path);
#else
        return mkdir(path, 0755);
#endif
    }
    
    return 0;
}

static int rotate_file(file_backend_impl_t* impl) {
    /* Close current file if open */
    if (impl->current_file) {
        fclose(impl->current_file);
        impl->current_file = NULL;
    }
    
    /* Generate new filename with timestamp */
    time_t now = time(NULL);
    char filename[512];
    snprintf(filename, sizeof(filename), "%s/%s_%ld_%d.jsonl",
             impl->output_dir, impl->filename_prefix, now, getpid());
    
    /* Open new file */
    impl->current_file = fopen(filename, "a");
    if (!impl->current_file) {
        fprintf(stderr, "[file_backend] Failed to open file: %s\n", filename);
        return -1;
    }
    
    impl->current_size = 0;
    return 0;
}

static char* event_to_json_line(const monitoring_event_t* event) {
    if (!event) return NULL;
    
    /* Estimate size */
    size_t size = 2048;
    size += event->num_metrics * 128;
    size += event->num_metadata * 128;
    
    char* json = malloc(size);
    if (!json) return NULL;
    
    /* Build JSON object (simplified, no escaping for now) */
    int offset = 0;
    offset += snprintf(json + offset, size - offset,
                      "{\"idempotency_key\":\"%s\","
                      "\"site_id\":\"%s\","
                      "\"app_name\":\"%s\","
                      "\"app_version\":\"%s\","
                      "\"entity_type\":%d,"
                      "\"entity_id\":\"%s\","
                      "\"event_kind\":%d,"
                      "\"timestamp\":%ld,"
                      "\"status\":\"%s\"",
                      event->idempotency_key,
                      event->site_id,
                      event->app_name,
                      event->app_version,
                      event->entity_type,
                      event->entity_id,
                      event->event_kind,
                      event->timestamp,
                      event->status);
    
    /* Add metrics */
    if (event->num_metrics > 0) {
        offset += snprintf(json + offset, size - offset, ",\"metrics\":{");
        for (int i = 0; i < event->num_metrics; i++) {
            offset += snprintf(json + offset, size - offset, "\"%s\":%.6f",
                             event->metric_keys[i], event->metric_values[i]);
            if (i < event->num_metrics - 1) {
                offset += snprintf(json + offset, size - offset, ",");
            }
        }
        offset += snprintf(json + offset, size - offset, "}");
    }
    
    /* Add metadata */
    if (event->num_metadata > 0) {
        offset += snprintf(json + offset, size - offset, ",\"metadata\":{");
        for (int i = 0; i < event->num_metadata; i++) {
            offset += snprintf(json + offset, size - offset, "\"%s\":\"%s\"",
                             event->metadata_keys[i], event->metadata_values[i]);
            if (i < event->num_metadata - 1) {
                offset += snprintf(json + offset, size - offset, ",");
            }
        }
        offset += snprintf(json + offset, size - offset, "}");
    }
    
    /* End JSON and add newline */
    offset += snprintf(json + offset, size - offset, "}\n");
    
    return json;
}

