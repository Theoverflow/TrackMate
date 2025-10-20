#' Wafer Monitor R SDK
#'
#' @description
#' R client library for monitoring distributed applications.
#'
#' @section Main Functions:
#' \itemize{
#'   \item{\code{\link{monitoring_init}}: Initialize the SDK}
#'   \item{\code{\link{monitoring_start}}: Start a monitored context}
#'   \item{\code{\link{monitoring_progress}}: Report progress}
#'   \item{\code{\link{monitoring_finish}}: Finish successfully}
#'   \item{\code{\link{monitoring_error}}: Finish with error}
#' }
#'
#' @docType package
#' @name monitoring-package
NULL

# Global SDK state
.sdk_state <- new.env(parent = emptyenv())
.sdk_state$initialized <- FALSE
.sdk_state$config <- NULL
.sdk_state$backend <- NULL

#' Initialize Monitoring SDK
#'
#' @param mode Character. Either "sidecar" or "direct"
#' @param app_name Character. Name of the application
#' @param app_version Character. Version of the application
#' @param site_id Character. Site identifier
#' @param instance_id Character. Instance identifier (optional, defaults to hostname)
#' @param sidecar_url Character. URL of sidecar agent (for sidecar mode)
#' @param timeout Numeric. Request timeout in seconds (default: 5.0)
#' @param max_retries Integer. Maximum retries for failed requests (default: 3)
#' @param backend_type Character. Backend type for direct mode ("filesystem", "s3", etc.)
#' @param backend_config List. Backend-specific configuration
#'
#' @return Invisible NULL. Throws error on failure.
#'
#' @export
#' @examples
#' \dontrun{
#' monitoring_init(
#'   mode = "sidecar",
#'   app_name = "my-r-app",
#'   app_version = "1.0.0",
#'   site_id = "fab1",
#'   sidecar_url = "http://localhost:17000"
#' )
#' }
monitoring_init <- function(mode = c("sidecar", "direct"),
                           app_name,
                           app_version,
                           site_id,
                           instance_id = NULL,
                           sidecar_url = "http://localhost:17000",
                           timeout = 5.0,
                           max_retries = 3,
                           backend_type = "filesystem",
                           backend_config = list()) {
  
  if (.sdk_state$initialized) {
    stop("SDK already initialized. Call monitoring_shutdown() first.")
  }
  
  mode <- match.arg(mode)
  
  # Default instance_id to hostname
  if (is.null(instance_id)) {
    instance_id <- Sys.info()["nodename"]
  }
  
  # Store configuration
  .sdk_state$config <- list(
    mode = mode,
    app_name = app_name,
    app_version = app_version,
    site_id = site_id,
    instance_id = instance_id,
    sidecar_url = sidecar_url,
    timeout = timeout,
    max_retries = max_retries,
    backend_type = backend_type,
    backend_config = backend_config
  )
  
  # Initialize backend
  if (mode == "sidecar") {
    .sdk_state$backend <- SidecarBackend$new(
      url = sidecar_url,
      timeout = timeout,
      max_retries = max_retries
    )
  } else {
    if (backend_type == "filesystem") {
      .sdk_state$backend <- FilesystemBackend$new(backend_config)
    } else {
      stop(sprintf("Unsupported backend type: %s", backend_type))
    }
  }
  
  .sdk_state$initialized <- TRUE
  message(sprintf("✓ Monitoring SDK initialized (mode=%s)", mode))
  
  invisible(NULL)
}

#' Shutdown Monitoring SDK
#'
#' @return Invisible NULL
#' @export
monitoring_shutdown <- function() {
  if (!.sdk_state$initialized) {
    warning("SDK not initialized")
    return(invisible(NULL))
  }
  
  .sdk_state$initialized <- FALSE
  .sdk_state$config <- NULL
  .sdk_state$backend <- NULL
  
  message("✓ Monitoring SDK shut down")
  invisible(NULL)
}

#' Check if SDK is Initialized
#'
#' @return Logical. TRUE if initialized, FALSE otherwise
#' @export
monitoring_is_initialized <- function() {
  return(.sdk_state$initialized)
}

#' Start a Monitored Context
#'
#' @param name Character. Name of the job/task
#' @param entity_id Character. Unique identifier for the entity
#' @param entity_type Character. Type of entity ("job", "task", "step")
#'
#' @return A MonitoringContext R6 object
#' @export
#' @examples
#' \dontrun{
#' ctx <- monitoring_start("process-wafer", "W-12345")
#' monitoring_progress(ctx, 50, "Halfway done")
#' monitoring_finish(ctx)
#' }
monitoring_start <- function(name, entity_id, entity_type = "job") {
  if (!.sdk_state$initialized) {
    stop("SDK not initialized. Call monitoring_init() first.")
  }
  
  ctx <- MonitoringContext$new(
    name = name,
    entity_id = entity_id,
    entity_type = entity_type,
    config = .sdk_state$config,
    backend = .sdk_state$backend
  )
  
  ctx$start()
  return(ctx)
}

