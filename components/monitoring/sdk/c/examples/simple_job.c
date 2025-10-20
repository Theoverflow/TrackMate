/**
 * @file simple_job.c
 * @brief Simple example of using the C monitoring SDK
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include "monitoring.h"

int main() {
    printf("=== C SDK Simple Job Example ===\n\n");
    
    /* Configure SDK */
    monitoring_config_t config = {
        .mode = MONITORING_MODE_SIDECAR,
        .app_name = "example-c-job",
        .app_version = "1.0.0",
        .site_id = "fab1",
        .instance_id = "example-001",
        .sidecar_url = "http://localhost:17000",
        .timeout = 5.0,
        .max_retries = 3,
        .num_backends = 0
    };
    
    /* Initialize SDK */
    monitoring_error_t err = monitoring_init(&config);
    if (err != MONITORING_OK) {
        fprintf(stderr, "Failed to initialize SDK: %s\n", 
                monitoring_error_string(err));
        return 1;
    }
    
    printf("✓ SDK initialized (version %s)\n", monitoring_version());
    printf("✓ Mode: Sidecar\n");
    printf("✓ Sidecar URL: %s\n\n", config.sidecar_url);
    
    /* Start monitored job */
    printf("Starting monitored job...\n");
    monitoring_context_t ctx = monitoring_start("process-wafer", "W-12345");
    
    if (!ctx) {
        fprintf(stderr, "Failed to start monitoring context\n");
        monitoring_shutdown();
        return 1;
    }
    
    /* Simulate work with progress updates */
    for (int i = 1; i <= 5; i++) {
        sleep(1);
        int progress = i * 20;
        
        char message[64];
        snprintf(message, sizeof(message), "Processing step %d/5", i);
        
        monitoring_progress(ctx, progress, message);
        printf("  [%3d%%] %s\n", progress, message);
        
        /* Add some metrics */
        monitoring_add_metric(ctx, "temperature", 75.5 + i);
        monitoring_add_metric(ctx, "pressure", 1013.25 - i * 0.5);
    }
    
    /* Add final metadata */
    monitoring_add_metadata(ctx, "operator", "john.doe");
    monitoring_add_metadata(ctx, "machine_id", "WFR-001");
    
    /* Finish successfully */
    printf("\n✓ Job completed successfully\n");
    err = monitoring_finish(ctx);
    
    if (err != MONITORING_OK) {
        fprintf(stderr, "Failed to finish context: %s\n",
                monitoring_error_string(err));
    }
    
    /* Cleanup */
    monitoring_shutdown();
    printf("✓ SDK shut down\n\n");
    
    return 0;
}

