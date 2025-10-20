#' Runtime Configuration with Hot-Reloading for R SDK
#'
#' @description
#' Enables dynamic backend routing changes without restarting R sessions.
#'
#' @section Features:
#' \itemize{
#'   \item{Load configuration from YAML files}
#'   \item{Auto-detection of file changes}
#'   \item{Hot-reload backends without restart}
#'   \item{Callback support for reload events}
#'   \item{Fallback to default configuration}
#' }
#'
#' @name runtime_config
NULL

# Runtime config state (module-level)
.runtime_state <- new.env(parent = emptyenv())
.runtime_state$initialized <- FALSE
.runtime_state$config_file <- NULL
.runtime_state$check_interval <- 30
.runtime_state$auto_reload <- FALSE
.runtime_state$on_reload <- NULL
.runtime_state$last_mtime <- 0
.runtime_state$last_reload_time <- 0
.runtime_state$last_reload_success <- FALSE
.runtime_state$timer_id <- NULL

#' Initialize SDK with Runtime Configuration
#'
#' @param config_file Path to YAML configuration file
#' @param default_config List with default configuration (fallback)
#' @param auto_reload Logical. Enable automatic config reloading
#' @param check_interval Numeric. Check interval in seconds (default: 30)
#' @param on_reload Function(success, message) callback for reload events
#' @param use_fallback Logical. Use default config if file not found
#'
#' @return Invisible NULL
#' @export
#'
#' @examples
#' \dontrun{
#' default_config <- list(
#'   mode = "sidecar",
#'   app = list(name = "my-r-app", version = "1.0.0", site_id = "fab1"),
#'   sidecar = list(url = "http://localhost:17000")
#' )
#' 
#' monitoring_init_with_runtime_config(
#'   config_file = "monitoring_config.yaml",
#'   default_config = default_config,
#'   auto_reload = TRUE,
#'   on_reload = function(success, message) {
#'     if (success) message("✓ Config reloaded: ", message)
#'     else warning("✗ Config reload failed: ", message)
#'   }
#' )
#' }
monitoring_init_with_runtime_config <- function(
  config_file,
  default_config = NULL,
  auto_reload = TRUE,
  check_interval = 30,
  on_reload = NULL,
  use_fallback = TRUE
) {
  if (.runtime_state$initialized) {
    stop("Runtime config already initialized. Call monitoring_shutdown_runtime_config() first.")
  }
  
  # Store runtime options
  .runtime_state$config_file <- config_file
  .runtime_state$check_interval <- check_interval
  .runtime_state$auto_reload <- auto_reload
  .runtime_state$on_reload <- on_reload
  
  # Try to load config from file
  config <- .load_config_from_file(config_file)
  
  if (is.null(config) && use_fallback && !is.null(default_config)) {
    config <- default_config
    message("Using default config as fallback")
  } else if (is.null(config)) {
    stop("Failed to load config and no fallback available")
  }
  
  # Initialize SDK with loaded config
  tryCatch({
    do.call(monitoring_init, config)
    .runtime_state$last_reload_time <- Sys.time()
    .runtime_state$last_reload_success <- TRUE
    message("✓ SDK initialized with runtime config from: ", config_file)
  }, error = function(e) {
    if (!is.null(on_reload)) {
      on_reload(FALSE, paste("Init failed:", e$message))
    }
    stop(e)
  })
  
  # Get initial file mtime
  if (file.exists(config_file)) {
    .runtime_state$last_mtime <- file.info(config_file)$mtime
  }
  
  # Start auto-reload timer if enabled
  if (auto_reload) {
    .start_file_watcher()
  }
  
  .runtime_state$initialized <- TRUE
  
  if (!is.null(on_reload)) {
    on_reload(TRUE, "Initial configuration loaded")
  }
  
  invisible(NULL)
}

#' Manually Reload Configuration
#'
#' @return Logical. TRUE if reload successful, FALSE otherwise
#' @export
monitoring_reload_runtime_config <- function() {
  if (!.runtime_state$initialized) {
    warning("Runtime config not initialized")
    return(FALSE)
  }
  
  message("Manually reloading configuration...")
  return(.reload_config())
}

#' Get Runtime Configuration Status
#'
#' @return List with reload status information
#' @export
monitoring_get_runtime_status <- function() {
  if (!.runtime_state$initialized) {
    return(list(initialized = FALSE))
  }
  
  list(
    initialized = .runtime_state$initialized,
    config_file = .runtime_state$config_file,
    auto_reload = .runtime_state$auto_reload,
    check_interval = .runtime_state$check_interval,
    last_reload_time = .runtime_state$last_reload_time,
    last_reload_success = .runtime_state$last_reload_success
  )
}

