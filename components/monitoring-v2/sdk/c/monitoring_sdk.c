/**
 * MonitoringSDK - C Implementation
 * Version: 2.0.0
 */

#include "monitoring_sdk.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <pthread.h>
#include <errno.h>

/* Message buffer entry */
typedef struct {
    char data[MONITORING_MAX_MESSAGE_LEN];
    size_t len;
} message_t;

/* SDK structure */
struct monitoring_sdk {
    char source[MONITORING_MAX_SOURCE_LEN];
    char tcp_host[MONITORING_MAX_HOST_LEN];
    int tcp_port;
    
    int sockfd;
    monitoring_state_t state;
    
    /* Buffer */
    message_t buffer[MONITORING_MAX_BUFFER_SIZE];
    size_t buffer_head;
    size_t buffer_tail;
    size_t buffer_count;
    
    /* Context */
    char trace_id[MONITORING_MAX_ID_LEN];
    char span_id[MONITORING_MAX_ID_LEN];
    
    /* Statistics */
    uint64_t messages_sent;
    uint64_t messages_buffered;
    uint64_t messages_dropped;
    uint64_t reconnect_count;
    uint64_t overflow_count;
    
    /* Reconnection */
    double reconnect_delay;
    time_t last_reconnect;
    
    /* Thread safety */
    pthread_mutex_t lock;
};

/* Helper functions */
static int64_t get_timestamp_ms(void);
static void generate_id(char* out, size_t len);
static int connect_socket(monitoring_sdk_t* sdk);
static int send_message(monitoring_sdk_t* sdk, const char* msg, size_t len);
static void buffer_message(monitoring_sdk_t* sdk, const char* msg, size_t len);
static void flush_buffer(monitoring_sdk_t* sdk);
static int format_message(char* out, size_t out_len, monitoring_sdk_t* sdk,
                         const char* type, const char* data_json);

/* Get current timestamp in milliseconds */
static int64_t get_timestamp_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    return (int64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

/* Generate random ID */
static void generate_id(char* out, size_t len) {
    static const char charset[] = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    static int seeded = 0;
    
    if (!seeded) {
        srand(time(NULL));
        seeded = 1;
    }
    
    for (size_t i = 0; i < len - 1; i++) {
        out[i] = charset[rand() % (sizeof(charset) - 1)];
    }
    out[len - 1] = '\0';
}

/* Connect to sidecar */
static int connect_socket(monitoring_sdk_t* sdk) {
    if (sdk->state == MONITORING_STATE_CONNECTED && sdk->sockfd >= 0) {
        return 0;  /* Already connected */
    }
    
    /* Throttle reconnection attempts */
    time_t now = time(NULL);
    if (now - sdk->last_reconnect < (time_t)sdk->reconnect_delay) {
        return -1;
    }
    sdk->last_reconnect = now;
    
    /* Create socket */
    sdk->sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sdk->sockfd < 0) {
        sdk->reconnect_delay = (sdk->reconnect_delay < 30) ? sdk->reconnect_delay * 2 : 30;
        return -1;
    }
    
    /* Connect */
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(sdk->tcp_port);
    
    if (inet_pton(AF_INET, sdk->tcp_host, &addr.sin_addr) <= 0) {
        close(sdk->sockfd);
        sdk->sockfd = -1;
        return -1;
    }
    
    if (connect(sdk->sockfd, (struct sockaddr*)&addr, sizeof(addr)) < 0) {
        close(sdk->sockfd);
        sdk->sockfd = -1;
        sdk->reconnect_delay = (sdk->reconnect_delay < 30) ? sdk->reconnect_delay * 2 : 30;
        return -1;
    }
    
    sdk->state = MONITORING_STATE_CONNECTED;
    sdk->reconnect_delay = 1.0;
    sdk->reconnect_count++;
    
    /* Flush buffer */
    flush_buffer(sdk);
    
    return 0;
}