#' Report Progress
#'
#' @param ctx MonitoringContext object
#' @param progress Numeric. Progress percentage (0-100)
#' @param message Character. Status message
#'
#' @return Invisible NULL
#' @export
monitoring_progress <- function(ctx, progress, message = NULL) {
  if (!inherits(ctx, "MonitoringContext")) {
    stop("Invalid context object")
  }
  ctx$progress(progress, message)
  invisible(NULL)
}

#' Add Metric to Context
#'
#' @param ctx MonitoringContext object
#' @param key Character. Metric name
#' @param value Numeric. Metric value
#'
#' @return Invisible NULL
#' @export
monitoring_add_metric <- function(ctx, key, value) {
  if (!inherits(ctx, "MonitoringContext")) {
    stop("Invalid context object")
  }
  ctx$add_metric(key, value)
  invisible(NULL)
}

#' Add Metadata to Context
#'
#' @param ctx MonitoringContext object
#' @param key Character. Metadata key
#' @param value Character. Metadata value
#'
#' @return Invisible NULL
#' @export
monitoring_add_metadata <- function(ctx, key, value) {
  if (!inherits(ctx, "MonitoringContext")) {
    stop("Invalid context object")
  }
  ctx$add_metadata(key, value)
  invisible(NULL)
}

#' Finish Context Successfully
#'
#' @param ctx MonitoringContext object
#'
#' @return Invisible NULL
#' @export
monitoring_finish <- function(ctx) {
  if (!inherits(ctx, "MonitoringContext")) {
    stop("Invalid context object")
  }
  ctx$finish()
  invisible(NULL)
}

#' Finish Context with Error
#'
#' @param ctx MonitoringContext object
#' @param error_message Character. Error message
#'
#' @return Invisible NULL
#' @export
monitoring_error <- function(ctx, error_message) {
  if (!inherits(ctx, "MonitoringContext")) {
    stop("Invalid context object")
  }
  ctx$error(error_message)
  invisible(NULL)
}

#' Cancel Context
#'
#' @param ctx MonitoringContext object
#'
#' @return Invisible NULL
#' @export
monitoring_cancel <- function(ctx) {
  if (!inherits(ctx, "MonitoringContext")) {
    stop("Invalid context object")
  }
  ctx$cancel()
  invisible(NULL)
}

# ============================================================================
# MonitoringContext R6 Class
# ============================================================================

