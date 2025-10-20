/**
 * @file runtime_config.c
 * @brief Runtime Configuration Implementation
 */

#include "monitoring_runtime_config.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include <pthread.h>

/* JSON parsing - using a simple parser for demonstration */
/* In production, use a library like cJSON or json-c */

typedef struct {
    monitoring_runtime_config_options_t options;
    monitoring_config_t default_config;
    monitoring_config_t current_config;
    
    pthread_t watcher_thread;
    bool watcher_running;
    pthread_mutex_t config_lock;
    
    time_t last_modified;
    time_t last_reload_time;
    bool last_reload_success;
    
    bool initialized;
} runtime_config_state_t;

static runtime_config_state_t g_runtime_state = {
    .initialized = false,
    .watcher_running = false,
    .last_modified = 0,
    .last_reload_time = 0,
    .last_reload_success = false
};

/* Forward declarations */
static void* config_watcher_thread(void* arg);
static monitoring_error_t load_config_from_file(const char* path, monitoring_config_t* config);
static time_t get_file_mtime(const char* path);
static monitoring_error_t apply_new_config(const monitoring_config_t* new_config);

monitoring_error_t monitoring_init_with_runtime_config(
    const monitoring_config_t* default_config,
    const monitoring_runtime_config_options_t* runtime_options)
{
    if (!default_config || !runtime_options) {
        return MONITORING_INVALID_PARAM;
    }
    
    if (g_runtime_state.initialized) {
        return MONITORING_ALREADY_INIT;
    }
    
    /* Store default configuration */
    memcpy(&g_runtime_state.default_config, default_config, sizeof(monitoring_config_t));
    memcpy(&g_runtime_state.options, runtime_options, sizeof(monitoring_runtime_config_options_t));
    
    pthread_mutex_init(&g_runtime_state.config_lock, NULL);
    
    /* Try to load config from file */
    monitoring_config_t loaded_config;
    monitoring_error_t err = load_config_from_file(
        runtime_options->config_file_path,
        &loaded_config
    );
    
    if (err == MONITORING_OK) {
        /* Use loaded config */
        memcpy(&g_runtime_state.current_config, &loaded_config, sizeof(monitoring_config_t));
        fprintf(stderr, "[runtime_config] Loaded config from: %s\n", 
                runtime_options->config_file_path);
    } else if (runtime_options->use_fallback) {
        /* Use default config as fallback */
        memcpy(&g_runtime_state.current_config, default_config, sizeof(monitoring_config_t));
        fprintf(stderr, "[runtime_config] Using default config (file load failed: %s)\n",
                monitoring_error_string(err));
    } else {
        return err;
    }
    
    /* Initialize SDK with current config */
    err = monitoring_init(&g_runtime_state.current_config);
    if (err != MONITORING_OK) {
        pthread_mutex_destroy(&g_runtime_state.config_lock);
        return err;
    }
    
    g_runtime_state.last_modified = get_file_mtime(runtime_options->config_file_path);
    g_runtime_state.initialized = true;
    
    /* Start config watcher thread if auto-reload enabled */
    if (runtime_options->auto_reload) {
        g_runtime_state.watcher_running = true;
        pthread_create(&g_runtime_state.watcher_thread, NULL, 
                      config_watcher_thread, NULL);
    }
    
    return MONITORING_OK;
}

monitoring_error_t monitoring_reload_config(void)
{
    if (!g_runtime_state.initialized) {
        return MONITORING_NOT_INITIALIZED;
    }
    
    pthread_mutex_lock(&g_runtime_state.config_lock);
    
    monitoring_config_t new_config;
    monitoring_error_t err = load_config_from_file(
        g_runtime_state.options.config_file_path,
        &new_config
    );
    
    if (err == MONITORING_OK) {
        /* Apply new configuration */
        err = apply_new_config(&new_config);
        
        if (err == MONITORING_OK) {
            memcpy(&g_runtime_state.current_config, &new_config, 
                   sizeof(monitoring_config_t));
            g_runtime_state.last_reload_time = time(NULL);
            g_runtime_state.last_reload_success = true;
            
            fprintf(stderr, "[runtime_config] Configuration reloaded successfully\n");
            
            /* Trigger callback */
            if (g_runtime_state.options.on_config_reload) {
                g_runtime_state.options.on_config_reload(true, "Configuration reloaded");
            }
        } else {
            g_runtime_state.last_reload_success = false;
            
            fprintf(stderr, "[runtime_config] Failed to apply new config: %s\n",
                   monitoring_error_string(err));
            
            if (g_runtime_state.options.on_config_reload) {
                g_runtime_state.options.on_config_reload(false, monitoring_error_string(err));
            }
        }
    } else {
        g_runtime_state.last_reload_success = false;
        
        fprintf(stderr, "[runtime_config] Failed to load config file: %s\n",
               monitoring_error_string(err));
        
        if (g_runtime_state.options.on_config_reload) {
            g_runtime_state.options.on_config_reload(false, monitoring_error_string(err));
        }
    }
    
    pthread_mutex_unlock(&g_runtime_state.config_lock);
    
    return err;
}

