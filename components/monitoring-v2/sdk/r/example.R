#!/usr/bin/env Rscript
# R SDK Example
# Demonstrates monitoring instrumentation

library(jsonlite)

# Source SDK
source("monitoring_sdk.R")

main <- function() {
  cat("=== R SDK Example ===\n\n")
  
  # Create SDK
  sdk <- MonitoringSDK$new(source = "r-service", debug = TRUE)
  
  # Log service start
  sdk$log_event("info", "R service starting")
  
  # Generate job ID
  job_id <- sprintf("job-%d", as.integer(Sys.time()))
  sdk$set_trace_id(job_id)
  
  # Start main span
  main_span <- sdk$start_span("process_batch", job_id)
  
  sdk$log_event("info", "Processing 5 items", list(job_id = job_id))
  
  # Process items
  items <- c("item-001", "item-002", "item-003", "item-004", "item-005")
  
  for (i in seq_along(items)) {
    item <- items[i]
    
    # Start item span
    item_span <- sdk$start_span("process_item")
    
    sdk$log_event("info", sprintf("Processing %s", item), 
                  list(item = item, index = i))
    
    # Simulate work
    Sys.sleep(runif(1, 0.1, 0.3))
    
    # Log progress
    percent <- as.integer(i / length(items) * 100)
    sdk$log_progress(job_id, percent, "processing")
    
    # Log metric
    processing_time <- runif(1, 50, 200)
    sdk$log_metric("item_processing_time_ms", processing_time, "milliseconds",
                   list(item = item))
    
    # End item span
    sdk$end_span(item_span, "success", list(item = item))
  }
  
  # Log resource usage
  sdk$log_resource(
    cpu_percent = runif(1, 30, 60),
    memory_mb = runif(1, 512, 1024),
    disk_io_mb = runif(1, 10, 50),
    network_io_mb = runif(1, 5, 20)
  )
  
  # Complete
  sdk$log_progress(job_id, 100, "completed")
  sdk$log_event("info", "Batch processing completed", list(job_id = job_id))
  
  # End main span
  sdk$end_span(main_span, "success")
  
  # Show statistics
  stats <- sdk$get_stats()
  cat("\n📊 SDK Statistics:\n")
  cat(sprintf("   State: %s\n", stats$state))
  cat(sprintf("   Messages sent: %d\n", stats$messages_sent))
  cat(sprintf("   Messages buffered: %d\n", stats$messages_buffered))
  cat(sprintf("   Messages dropped: %d\n", stats$messages_dropped))
  cat(sprintf("   Buffer size: %d\n", stats$buffer_size))
  cat(sprintf("   Reconnections: %d\n", stats$reconnect_count))
  
  # Cleanup
  sdk$close()
  
  cat("\n✓ R service finished\n\n")
}

# Run
if (!interactive()) {
  main()
}