#' @import R6
MonitoringContext <- R6::R6Class(
  "MonitoringContext",
  
  public = list(
    name = NULL,
    entity_id = NULL,
    entity_type = NULL,
    config = NULL,
    backend = NULL,
    start_time = NULL,
    metrics = NULL,
    metadata = NULL,
    
    initialize = function(name, entity_id, entity_type, config, backend) {
      self$name <- name
      self$entity_id <- entity_id
      self$entity_type <- entity_type
      self$config <- config
      self$backend <- backend
      self$metrics <- list()
      self$metadata <- list()
    },
    
    start = function() {
      self$start_time <- Sys.time()
      
      event <- list(
        idempotency_key = sprintf("%s-start-%d", self$entity_id, as.numeric(self$start_time)),
        site_id = self$config$site_id,
        app_name = self$config$app_name,
        app_version = self$config$app_version,
        entity_type = self$entity_type,
        entity_id = self$entity_id,
        event_kind = "started",
        timestamp = as.numeric(self$start_time),
        status = "started",
        metrics = list(),
        metadata = list()
      )
      
      self$backend$send_event(event)
    },
    
    progress = function(progress, message = NULL) {
      event <- list(
        idempotency_key = sprintf("%s-progress-%d", self$entity_id, as.numeric(Sys.time())),
        site_id = self$config$site_id,
        app_name = self$config$app_name,
        app_version = self$config$app_version,
        entity_type = self$entity_type,
        entity_id = self$entity_id,
        event_kind = "progress",
        timestamp = as.numeric(Sys.time()),
        status = if (!is.null(message)) message else "in_progress",
        metrics = list(progress = progress),
        metadata = list()
      )
      
      self$backend$send_event(event)
    },
    
    add_metric = function(key, value) {
      self$metrics[[key]] <- value
    },
    
    add_metadata = function(key, value) {
      self$metadata[[key]] <- value
    },
    
    finish = function() {
      # Add duration metric
      duration <- as.numeric(difftime(Sys.time(), self$start_time, units = "secs"))
      self$metrics[["duration_seconds"]] <- duration
      
      event <- list(
        idempotency_key = sprintf("%s-finish-%d", self$entity_id, as.numeric(Sys.time())),
        site_id = self$config$site_id,
        app_name = self$config$app_name,
        app_version = self$config$app_version,
        entity_type = self$entity_type,
        entity_id = self$entity_id,
        event_kind = "finished",
        timestamp = as.numeric(Sys.time()),
        status = "success",
        metrics = self$metrics,
        metadata = self$metadata
      )
      
      self$backend$send_event(event)
    },
    
    error = function(error_message) {
      self$metadata[["error"]] <- error_message
      
      event <- list(
        idempotency_key = sprintf("%s-error-%d", self$entity_id, as.numeric(Sys.time())),
        site_id = self$config$site_id,
        app_name = self$config$app_name,
        app_version = self$config$app_version,
        entity_type = self$entity_type,
        entity_id = self$entity_id,
        event_kind = "error",
        timestamp = as.numeric(Sys.time()),
        status = "error",
        metrics = self$metrics,
        metadata = self$metadata
      )
      
      self$backend$send_event(event)
    },
    
    cancel = function() {
      event <- list(
        idempotency_key = sprintf("%s-cancel-%d", self$entity_id, as.numeric(Sys.time())),
        site_id = self$config$site_id,
        app_name = self$config$app_name,
        app_version = self$config$app_version,
        entity_type = self$entity_type,
        entity_id = self$entity_id,
        event_kind = "canceled",
        timestamp = as.numeric(Sys.time()),
        status = "canceled",
        metrics = list(),
        metadata = list()
      )
      
      self$backend$send_event(event)
    }
  )
)

# ============================================================================
# Backend Classes
# ============================================================================

#' @import R6
#' @import httr
#' @import jsonlite
SidecarBackend <- R6::R6Class(
  "SidecarBackend",
  
  public = list(
    url = NULL,
    timeout = NULL,
    max_retries = NULL,
    
    initialize = function(url, timeout, max_retries) {
      self$url <- url
      self$timeout <- timeout
      self$max_retries <- max_retries
    },
    
    send_event = function(event) {
      endpoint <- sprintf("%s/v1/ingest/events", self$url)
      
      for (attempt in 1:self$max_retries) {
        tryCatch({
          response <- httr::POST(
            endpoint,
            body = jsonlite::toJSON(event, auto_unbox = TRUE),
            httr::content_type_json(),
            httr::timeout(self$timeout)
          )
          
          if (httr::status_code(response) >= 200 && httr::status_code(response) < 300) {
            return(invisible(NULL))
          }
          
          if (httr::status_code(response) >= 400 && httr::status_code(response) < 500) {
            # Client error, don't retry
            warning(sprintf("HTTP error %d: %s", httr::status_code(response), httr::content(response, "text")))
            return(invisible(NULL))
          }
          
        }, error = function(e) {
          if (attempt == self$max_retries) {
            warning(sprintf("Failed to send event after %d attempts: %s", self$max_retries, e$message))
          } else {
            Sys.sleep(0.1 * (2^attempt))  # Exponential backoff
          }
        })
      }
      
      invisible(NULL)
    }
  )
)

#' @import R6
FilesystemBackend <- R6::R6Class(
  "FilesystemBackend",
  
  public = list(
    output_dir = NULL,
    filename_prefix = NULL,
    
    initialize = function(config) {
      self$output_dir <- config$output_dir %||% "./monitoring_events"
      self$filename_prefix <- config$filename_prefix %||% "events"
      
      # Create directory if it doesn't exist
      if (!dir.exists(self$output_dir)) {
        dir.create(self$output_dir, recursive = TRUE)
      }
    },
    
    send_event = function(event) {
      timestamp <- as.numeric(Sys.time())
      filename <- sprintf("%s/%s_%d_%d.jsonl", 
                         self$output_dir, 
                         self$filename_prefix,
                         timestamp,
                         Sys.getpid())
      
      json_line <- jsonlite::toJSON(event, auto_unbox = TRUE)
      
      tryCatch({
        write(json_line, file = filename, append = TRUE)
      }, error = function(e) {
        warning(sprintf("Failed to write event to file: %s", e$message))
      })
      
      invisible(NULL)
    }
  )
)

# Helper: NULL coalescing operator
`%||%` <- function(x, y) {
  if (is.null(x)) y else x
}

