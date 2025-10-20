/**
 * @file direct_mode.c
 * @brief Example using direct mode with file backend
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include "monitoring.h"

int main() {
    printf("=== C SDK Direct Mode Example ===\n\n");
    
    /* Configure SDK in direct mode */
    monitoring_backend_config_t backends[] = {
        {
            .type = MONITORING_BACKEND_FILESYSTEM,
            .enabled = true,
            .priority = 1,
            .config = NULL  /* TODO: Add file backend config */
        }
    };
    
    monitoring_config_t config = {
        .mode = MONITORING_MODE_DIRECT,
        .app_name = "direct-mode-example",
        .app_version = "1.0.0",
        .site_id = "fab1",
        .instance_id = "direct-001",
        .backends = backends,
        .num_backends = 1
    };
    
    /* Initialize SDK */
    monitoring_error_t err = monitoring_init(&config);
    if (err != MONITORING_OK) {
        fprintf(stderr, "Failed to initialize SDK: %s\n",
                monitoring_error_string(err));
        return 1;
    }
    
    printf("✓ SDK initialized in DIRECT mode\n");
    printf("✓ Using FileSystem backend\n");
    printf("✓ Events will be written to: ./monitoring_events/\n\n");
    
    /* Run a simple job */
    printf("Running monitored job...\n");
    monitoring_context_t ctx = monitoring_start("direct-job", "job-001");
    
    if (!ctx) {
        fprintf(stderr, "Failed to start context\n");
        monitoring_shutdown();
        return 1;
    }
    
    /* Simulate work */
    for (int i = 1; i <= 3; i++) {
        sleep(1);
        int progress = i * 33;
        monitoring_progress(ctx, progress, "Processing");
        monitoring_add_metric(ctx, "iteration", (double)i);
        printf("  [%3d%%] Iteration %d/3\n", progress, i);
    }
    
    /* Finish */
    printf("\n✓ Job completed\n");
    monitoring_finish(ctx);
    
    /* Cleanup */
    monitoring_shutdown();
    printf("✓ SDK shut down\n");
    printf("\nℹ  Check ./monitoring_events/ for output files\n\n");
    
    return 0;
}