/* Send message over socket */
static int send_message(monitoring_sdk_t* sdk, const char* msg, size_t len) {
    if (sdk->state != MONITORING_STATE_CONNECTED || sdk->sockfd < 0) {
        buffer_message(sdk, msg, len);
        connect_socket(sdk);
        return -1;
    }
    
    ssize_t sent = send(sdk->sockfd, msg, len, 0);
    if (sent < 0 || (size_t)sent != len) {
        sdk->state = MONITORING_STATE_DISCONNECTED;
        close(sdk->sockfd);
        sdk->sockfd = -1;
        
        buffer_message(sdk, msg, len);
        connect_socket(sdk);
        return -1;
    }
    
    sdk->messages_sent++;
    return 0;
}

/* Buffer message locally */
static void buffer_message(monitoring_sdk_t* sdk, const char* msg, size_t len) {
    if (sdk->buffer_count >= MONITORING_MAX_BUFFER_SIZE) {
        sdk->state = MONITORING_STATE_OVERFLOW;
        sdk->overflow_count++;
        sdk->messages_dropped++;
        return;
    }
    
    message_t* entry = &sdk->buffer[sdk->buffer_tail];
    size_t copy_len = (len < MONITORING_MAX_MESSAGE_LEN) ? len : MONITORING_MAX_MESSAGE_LEN - 1;
    memcpy(entry->data, msg, copy_len);
    entry->data[copy_len] = '\0';
    entry->len = copy_len;
    
    sdk->buffer_tail = (sdk->buffer_tail + 1) % MONITORING_MAX_BUFFER_SIZE;
    sdk->buffer_count++;
    sdk->messages_buffered++;
}

/* Flush buffered messages */
static void flush_buffer(monitoring_sdk_t* sdk) {
    while (sdk->buffer_count > 0 && sdk->state == MONITORING_STATE_CONNECTED) {
        message_t* entry = &sdk->buffer[sdk->buffer_head];
        
        if (send_message(sdk, entry->data, entry->len) < 0) {
            break;  /* Failed, keep remaining in buffer */
        }
        
        sdk->buffer_head = (sdk->buffer_head + 1) % MONITORING_MAX_BUFFER_SIZE;
        sdk->buffer_count--;
    }
    
    /* Reset overflow state if buffer cleared */
    if (sdk->buffer_count == 0 && sdk->state == MONITORING_STATE_OVERFLOW) {
        sdk->state = MONITORING_STATE_CONNECTED;
        sdk->overflow_count = 0;
    }
}

/* Format message as JSON */
static int format_message(char* out, size_t out_len, monitoring_sdk_t* sdk,
                         const char* type, const char* data_json) {
    int len = snprintf(out, out_len,
        "{\"v\":1,\"src\":\"%s\",\"ts\":%lld,\"type\":\"%s\"",
        sdk->source, (long long)get_timestamp_ms(), type);
    
    if (sdk->trace_id[0] != '\0') {
        len += snprintf(out + len, out_len - len, ",\"tid\":\"%s\"", sdk->trace_id);
    }
    
    if (sdk->span_id[0] != '\0') {
        len += snprintf(out + len, out_len - len, ",\"sid\":\"%s\"", sdk->span_id);
    }
    
    len += snprintf(out + len, out_len - len, ",\"data\":%s}\n", data_json);
    
    return len;
}

/* Public API */

monitoring_sdk_t* monitoring_sdk_create(const char* source, const char* tcp_host, int tcp_port) {
    if (!source) {
        return NULL;
    }
    
    monitoring_sdk_t* sdk = (monitoring_sdk_t*)calloc(1, sizeof(monitoring_sdk_t));
    if (!sdk) {
        return NULL;
    }
    
    strncpy(sdk->source, source, MONITORING_MAX_SOURCE_LEN - 1);
    strncpy(sdk->tcp_host, tcp_host ? tcp_host : "localhost", MONITORING_MAX_HOST_LEN - 1);
    sdk->tcp_port = tcp_port > 0 ? tcp_port : 17000;
    
    sdk->sockfd = -1;
    sdk->state = MONITORING_STATE_DISCONNECTED;
    sdk->reconnect_delay = 1.0;
    
    pthread_mutex_init(&sdk->lock, NULL);
    
    /* Initial connection attempt */
    connect_socket(sdk);
    
    return sdk;
}

