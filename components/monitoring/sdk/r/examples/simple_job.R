#!/usr/bin/env Rscript

# Simple R job example using the monitoring SDK

library(monitoring)

cat("=== R SDK Simple Job Example ===\n\n")

# Initialize SDK
monitoring_init(
  mode = "sidecar",
  app_name = "example-r-job",
  app_version = "1.0.0",
  site_id = "fab1",
  sidecar_url = "http://localhost:17000"
)

cat("✓ SDK initialized\n\n")

# Start monitored job
cat("Starting monitored job...\n")
ctx <- monitoring_start("process-data", "R-12345")

# Simulate work with progress updates
for (i in 1:5) {
  Sys.sleep(1)
  progress <- i * 20
  message <- sprintf("Processing step %d/5", i)
  
  monitoring_progress(ctx, progress, message)
  cat(sprintf("  [%3d%%] %s\n", progress, message))
  
  # Add some metrics
  monitoring_add_metric(ctx, "temperature", 75.5 + i)
  monitoring_add_metric(ctx, "pressure", 1013.25 - i * 0.5)
}

# Add final metadata
monitoring_add_metadata(ctx, "operator", "john.doe")
monitoring_add_metadata(ctx, "machine_id", "WFR-001")

# Finish successfully
cat("\n✓ Job completed successfully\n")
monitoring_finish(ctx)

# Cleanup
monitoring_shutdown()
cat("✓ SDK shut down\n\n")

