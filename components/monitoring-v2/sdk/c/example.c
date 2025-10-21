/**
 * C SDK Example
 * Demonstrates monitoring instrumentation
 */

#include "monitoring_sdk.h"
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <time.h>

void process_item(monitoring_sdk_t* sdk, const char* item, const char* job_id, int index, int total);

int main() {
    printf("=== C SDK Example with Job Analysis ===\n\n");
    
    // Create SDK
    monitoring_sdk_t* sdk = monitoring_sdk_create("c-service", "localhost", 17000);
    if (!sdk) {
        fprintf(stderr, "Failed to create SDK\n");
        return 1;
    }
    
    // Start job analysis
    char* job_id = monitoring_start_job_analysis(sdk, "batch_processing_job", "multiprocess");
    if (job_id) {
        monitoring_set_trace_id(sdk, job_id);
        printf("Started job analysis: %s\n", job_id);
    }
    
    // Log service start
    monitoring_log_event(sdk, "info", "C service starting", NULL);
    
    // Start main span
    char main_span[32];
    monitoring_start_span(sdk, "process_batch", job_id, main_span);
    
    monitoring_log_event(sdk, "info", "Processing 5 items", "{\"job_id\":\"job-123\"}");
    
    // Process items with subjob tracking
    const char* items[] = {"item-001", "item-002", "item-003", "item-004", "item-005"};
    int num_items = 5;
    
    for (int i = 0; i < num_items; i++) {
        // Start subjob tracking
        char subjob_name[64];
        snprintf(subjob_name, sizeof(subjob_name), "process_%s", items[i]);
        char* subjob_id = monitoring_track_subjob(sdk, subjob_name, "task");
        
        process_item(sdk, items[i], job_id, i, num_items);
        
        // End subjob
        monitoring_end_subjob(sdk, subjob_id, "completed");
        free(subjob_id);
    }
    
    // Log final resource usage
    monitoring_log_resource_auto(sdk);  // Final job analysis metrics
    
    // Complete
    monitoring_log_progress(sdk, job_id, 100, "completed");
    monitoring_log_event(sdk, "info", "Batch processing completed", "{\"job_id\":\"job-123\"}");
    
    // End main span
    monitoring_end_span(sdk, main_span, "success", NULL);
    
    // End job analysis
    monitoring_end_job_analysis(sdk, "completed");
    
    // Show statistics
    uint64_t sent, buffered, dropped;
    monitoring_get_stats(sdk, &sent, &buffered, &dropped);
    
    printf("\n📊 SDK Statistics:\n");
    printf("   State: %d\n", monitoring_get_state(sdk));
    printf("   Messages sent: %llu\n", (unsigned long long)sent);
    printf("   Messages buffered: %llu\n", (unsigned long long)buffered);
    printf("   Messages dropped: %llu\n", (unsigned long long)dropped);
    
    // Cleanup
    free(job_id);
    monitoring_sdk_destroy(sdk);
    
    printf("\n✓ C service finished\n\n");
    
    return 0;
}

void process_item(monitoring_sdk_t* sdk, const char* item, const char* job_id, int index, int total) {
    // Start item span
    char item_span[32];
    monitoring_start_span(sdk, "process_item", NULL, item_span);
    
    char context[128];
    snprintf(context, sizeof(context), "{\"item\":\"%s\",\"index\":%d}", item, index);
    monitoring_log_event(sdk, "info", "Processing item", context);
    
    // Simulate work
    usleep((rand() % 200 + 100) * 1000);  // 100-300ms
    
    // Log progress
    int percent = (int)(((float)(index + 1) / total) * 100);
    monitoring_log_progress(sdk, job_id, percent, "processing");
    
    // Log metric
    double processing_time = (rand() % 150) + 50.0;
    char tags[64];
    snprintf(tags, sizeof(tags), "{\"item\":\"%s\"}", item);
    monitoring_log_metric(sdk, "item_processing_time_ms", processing_time, "milliseconds", tags);
    
    // Log resource usage for this item (auto-collected)
    monitoring_log_resource_auto(sdk);
    
    // End span
    monitoring_end_span(sdk, item_span, "success", tags);
}