void monitoring_sdk_destroy(monitoring_sdk_t* sdk) {
    if (!sdk) return;
    
    pthread_mutex_lock(&sdk->lock);
    
    /* Send goodbye */
    if (sdk->state == MONITORING_STATE_CONNECTED) {
        char msg[256];
        int len = format_message(msg, sizeof(msg), sdk, "goodbye", "{}");
        send(sdk->sockfd, msg, len, 0);
    }
    
    /* Close socket */
    if (sdk->sockfd >= 0) {
        close(sdk->sockfd);
    }
    
    pthread_mutex_unlock(&sdk->lock);
    pthread_mutex_destroy(&sdk->lock);
    
    free(sdk);
}

monitoring_error_t monitoring_log_event(monitoring_sdk_t* sdk, const char* level,
                                       const char* message, const char* context_json) {
    if (!sdk || !level || !message) {
        return MONITORING_ERROR_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&sdk->lock);
    
    char data[512];
    snprintf(data, sizeof(data), "{\"level\":\"%s\",\"msg\":\"%s\",\"ctx\":%s}",
             level, message, context_json ? context_json : "{}");
    
    char msg[MONITORING_MAX_MESSAGE_LEN];
    int len = format_message(msg, sizeof(msg), sdk, "event", data);
    
    int result = send_message(sdk, msg, len);
    
    pthread_mutex_unlock(&sdk->lock);
    
    return result == 0 ? MONITORING_OK : MONITORING_ERROR_SEND;
}

monitoring_error_t monitoring_log_metric(monitoring_sdk_t* sdk, const char* name,
                                        double value, const char* unit, const char* tags_json) {
    if (!sdk || !name) {
        return MONITORING_ERROR_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&sdk->lock);
    
    char data[512];
    snprintf(data, sizeof(data), "{\"name\":\"%s\",\"value\":%.2f,\"unit\":\"%s\",\"tags\":%s}",
             name, value, unit ? unit : "", tags_json ? tags_json : "{}");
    
    char msg[MONITORING_MAX_MESSAGE_LEN];
    int len = format_message(msg, sizeof(msg), sdk, "metric", data);
    
    int result = send_message(sdk, msg, len);
    
    pthread_mutex_unlock(&sdk->lock);
    
    return result == 0 ? MONITORING_OK : MONITORING_ERROR_SEND;
}

monitoring_error_t monitoring_log_progress(monitoring_sdk_t* sdk, const char* job_id,
                                          int percent, const char* status) {
    if (!sdk || !job_id) {
        return MONITORING_ERROR_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&sdk->lock);
    
    percent = (percent < 0) ? 0 : (percent > 100) ? 100 : percent;
    
    char data[256];
    snprintf(data, sizeof(data), "{\"job_id\":\"%s\",\"percent\":%d,\"status\":\"%s\"}",
             job_id, percent, status ? status : "running");
    
    char msg[MONITORING_MAX_MESSAGE_LEN];
    int len = format_message(msg, sizeof(msg), sdk, "progress", data);
    
    int result = send_message(sdk, msg, len);
    
    pthread_mutex_unlock(&sdk->lock);
    
    return result == 0 ? MONITORING_OK : MONITORING_ERROR_SEND;
}

/* Helper functions for auto-collecting metrics */
static double get_cpu_percent() {
    FILE* fp = fopen("/proc/stat", "r");
    if (!fp) return 0.0;
    
    unsigned long user, nice, system, idle;
    if (fscanf(fp, "cpu %lu %lu %lu %lu", &user, &nice, &system, &idle) == 4) {
        fclose(fp);
        unsigned long total = user + nice + system + idle;
        unsigned long used = user + nice + system;
        return total > 0 ? (double)used / total * 100.0 : 0.0;
    }
    
    fclose(fp);
    return 0.0;
}

