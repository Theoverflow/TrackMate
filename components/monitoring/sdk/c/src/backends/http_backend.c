/**
 * @file http_backend.c
 * @brief HTTP Backend Implementation for Sidecar Communication
 */

#include "http_backend.h"
#include <curl/curl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ========================================================================== */
/* Internal Structures                                                        */
/* ========================================================================== */

typedef struct {
    char* url;
    float timeout;
    int max_retries;
    CURL* curl_handle;
    struct curl_slist* headers;
} http_backend_impl_t;

typedef struct {
    char* data;
    size_t size;
} http_response_t;

/* ========================================================================== */
/* Forward Declarations                                                       */
/* ========================================================================== */

static size_t write_callback(void* contents, size_t size, size_t nmemb, void* userp);
static char* event_to_json(const monitoring_event_t* event);

/* ========================================================================== */
/* Initialization & Cleanup                                                   */
/* ========================================================================== */

int http_backend_init(http_backend_t** backend, const monitoring_backend_config_t* config) {
    if (!backend || !config) {
        return -1;
    }
    
    http_backend_impl_t* impl = calloc(1, sizeof(http_backend_impl_t));
    if (!impl) {
        return -1;
    }
    
    /* Parse configuration */
    const char* url = "http://localhost:17000"; /* default */
    float timeout = 5.0f; /* default */
    int max_retries = 3; /* default */
    
    /* TODO: Parse from config */
    
    impl->url = strdup(url);
    impl->timeout = timeout;
    impl->max_retries = max_retries;
    
    /* Initialize CURL */
    curl_global_init(CURL_GLOBAL_DEFAULT);
    impl->curl_handle = curl_easy_init();
    
    if (!impl->curl_handle) {
        free(impl->url);
        free(impl);
        return -1;
    }
    
    /* Setup HTTP headers */
    impl->headers = NULL;
    impl->headers = curl_slist_append(impl->headers, "Content-Type: application/json");
    impl->headers = curl_slist_append(impl->headers, "Accept: application/json");
    
    *backend = (http_backend_t*)impl;
    return 0;
}

void http_backend_close(http_backend_t* backend) {
    if (!backend) return;
    
    http_backend_impl_t* impl = (http_backend_impl_t*)backend;
    
    if (impl->curl_handle) {
        curl_easy_cleanup(impl->curl_handle);
    }
    
    if (impl->headers) {
        curl_slist_free_all(impl->headers);
    }
    
    free(impl->url);
    free(impl);
    
    curl_global_cleanup();
}

/* ========================================================================== */
/* Event Sending                                                              */
/* ========================================================================== */

