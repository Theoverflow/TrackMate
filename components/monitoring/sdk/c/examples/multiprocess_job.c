/**
 * @file multiprocess_job.c
 * @brief Multiprocess job example simulating real workload
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/wait.h>
#include <time.h>
#include "monitoring.h"

#define NUM_WORKERS 4
#define TASKS_PER_WORKER 5

void worker_process(int worker_id, monitoring_config_t* config) {
    /* Re-initialize SDK in child process */
    monitoring_init(config);
    
    char entity_id[64];
    snprintf(entity_id, sizeof(entity_id), "worker-%d", worker_id);
    
    monitoring_context_t ctx = monitoring_start("worker-task", entity_id);
    if (!ctx) {
        fprintf(stderr, "Worker %d: Failed to start context\n", worker_id);
        exit(1);
    }
    
    monitoring_add_metadata(ctx, "worker_id", entity_id);
    
    /* Simulate processing tasks */
    for (int task = 0; task < TASKS_PER_WORKER; task++) {
        /* Simulate work (100ms per task) */
        usleep(100000);
        
        int progress = ((task + 1) * 100) / TASKS_PER_WORKER;
        monitoring_progress(ctx, progress, "Processing tasks");
        
        /* Add metrics */
        monitoring_add_metric(ctx, "tasks_completed", (double)(task + 1));
        monitoring_add_metric(ctx, "cpu_usage", 45.0 + (rand() % 30));
        
        printf("[Worker %d] Task %d/%d completed (%d%%)\n",
               worker_id, task + 1, TASKS_PER_WORKER, progress);
    }
    
    monitoring_finish(ctx);
    monitoring_shutdown();
}

int main() {
    printf("=== C SDK Multiprocess Job Example ===\n\n");
    
    srand(time(NULL));
    
    /* Configure SDK */
    monitoring_config_t config = {
        .mode = MONITORING_MODE_SIDECAR,
        .app_name = "multiprocess-c-job",
        .app_version = "1.0.0",
        .site_id = "fab1",
        .instance_id = "mp-001",
        .sidecar_url = "http://localhost:17000",
        .timeout = 5.0,
        .max_retries = 3,
        .num_backends = 0
    };
    
    /* Initialize SDK in parent */
    monitoring_error_t err = monitoring_init(&config);
    if (err != MONITORING_OK) {
        fprintf(stderr, "Failed to initialize SDK: %s\n",
                monitoring_error_string(err));
        return 1;
    }
    
    printf("✓ SDK initialized\n");
    printf("✓ Spawning %d worker processes...\n\n", NUM_WORKERS);
    
    /* Start parent job monitoring */
    monitoring_context_t parent_ctx = monitoring_start("multiprocess-job", "main");
    if (!parent_ctx) {
        fprintf(stderr, "Failed to start parent context\n");
        monitoring_shutdown();
        return 1;
    }
    
    /* Spawn worker processes */
    pid_t workers[NUM_WORKERS];
    for (int i = 0; i < NUM_WORKERS; i++) {
        workers[i] = fork();
        
        if (workers[i] == 0) {
            /* Child process */
            worker_process(i + 1, &config);
            exit(0);
        } else if (workers[i] < 0) {
            fprintf(stderr, "Failed to fork worker %d\n", i + 1);
            monitoring_error(parent_ctx, "Failed to spawn workers");
            monitoring_shutdown();
            return 1;
        }
    }
    
    /* Wait for all workers to complete */
    int completed = 0;
    for (int i = 0; i < NUM_WORKERS; i++) {
        int status;
        waitpid(workers[i], &status, 0);
        completed++;
        
        int progress = (completed * 100) / NUM_WORKERS;
        monitoring_progress(parent_ctx, progress, "Workers completing");
        
        printf("\n[Parent] Worker %d completed (%d/%d)\n",
               i + 1, completed, NUM_WORKERS);
    }
    
    /* Add summary metrics */
    monitoring_add_metric(parent_ctx, "total_workers", (double)NUM_WORKERS);
    monitoring_add_metric(parent_ctx, "total_tasks", (double)(NUM_WORKERS * TASKS_PER_WORKER));
    
    printf("\n✓ All workers completed\n");
    monitoring_finish(parent_ctx);
    
    /* Cleanup */
    monitoring_shutdown();
    printf("✓ Job finished successfully\n\n");
    
    return 0;
}