static double get_memory_mb() {
    FILE* fp = fopen("/proc/meminfo", "r");
    if (!fp) return 0.0;
    
    char line[256];
    unsigned long mem_total = 0, mem_available = 0;
    
    while (fgets(line, sizeof(line), fp)) {
        if (sscanf(line, "MemTotal: %lu kB", &mem_total) == 1) continue;
        if (sscanf(line, "MemAvailable: %lu kB", &mem_available) == 1) break;
    }
    
    fclose(fp);
    
    if (mem_total > 0 && mem_available > 0) {
        unsigned long used_kb = mem_total - mem_available;
        return (double)used_kb / 1024.0;  // Convert to MB
    }
    
    return 0.0;
}

static double get_disk_io_mb() {
    FILE* fp = fopen("/proc/diskstats", "r");
    if (!fp) return 0.0;
    
    char line[256];
    unsigned long long total_sectors = 0;
    unsigned long read_sectors, write_sectors;
    
    while (fgets(line, sizeof(line), fp)) {
        // Format: major minor name ... sectors_read ... sectors_written ...
        if (sscanf(line, "%*d %*d %*s %*d %*d %lu %*d %*d %*d %lu",
                   &read_sectors, &write_sectors) == 2) {
            total_sectors += (read_sectors + write_sectors);
        }
    }
    
    fclose(fp);
    
    // Convert sectors to MB (sector = 512 bytes)
    return (double)(total_sectors * 512) / (1024.0 * 1024.0);
}

static double get_network_io_mb() {
    FILE* fp = fopen("/proc/net/dev", "r");
    if (!fp) return 0.0;
    
    char line[256];
    unsigned long long total_bytes = 0;
    unsigned long long rx_bytes, tx_bytes;
    
    // Skip header lines
    fgets(line, sizeof(line), fp);
    fgets(line, sizeof(line), fp);
    
    while (fgets(line, sizeof(line), fp)) {
        // Format: interface: rx_bytes ... tx_bytes ...
        if (sscanf(line, "%*s %llu %*d %*d %*d %*d %*d %*d %*d %llu",
                   &rx_bytes, &tx_bytes) == 2) {
            total_bytes += (rx_bytes + tx_bytes);
        }
    }
    
    fclose(fp);
    
    return (double)total_bytes / (1024.0 * 1024.0);  // Convert to MB
}

monitoring_error_t monitoring_log_resource(monitoring_sdk_t* sdk, double cpu_percent,
                                          double memory_mb, double disk_io_mb, double network_io_mb) {
    if (!sdk) {
        return MONITORING_ERROR_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&sdk->lock);
    
    // Auto-collect metrics if negative values provided
    if (cpu_percent < 0)    cpu_percent = get_cpu_percent();
    if (memory_mb < 0)      memory_mb = get_memory_mb();
    if (disk_io_mb < 0)     disk_io_mb = get_disk_io_mb();
    if (network_io_mb < 0)  network_io_mb = get_network_io_mb();
    
    char data[256];
    snprintf(data, sizeof(data), "{\"cpu\":%.2f,\"mem\":%.2f,\"disk\":%.2f,\"net\":%.2f,\"pid\":%d}",
             cpu_percent, memory_mb, disk_io_mb, network_io_mb, (int)getpid());
    
    char msg[MONITORING_MAX_MESSAGE_LEN];
    int len = format_message(msg, sizeof(msg), sdk, "resource", data);
    
    int result = send_message(sdk, msg, len);
    
    pthread_mutex_unlock(&sdk->lock);
    
    return result == 0 ? MONITORING_OK : MONITORING_ERROR_SEND;
}

monitoring_error_t monitoring_log_resource_auto(monitoring_sdk_t* sdk) {
    return monitoring_log_resource(sdk, -1, -1, -1, -1);
}

