/**
 * @file error_example.c
 * @brief Example demonstrating error handling
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include "monitoring.h"

int main() {
    printf("=== C SDK Error Handling Example ===\n\n");
    
    /* Configure SDK */
    monitoring_config_t config = {
        .mode = MONITORING_MODE_SIDECAR,
        .app_name = "error-example",
        .app_version = "1.0.0",
        .site_id = "fab1",
        .instance_id = "err-001",
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
    
    printf("✓ SDK initialized\n\n");
    
    /* Example 1: Successful job */
    printf("Example 1: Successful job\n");
    printf("---------------------------\n");
    monitoring_context_t ctx1 = monitoring_start("test-job-success", "job-001");
    sleep(1);
    monitoring_finish(ctx1);
    printf("✓ Completed successfully\n\n");
    
    /* Example 2: Job with error */
    printf("Example 2: Job with error\n");
    printf("---------------------------\n");
    monitoring_context_t ctx2 = monitoring_start("test-job-error", "job-002");
    sleep(1);
    monitoring_add_metadata(ctx2, "error_code", "ERR_INVALID_INPUT");
    monitoring_error(ctx2, "Invalid input parameter detected");
    printf("✗ Job failed with error\n\n");
    
    /* Example 3: Job with cancellation */
    printf("Example 3: Job cancelled\n");
    printf("---------------------------\n");
    monitoring_context_t ctx3 = monitoring_start("test-job-cancel", "job-003");
    sleep(1);
    monitoring_cancel(ctx3);
    printf("⊘ Job cancelled\n\n");
    
    /* Example 4: Testing NULL parameters */
    printf("Example 4: Invalid parameters\n");
    printf("---------------------------\n");
    err = monitoring_send_event(NULL);
    printf("Sending NULL event: %s\n", monitoring_error_string(err));
    
    monitoring_context_t ctx_null = monitoring_start(NULL, "test");
    printf("Starting with NULL name: %s\n", 
           ctx_null ? "SUCCESS" : "FAILED (expected)");
    
    /* Cleanup */
    monitoring_shutdown();
    printf("\n✓ All examples completed\n\n");
    
    return 0;
}

