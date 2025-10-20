/**
 * @file runtime_config_example.c
 * @brief Example: Runtime Configuration with Hot-Reloading
 * 
 * Demonstrates:
 * - Loading config from JSON file
 * - Automatic config reloading
 * - Adding backends without restart
 * - Fault-tolerant config updates
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <signal.h>
#include "monitoring.h"
#include "monitoring_runtime_config.h"

static volatile bool g_running = true;

void signal_handler(int sig) {
    (void)sig;
    g_running = false;
}

void config_reload_callback(bool success, const char* message) {
    if (success) {
        printf("✓ Config reloaded: %s\n", message);
    } else {
        printf("✗ Config reload failed: %s\n", message);
    }
}

void print_usage(const char* prog) {
    printf("Usage: %s [config-file]\n", prog);
    printf("\n");
    printf("Example config file (config.json):\n");
    printf("{\n");
    printf("  \"mode\": \"direct\",\n");
    printf("  \"app\": {\n");
    printf("    \"name\": \"runtime-config-example\",\n");
    printf("    \"version\": \"1.0.0\",\n");
    printf("    \"site_id\": \"fab1\"\n");
    printf("  },\n");
    printf("  \"backends\": [\n");
    printf("    {\n");
    printf("      \"type\": \"filesystem\",\n");
    printf("      \"name\": \"local-fs\",\n");
    printf("      \"enabled\": true,\n");
    printf("      \"priority\": 1\n");
    printf("    },\n");
    printf("    {\n");
    printf("      \"type\": \"sidecar\",\n");
    printf("      \"name\": \"local-sidecar\",\n");
    printf("      \"enabled\": true,\n");
    printf("      \"priority\": 2,\n");
    printf("      \"config\": {\n");
    printf("        \"url\": \"http://localhost:17000\"\n");
    printf("      }\n");
    printf("    }\n");
    printf("  ]\n");
    printf("}\n");
    printf("\n");
    printf("To add a backend at runtime:\n");
    printf("1. Edit config.json\n");
    printf("2. Add new backend to 'backends' array\n");
    printf("3. SDK will auto-reload and activate new backend\n");
    printf("4. No application restart needed!\n");
}

int main(int argc, char* argv[]) {
    printf("=== Runtime Configuration Example ===\n\n");
    
    const char* config_file = "config.json";
    if (argc > 1) {
        if (strcmp(argv[1], "--help") == 0 || strcmp(argv[1], "-h") == 0) {
            print_usage(argv[0]);
            return 0;
        }
        config_file = argv[1];
    }
    
    printf("Using config file: %s\n\n", config_file);
    
    /* Setup signal handling */
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);
    
    /* Default configuration (compile-time fallback) */
    monitoring_config_t default_config = {
        .mode = MONITORING_MODE_SIDECAR,
        .app_name = "runtime-config-example",
        .app_version = "1.0.0",
        .site_id = "fab1",
        .instance_id = "example-001",
        .sidecar_url = "http://localhost:17000",
        .timeout = 5.0,
        .max_retries = 3,
        .num_backends = 0
    };
    
    /* Runtime configuration options */
    monitoring_runtime_config_options_t runtime_opts = {
        .config_file_path = config_file,
        .check_interval_seconds = 10,  /* Check every 10 seconds */
        .auto_reload = true,
        .on_config_reload = config_reload_callback,
        .use_fallback = true  /* Use default config if file not found */
    };
    
    /* Initialize with runtime config support */
    monitoring_error_t err = monitoring_init_with_runtime_config(
        &default_config,
        &runtime_opts
    );
    
    if (err != MONITORING_OK) {
        fprintf(stderr, "Failed to initialize SDK: %s\n", 
                monitoring_error_string(err));
        return 1;
    }
    
    printf("✓ SDK initialized with runtime config\n");
    printf("✓ Config file: %s\n", config_file);
    printf("✓ Auto-reload: enabled (check every %d seconds)\n\n", 
           runtime_opts.check_interval_seconds);
    
    printf("Running application...\n");
    printf("Try editing '%s' while this runs!\n", config_file);
    printf("Add/remove backends and see them activated without restart.\n");
    printf("Press Ctrl+C to stop.\n\n");
    
    /* Simulate long-running application */
    int event_count = 0;
    
    while (g_running) {
        /* Send periodic events */
        char entity_id[64];
        snprintf(entity_id, sizeof(entity_id), "event-%d", ++event_count);
        
        monitoring_context_t ctx = monitoring_start("periodic-job", entity_id);
        if (ctx) {
            monitoring_progress(ctx, 50, "processing");
            monitoring_add_metric(ctx, "event_number", (double)event_count);
            monitoring_finish(ctx);
            
            printf("[%d] Sent event to active backends\n", event_count);
        }
        
        /* Check reload status */
        time_t last_reload;
        bool reload_success;
        monitoring_get_reload_status(&last_reload, &reload_success);
        
        if (last_reload > 0) {
            printf("    Last reload: %ld seconds ago (%s)\n",
                   time(NULL) - last_reload,
                   reload_success ? "success" : "failed");
        }
        
        sleep(5);  /* Wait between events */
    }
    
    printf("\n✓ Shutting down...\n");
    
    /* Cleanup */
    monitoring_set_auto_reload(false);  /* Stop watcher thread */
    monitoring_shutdown();
    
    printf("✓ Application stopped\n\n");
    printf("Summary:\n");
    printf("  - Events sent: %d\n", event_count);
    printf("  - Config file: %s\n", config_file);
    printf("  - Runtime reloads: check logs above\n\n");
    
    return 0;
}