monitoring_error_t monitoring_start_span(monitoring_sdk_t* sdk, const char* name,
                                        const char* trace_id, char* span_id_out) {
    if (!sdk || !name || !span_id_out) {
        return MONITORING_ERROR_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&sdk->lock);
    
    /* Generate span ID */
    generate_id(span_id_out, MONITORING_MAX_ID_LEN);
    
    /* Set trace ID */
    if (trace_id) {
        strncpy(sdk->trace_id, trace_id, MONITORING_MAX_ID_LEN - 1);
    } else if (sdk->trace_id[0] == '\0') {
        generate_id(sdk->trace_id, MONITORING_MAX_ID_LEN);
    }
    
    /* Set current span */
    strncpy(sdk->span_id, span_id_out, MONITORING_MAX_ID_LEN - 1);
    
    /* Send span start */
    char data[256];
    snprintf(data, sizeof(data),
             "{\"name\":\"%s\",\"start\":%lld,\"end\":null,\"status\":\"started\",\"tags\":{}}",
             name, (long long)get_timestamp_ms());
    
    char msg[MONITORING_MAX_MESSAGE_LEN];
    int len = format_message(msg, sizeof(msg), sdk, "span", data);
    
    int result = send_message(sdk, msg, len);
    
    pthread_mutex_unlock(&sdk->lock);
    
    return result == 0 ? MONITORING_OK : MONITORING_ERROR_SEND;
}

monitoring_error_t monitoring_end_span(monitoring_sdk_t* sdk, const char* span_id,
                                      const char* status, const char* tags_json) {
    if (!sdk || !span_id) {
        return MONITORING_ERROR_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&sdk->lock);
    
    char data[256];
    snprintf(data, sizeof(data),
             "{\"name\":\"\",\"start\":0,\"end\":%lld,\"status\":\"%s\",\"tags\":%s}",
             (long long)get_timestamp_ms(), status ? status : "success",
             tags_json ? tags_json : "{}");
    
    char msg[MONITORING_MAX_MESSAGE_LEN];
    int len = format_message(msg, sizeof(msg), sdk, "span", data);
    
    int result = send_message(sdk, msg, len);
    
    /* Clear current span if it matches */
    if (strcmp(sdk->span_id, span_id) == 0) {
        sdk->span_id[0] = '\0';
    }
    
    pthread_mutex_unlock(&sdk->lock);
    
    return result == 0 ? MONITORING_OK : MONITORING_ERROR_SEND;
}

monitoring_error_t monitoring_set_trace_id(monitoring_sdk_t* sdk, const char* trace_id) {
    if (!sdk || !trace_id) {
        return MONITORING_ERROR_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&sdk->lock);
    strncpy(sdk->trace_id, trace_id, MONITORING_MAX_ID_LEN - 1);
    pthread_mutex_unlock(&sdk->lock);
    
    return MONITORING_OK;
}

monitoring_error_t monitoring_get_stats(monitoring_sdk_t* sdk, uint64_t* messages_sent,
                                       uint64_t* messages_buffered, uint64_t* messages_dropped) {
    if (!sdk) {
        return MONITORING_ERROR_INVALID_PARAM;
    }
    
    pthread_mutex_lock(&sdk->lock);
    
    if (messages_sent) *messages_sent = sdk->messages_sent;
    if (messages_buffered) *messages_buffered = sdk->messages_buffered;
    if (messages_dropped) *messages_dropped = sdk->messages_dropped;
    
    pthread_mutex_unlock(&sdk->lock);
    
    return MONITORING_OK;
}

monitoring_state_t monitoring_get_state(monitoring_sdk_t* sdk) {
    if (!sdk) {
        return MONITORING_STATE_DISCONNECTED;
    }
    
    pthread_mutex_lock(&sdk->lock);
    monitoring_state_t state = sdk->state;
    pthread_mutex_unlock(&sdk->lock);
    
    return state;
}

