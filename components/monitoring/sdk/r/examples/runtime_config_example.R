#!/usr/bin/env Rscript

# Runtime Configuration Example for R SDK

library(monitoring)

cat("=== R SDK Runtime Configuration Example ===\n\n")

# Default configuration (fallback)
default_config <- list(
  mode = "sidecar",
  app_name = "runtime-config-r-example",
  app_version = "1.0.0",
  site_id = "fab1",
  sidecar_url = "http://localhost:17000"
)

# Config file path
config_file <- "monitoring_config_r.yaml"
if (length(commandArgs(trailingOnly = TRUE)) > 0) {
  config_file <- commandArgs(trailingOnly = TRUE)[1]
}

cat("Using config file:", config_file, "\n\n")

# Reload callback
on_reload_callback <- function(success, message) {
  if (success) {
    cat("✓ Config reloaded:", message, "\n")
  } else {
    cat("✗ Config reload failed:", message, "\n")
  }
}

# Initialize with runtime config
monitoring_init_with_runtime_config(
  config_file = config_file,
  default_config = default_config,
  auto_reload = TRUE,
  check_interval = 10,  # Check every 10 seconds
  on_reload = on_reload_callback,
  use_fallback = TRUE
)

cat("✓ SDK initialized with runtime config\n")
cat("✓ Config file:", config_file, "\n")
cat("✓ Auto-reload: enabled (check every 10 seconds)\n\n")

cat("Running application...\n")
cat("Try editing '", config_file, "' while this runs!\n", sep = "")
cat("Add/remove backends and see them activated without restart.\n")
cat("Press Ctrl+C to stop.\n\n")

# Simulate long-running application
event_count <- 0
running <- TRUE

# Setup signal handler
on_interrupt <- function() {
  running <<- FALSE
}

# Run main loop
tryCatch({
  while (running) {
    # Send periodic events
    event_count <- event_count + 1
    entity_id <- paste0("event-", event_count)
    
    ctx <- monitoring_start("periodic-job", entity_id)
    if (!is.null(ctx)) {
      monitoring_progress(ctx, 50, "processing")
      monitoring_add_metric(ctx, "event_number", event_count)
      monitoring_finish(ctx)
      
      cat("[", event_count, "] Sent event to active backends\n", sep = "")
    }
    
    # Display reload status
    status <- monitoring_get_runtime_status()
    if (!is.null(status$last_reload_time) && status$last_reload_time > 0) {
      elapsed <- as.numeric(difftime(Sys.time(), status$last_reload_time, units = "secs"))
      cat("    Last reload:", round(elapsed), "s ago (",
          ifelse(status$last_reload_success, "success", "failed"), ")\n")
    }
    
    Sys.sleep(5)  # Wait between events
  }
}, interrupt = function(e) {
  cat("\n\nShutting down gracefully...\n")
})

cat("\n✓ Shutting down...\n")
monitoring_shutdown_runtime_config()

cat("✓ Application stopped\n\n")
cat("Summary:\n")
cat("  - Events sent:", event_count, "\n")
cat("  - Config file:", config_file, "\n")
cat("  - Final status: runtime config shut down\n\n")