int http_backend_send_event(http_backend_t* backend, const monitoring_event_t* event) {
    if (!backend || !event) {
        return -1;
    }
    
    http_backend_impl_t* impl = (http_backend_impl_t*)backend;
    
    /* Convert event to JSON */
    char* json_data = event_to_json(event);
    if (!json_data) {
        return -1;
    }
    
    /* Prepare response buffer */
    http_response_t response = {0};
    
    /* Construct endpoint URL */
    char url[512];
    snprintf(url, sizeof(url), "%s/v1/ingest/events", impl->url);
    
    /* Configure CURL request */
    curl_easy_setopt(impl->curl_handle, CURLOPT_URL, url);
    curl_easy_setopt(impl->curl_handle, CURLOPT_POST, 1L);
    curl_easy_setopt(impl->curl_handle, CURLOPT_POSTFIELDS, json_data);
    curl_easy_setopt(impl->curl_handle, CURLOPT_POSTFIELDSIZE, strlen(json_data));
    curl_easy_setopt(impl->curl_handle, CURLOPT_HTTPHEADER, impl->headers);
    curl_easy_setopt(impl->curl_handle, CURLOPT_TIMEOUT_MS, (long)(impl->timeout * 1000));
    curl_easy_setopt(impl->curl_handle, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(impl->curl_handle, CURLOPT_WRITEDATA, (void*)&response);
    
    /* Perform request with retries */
    int retries = 0;
    CURLcode res = CURLE_OK;
    
    while (retries <= impl->max_retries) {
        res = curl_easy_perform(impl->curl_handle);
        
        if (res == CURLE_OK) {
            long http_code = 0;
            curl_easy_getinfo(impl->curl_handle, CURLINFO_RESPONSE_CODE, &http_code);
            
            if (http_code >= 200 && http_code < 300) {
                /* Success */
                free(json_data);
                free(response.data);
                return 0;
            } else if (http_code >= 400 && http_code < 500) {
                /* Client error, no retry */
                fprintf(stderr, "[http_backend] HTTP error %ld\n", http_code);
                break;
            }
            /* Server error, retry */
        }
        
        retries++;
        if (retries <= impl->max_retries) {
            /* Exponential backoff */
            usleep(100000 * (1 << retries)); /* 100ms, 200ms, 400ms... */
        }
    }
    
    /* Failed after retries */
    fprintf(stderr, "[http_backend] Failed to send event: %s\n", curl_easy_strerror(res));
    free(json_data);
    free(response.data);
    return -1;
}

int http_backend_send_batch(http_backend_t* backend, const monitoring_event_t* events, int count) {
    if (!backend || !events || count <= 0) {
        return -1;
    }
    
    /* TODO: Implement batch endpoint support */
    /* For now, send individually */
    for (int i = 0; i < count; i++) {
        if (http_backend_send_event(backend, &events[i]) != 0) {
            return -1;
        }
    }
    
    return 0;
}

int http_backend_health_check(http_backend_t* backend) {
    if (!backend) {
        return -1;
    }
    
    http_backend_impl_t* impl = (http_backend_impl_t*)backend;
    
    char url[512];
    snprintf(url, sizeof(url), "%s/health", impl->url);
    
    http_response_t response = {0};
    
    curl_easy_setopt(impl->curl_handle, CURLOPT_URL, url);
    curl_easy_setopt(impl->curl_handle, CURLOPT_HTTPGET, 1L);
    curl_easy_setopt(impl->curl_handle, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(impl->curl_handle, CURLOPT_WRITEDATA, (void*)&response);
    
    CURLcode res = curl_easy_perform(impl->curl_handle);
    
    if (res == CURLE_OK) {
        long http_code = 0;
        curl_easy_getinfo(impl->curl_handle, CURLINFO_RESPONSE_CODE, &http_code);
        free(response.data);
        return (http_code == 200) ? 0 : -1;
    }
    
    free(response.data);
    return -1;
}

/* ========================================================================== */
/* Helper Functions                                                           */
/* ========================================================================== */

static size_t write_callback(void* contents, size_t size, size_t nmemb, void* userp) {
    size_t realsize = size * nmemb;
    http_response_t* mem = (http_response_t*)userp;
    
    char* ptr = realloc(mem->data, mem->size + realsize + 1);
    if (!ptr) {
        fprintf(stderr, "[http_backend] Out of memory\n");
        return 0;
    }
    
    mem->data = ptr;
    memcpy(&(mem->data[mem->size]), contents, realsize);
    mem->size += realsize;
    mem->data[mem->size] = 0;
    
    return realsize;
}

static void json_escape_string(const char* str, char* out, size_t out_size) {
    size_t j = 0;
    for (size_t i = 0; str[i] && j < out_size - 2; i++) {
        if (str[i] == '"' || str[i] == '\\') {
            out[j++] = '\\';
        }
        out[j++] = str[i];
    }
    out[j] = '\0';
}

static char* event_to_json(const monitoring_event_t* event) {
    if (!event) return NULL;
    
    /* Estimate size */
    size_t size = 2048; /* base size */
    size += event->num_metrics * 128;
    size += event->num_metadata * 128;
    
    char* json = malloc(size);
    if (!json) return NULL;
    
    char escaped[512];
    
    /* Start JSON object */
    int offset = 0;
    offset += snprintf(json + offset, size - offset, "{");
    
    /* Required fields */
    json_escape_string(event->idempotency_key, escaped, sizeof(escaped));
    offset += snprintf(json + offset, size - offset, "\"idempotency_key\":\"%s\",", escaped);
    
    json_escape_string(event->site_id, escaped, sizeof(escaped));
    offset += snprintf(json + offset, size - offset, "\"site_id\":\"%s\",", escaped);
    
    json_escape_string(event->app_name, escaped, sizeof(escaped));
    offset += snprintf(json + offset, size - offset, "\"app_name\":\"%s\",", escaped);
    
    json_escape_string(event->app_version, escaped, sizeof(escaped));
    offset += snprintf(json + offset, size - offset, "\"app_version\":\"%s\",", escaped);
    
    offset += snprintf(json + offset, size - offset, "\"entity_type\":%d,", event->entity_type);
    
    json_escape_string(event->entity_id, escaped, sizeof(escaped));
    offset += snprintf(json + offset, size - offset, "\"entity_id\":\"%s\",", escaped);
    
    offset += snprintf(json + offset, size - offset, "\"event_kind\":%d,", event->event_kind);
    offset += snprintf(json + offset, size - offset, "\"timestamp\":%ld,", event->timestamp);
    
    json_escape_string(event->status, escaped, sizeof(escaped));
    offset += snprintf(json + offset, size - offset, "\"status\":\"%s\"", escaped);
    
    /* Optional: metrics */
    if (event->num_metrics > 0 && event->metric_keys && event->metric_values) {
        offset += snprintf(json + offset, size - offset, ",\"metrics\":{");
        for (int i = 0; i < event->num_metrics; i++) {
            json_escape_string(event->metric_keys[i], escaped, sizeof(escaped));
            offset += snprintf(json + offset, size - offset, "\"%s\":%.6f", escaped, event->metric_values[i]);
            if (i < event->num_metrics - 1) {
                offset += snprintf(json + offset, size - offset, ",");
            }
        }
        offset += snprintf(json + offset, size - offset, "}");
    }
    
    /* Optional: metadata */
    if (event->num_metadata > 0 && event->metadata_keys && event->metadata_values) {
        offset += snprintf(json + offset, size - offset, ",\"metadata\":{");
        for (int i = 0; i < event->num_metadata; i++) {
            char escaped_key[256], escaped_val[256];
            json_escape_string(event->metadata_keys[i], escaped_key, sizeof(escaped_key));
            json_escape_string(event->metadata_values[i], escaped_val, sizeof(escaped_val));
            offset += snprintf(json + offset, size - offset, "\"%s\":\"%s\"", escaped_key, escaped_val);
            if (i < event->num_metadata - 1) {
                offset += snprintf(json + offset, size - offset, ",");
            }
        }
        offset += snprintf(json + offset, size - offset, "}");
    }
    
    /* End JSON object */
    offset += snprintf(json + offset, size - offset, "}");
    
    return json;
}