const char* monitoring_get_config_file_path(void)
{
    if (!g_runtime_state.initialized) {
        return NULL;
    }
    return g_runtime_state.options.config_file_path;
}

monitoring_error_t monitoring_set_auto_reload(bool enabled)
{
    if (!g_runtime_state.initialized) {
        return MONITORING_NOT_INITIALIZED;
    }
    
    pthread_mutex_lock(&g_runtime_state.config_lock);
    
    if (enabled && !g_runtime_state.watcher_running) {
        /* Start watcher */
        g_runtime_state.watcher_running = true;
        pthread_create(&g_runtime_state.watcher_thread, NULL,
                      config_watcher_thread, NULL);
    } else if (!enabled && g_runtime_state.watcher_running) {
        /* Stop watcher */
        g_runtime_state.watcher_running = false;
        pthread_join(g_runtime_state.watcher_thread, NULL);
    }
    
    g_runtime_state.options.auto_reload = enabled;
    
    pthread_mutex_unlock(&g_runtime_state.config_lock);
    
    return MONITORING_OK;
}

monitoring_error_t monitoring_get_reload_status(time_t* timestamp, bool* success)
{
    if (!g_runtime_state.initialized) {
        return MONITORING_NOT_INITIALIZED;
    }
    
    pthread_mutex_lock(&g_runtime_state.config_lock);
    
    if (timestamp) {
        *timestamp = g_runtime_state.last_reload_time;
    }
    
    if (success) {
        *success = g_runtime_state.last_reload_success;
    }
    
    pthread_mutex_unlock(&g_runtime_state.config_lock);
    
    return MONITORING_OK;
}

/* ========================================================================== */
/* Internal Functions                                                         */
/* ========================================================================== */

static void* config_watcher_thread(void* arg)
{
    (void)arg;
    
    while (g_runtime_state.watcher_running) {
        sleep(g_runtime_state.options.check_interval_seconds);
        
        if (!g_runtime_state.watcher_running) {
            break;
        }
        
        /* Check if config file has been modified */
        time_t current_mtime = get_file_mtime(g_runtime_state.options.config_file_path);
        
        if (current_mtime > g_runtime_state.last_modified) {
            fprintf(stderr, "[runtime_config] Config file changed, reloading...\n");
            
            /* Small delay to ensure file write is complete */
            usleep(100000); /* 100ms */
            
            monitoring_reload_config();
            
            g_runtime_state.last_modified = current_mtime;
        }
    }
    
    return NULL;
}

static time_t get_file_mtime(const char* path)
{
    struct stat st;
    if (stat(path, &st) == 0) {
        return st.st_mtime;
    }
    return 0;
}

static monitoring_error_t load_config_from_file(const char* path, monitoring_config_t* config)
{
    if (!path || !config) {
        return MONITORING_INVALID_PARAM;
    }
    
    FILE* fp = fopen(path, "r");
    if (!fp) {
        return MONITORING_IO_ERROR;
    }
    
    /* Read file content */
    fseek(fp, 0, SEEK_END);
    long size = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    
    char* content = malloc(size + 1);
    if (!content) {
        fclose(fp);
        return MONITORING_NO_MEMORY;
    }
    
    fread(content, 1, size, fp);
    content[size] = '\0';
    fclose(fp);
    
    /* Simple JSON parsing (in production, use a proper JSON library) */
    /* For now, we'll implement a minimal parser for demonstration */
    
    /* Extract mode */
    char* mode_str = strstr(content, "\"mode\"");
    if (mode_str) {
        if (strstr(mode_str, "\"sidecar\"")) {
            config->mode = MONITORING_MODE_SIDECAR;
        } else if (strstr(mode_str, "\"direct\"")) {
            config->mode = MONITORING_MODE_DIRECT;
        }
    }
    
    /* Extract app info */
    char* app_name = strstr(content, "\"name\"");
    if (app_name) {
        /* Parse app name (simplified) */
        char* start = strchr(app_name + 6, '"');
        if (start) {
            start++;
            char* end = strchr(start, '"');
            if (end) {
                size_t len = end - start;
                if (len < 256) {
                    strncpy((char*)config->app_name, start, len);
                    ((char*)config->app_name)[len] = '\0';
                }
            }
        }
    }
    
    /* Note: Full JSON parsing would extract all backends, configurations, etc. */
    /* This is a simplified demonstration. Use cJSON or similar in production. */
    
    free(content);
    
    return MONITORING_OK;
}

static monitoring_error_t apply_new_config(const monitoring_config_t* new_config)
{
    /* In a full implementation, this would:
     * 1. Initialize new backends
     * 2. Keep old backends active during transition
     * 3. Gracefully shutdown old backends
     * 4. Swap to new backends atomically
     * 
     * For now, we'll do a simplified version
     */
    
    /* TODO: Implement hot-swap logic */
    /* This requires backend interface changes to support:
     * - Backend lifecycle management
     * - Graceful shutdown
     * - Atomic swapping
     */
    
    return MONITORING_OK;
}