#' Enable or Disable Auto-Reload
#'
#' @param enabled Logical. TRUE to enable, FALSE to disable
#' @export
monitoring_set_auto_reload <- function(enabled) {
  if (!.runtime_state$initialized) {
    warning("Runtime config not initialized")
    return(invisible(NULL))
  }
  
  if (enabled && !.runtime_state$auto_reload) {
    .start_file_watcher()
    .runtime_state$auto_reload <- TRUE
    message("Auto-reload enabled")
  } else if (!enabled && .runtime_state$auto_reload) {
    .stop_file_watcher()
    .runtime_state$auto_reload <- FALSE
    message("Auto-reload disabled")
  }
  
  invisible(NULL)
}

#' Shutdown Runtime Configuration
#'
#' @export
monitoring_shutdown_runtime_config <- function() {
  if (!.runtime_state$initialized) {
    return(invisible(NULL))
  }
  
  .stop_file_watcher()
  monitoring_shutdown()
  
  .runtime_state$initialized <- FALSE
  .runtime_state$config_file <- NULL
  
  message("✓ Runtime config shut down")
  invisible(NULL)
}

# ============================================================================
# Internal Functions
# ============================================================================

.load_config_from_file <- function(file_path) {
  if (!file.exists(file_path)) {
    warning("Config file not found: ", file_path)
    return(NULL)
  }
  
  tryCatch({
    # Load YAML config
    if (!requireNamespace("yaml", quietly = TRUE)) {
      stop("yaml package required for config files. Install with: install.packages('yaml')")
    }
    
    config <- yaml::read_yaml(file_path)
    message("Config loaded from: ", file_path)
    return(config)
    
  }, error = function(e) {
    warning("Failed to load config file: ", e$message)
    return(NULL)
  })
}

.reload_config <- function() {
  config <- .load_config_from_file(.runtime_state$config_file)
  
  if (is.null(config)) {
    .runtime_state$last_reload_success <- FALSE
    .runtime_state$last_reload_time <- Sys.time()
    
    msg <- "Failed to load config file"
    warning(msg)
    if (!is.null(.runtime_state$on_reload)) {
      .runtime_state$on_reload(FALSE, msg)
    }
    return(FALSE)
  }
  
  tryCatch({
    # Shutdown current SDK
    monitoring_shutdown()
    
    # Re-initialize with new config
    do.call(monitoring_init, config)
    
    .runtime_state$last_reload_success <- TRUE
    .runtime_state$last_reload_time <- Sys.time()
    
    msg <- "Configuration reloaded successfully"
    message("✓ ", msg)
    if (!is.null(.runtime_state$on_reload)) {
      .runtime_state$on_reload(TRUE, msg)
    }
    
    return(TRUE)
    
  }, error = function(e) {
    .runtime_state$last_reload_success <- FALSE
    .runtime_state$last_reload_time <- Sys.time()
    
    msg <- paste("Failed to apply new config:", e$message)
    warning(msg)
    if (!is.null(.runtime_state$on_reload)) {
      .runtime_state$on_reload(FALSE, msg)
    }
    
    return(FALSE)
  })
}

.check_file_changed <- function() {
  if (!file.exists(.runtime_state$config_file)) {
    return(FALSE)
  }
  
  current_mtime <- file.info(.runtime_state$config_file)$mtime
  
  if (current_mtime > .runtime_state$last_mtime) {
    # File was modified
    .runtime_state$last_mtime <- current_mtime
    
    # Small delay to ensure file write is complete
    Sys.sleep(0.1)
    
    message("Config file changed, reloading...")
    .reload_config()
    
    return(TRUE)
  }
  
  return(FALSE)
}

.file_watcher_task <- function() {
  .check_file_changed()
}

.start_file_watcher <- function() {
  if (!is.null(.runtime_state$timer_id)) {
    return()  # Already running
  }
  
  # Schedule periodic check
  # Note: Using later package for async task scheduling
  if (!requireNamespace("later", quietly = TRUE)) {
    warning("later package recommended for auto-reload. Install with: install.packages('later')")
    warning("Auto-reload disabled. Use manual reload instead.")
    return()
  }
  
  # Create recurring task
  .runtime_state$timer_id <- later::later(
    function() {
      .file_watcher_task()
      # Reschedule
      if (.runtime_state$auto_reload) {
        .start_file_watcher()
      }
    },
    delay = .runtime_state$check_interval
  )
  
  message("File watcher started (check interval: ", .runtime_state$check_interval, "s)")
}

.stop_file_watcher <- function() {
  # In R, we can't easily cancel a later() task once scheduled
  # Just set auto_reload to FALSE to prevent rescheduling
  .runtime_state$timer_id <- NULL
}

