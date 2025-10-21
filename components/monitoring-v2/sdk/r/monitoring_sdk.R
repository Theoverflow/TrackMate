# MonitoringSDK - R
# Lightweight TCP-based monitoring instrumentation
# Version: 2.0.0

library(R6)

#' MonitoringSDK Class
#' 
#' @description
#' Lightweight monitoring SDK for R using TCP socket communication
#' 
#' @details
#' Features:
#' - TCP socket communication
#' - Local buffering (1000 messages)
#' - Circuit breaker pattern
#' - Automatic reconnection
#' - <1ms overhead per call
#' 
#' @examples
#' \dontrun{
#' sdk <- MonitoringSDK$new(source = "my-r-service")
#' sdk$log_event("info", "Service started")
#' sdk$log_metric("requests_total", 42, "count")
#' sdk$close()
#' }
#' 
#' @export
MonitoringSDK <- R6Class("MonitoringSDK",
  public = list(
    #' @field source Source identifier
    source = NULL,
    
    #' @field tcp_host TCP host
    tcp_host = NULL,
    
    #' @field tcp_port TCP port
    tcp_port = NULL,
    
    #' @field debug Debug mode
    debug = FALSE,
    
    #' @description Create a new MonitoringSDK instance
    #' @param source Source identifier (service/script name)
    #' @param tcp_host TCP host (default: "localhost")
    #' @param tcp_port TCP port (default: 17000)
    #' @param timeout Connection timeout in seconds (default: 5)
    #' @param debug Enable debug logging (default: FALSE)
    initialize = function(source, tcp_host = "localhost", tcp_port = 17000, 
                         timeout = 5, debug = FALSE) {
      if (missing(source) || is.null(source) || source == "") {
        stop("source is required")
      }
      
      self$source <- source
      self$tcp_host <- tcp_host
      self$tcp_port <- tcp_port
      self$debug <- debug
      
      private$.timeout <- timeout
      private$.state <- "disconnected"
      private$.socket <- NULL
      private$.buffer <- list()
      private$.overflow_count <- 0
      private$.reconnect_delay <- 1.0
      private$.last_reconnect <- 0
      
      # Context
      private$.trace_id <- NULL
      private$.span_id <- NULL
      private$.context <- list()
      
      # Job analysis
      private$.job_analysis_enabled <- TRUE
      private$.job_start_time <- NULL
      private$.job_metrics <- list()
      private$.subjob_tracker <- list()
      
      # Statistics
      private$.messages_sent <- 0
      private$.messages_buffered <- 0
      private$.messages_dropped <- 0
      private$.reconnect_count <- 0
      
      # Initial connection
      private$connect()
    },
    
    #' @description Log an event
    #' @param level Log level (debug, info, warn, error, fatal)
    #' @param message Event message
    #' @param context Optional context list
    log_event = function(level, message, context = list()) {
      private$send_message(list(
        type = "event",
        data = list(
          level = level,
          msg = message,
          ctx = context
        )
      ))
    },
    
    #' @description Log a metric
    #' @param name Metric name
    #' @param value Metric value
    #' @param unit Unit of measurement
    #' @param tags Optional tags list
    log_metric = function(name, value, unit = "", tags = list()) {
      private$send_message(list(
        type = "metric",
        data = list(
          name = name,
          value = as.numeric(value),
          unit = unit,
          tags = tags
        )
      ))
    },
    
    #' @description Log job progress
    #' @param job_id Job identifier
    #' @param percent Completion percentage (0-100)
    #' @param status Status description
    log_progress = function(job_id, percent, status = "running") {
      percent <- max(0, min(100, as.integer(percent)))
      
      private$send_message(list(
        type = "progress",
        data = list(
          job_id = job_id,
          percent = percent,
          status = status
        )
      ))
    },
    
    #' @description Log resource usage
    #' @param cpu_percent CPU usage percentage (NULL for auto)
    #' @param memory_mb Memory usage in MB (NULL for auto)
    #' @param disk_io_mb Disk I/O in MB (NULL for auto)
    #' @param network_io_mb Network I/O in MB (NULL for auto)
    log_resource = function(cpu_percent = NULL, memory_mb = NULL, disk_io_mb = NULL, network_io_mb = NULL) {
      # Auto-collect metrics if not provided
      if (is.null(cpu_percent))    cpu_percent <- private$get_cpu_percent()
      if (is.null(memory_mb))      memory_mb <- private$get_memory_mb()
      if (is.null(disk_io_mb))     disk_io_mb <- private$get_disk_io_mb()
      if (is.null(network_io_mb))  network_io_mb <- private$get_network_io_mb()
      
      # Enhanced resource data with job analysis
      resource_data <- list(
        cpu = as.numeric(cpu_percent),
        mem = as.numeric(memory_mb),
        disk = as.numeric(disk_io_mb),
        net = as.numeric(network_io_mb),
        pid = Sys.getpid()
      )
      
      # Add job analysis if enabled
      if (private$.job_analysis_enabled) {
        job_analysis <- private$analyze_current_job()
        resource_data <- c(resource_data, job_analysis)
      }
      
      private$send_message(list(
        type = "resource",
        data = resource_data
      ))
    },
    
    #' @description Start a distributed trace span
    #' @param name Span name
    #' @param trace_id Optional trace ID (NULL to generate)
    #' @return Span ID
    start_span = function(name, trace_id = NULL) {
      # Generate span ID
      span_id <- private$generate_id()
      
      # Set trace ID if provided
      if (!is.null(trace_id)) {
        private$.trace_id <- trace_id
      }
      
      # Generate trace ID if not set
      if (is.null(private$.trace_id)) {
        private$.trace_id <- private$generate_id()
      }
      
      # Store current span as parent
      parent_span_id <- private$.span_id
      
      # Set new span as current
      private$.span_id <- span_id
      
      # Send span start event
      msg <- list(
        type = "span",
        tid = private$.trace_id,
        sid = span_id,
        data = list(
          name = name,
          start = as.numeric(Sys.time()) * 1000,
          end = NULL,
          status = "started",
          tags = list()
        )
      )
      
      if (!is.null(parent_span_id)) {
        msg$pid <- parent_span_id
      }
      
      private$send_message(msg)
      
      return(span_id)
    },
    
    #' @description End a distributed trace span
    #' @param span_id Span ID from start_span
    #' @param status Span status (default: "success")
    #' @param tags Optional tags list
    end_span = function(span_id, status = "success", tags = list()) {
      private$send_message(list(
        type = "span",
        tid = private$.trace_id,
        sid = span_id,
        data = list(
          name = "",
          start = 0,
          end = as.numeric(Sys.time()) * 1000,
          status = status,
          tags = tags
        )
      ))
      
      # Clear current span if it matches
      if (!is.null(private$.span_id) && private$.span_id == span_id) {
        private$.span_id <- NULL
      }
    },
    
    #' @description Set trace ID for correlation
    #' @param trace_id Trace ID
    set_trace_id = function(trace_id) {
      private$.trace_id <- trace_id
    },
    
    #' @description Set context variable
    #' @param key Context key
    #' @param value Context value
    set_context = function(key, value) {
      private$.context[[key]] <- value
    },
    
    #' @description Get SDK statistics
    #' @return List of statistics
    get_stats = function() {
      list(
        source = self$source,
        state = private$.state,
        messages_sent = private$.messages_sent,
        messages_buffered = private$.messages_buffered,
        messages_dropped = private$.messages_dropped,
        buffer_size = length(private$.buffer),
        overflow_count = private$.overflow_count,
        reconnect_count = private$.reconnect_count
      )
    },
    
    # Job Analysis Methods
    
    #' @description Start analyzing a business job/process
    #' @param job_name Name of the job/process
    #' @param job_type Type of job (main, subjob, multiprocess)
    #' @return Job ID for tracking
    start_job_analysis = function(job_name, job_type = "main") {
      job_id <- paste0(job_name, "-", as.integer(Sys.time()), "-", private$generate_id())
      job_id <- substr(job_id, 1, 32)  # Truncate to 32 chars
      
      private$.job_start_time <- Sys.time()
      private$.job_metrics <- list(
        job_id = job_id,
        job_name = job_name,
        job_type = job_type,
        start_time = private$.job_start_time,
        process_count = 1,
        thread_count = 1,  # R doesn't have easy thread counting
        cpu_cores = parallel::detectCores(),
        memory_total_mb = private$get_total_memory_mb(),
        subjobs = list()
      )
      
      # Log job start
      self$log_event("info", paste("Job analysis started:", job_name), list(
        job_id = job_id,
        job_type = job_type,
        process_count = private$.job_metrics$process_count,
        thread_count = private$.job_metrics$thread_count
      ))
      
      return(job_id)
    },
    
    #' @description Track a subjob (child process, thread, or task)
    #' @param subjob_name Name of the subjob
    #' @param subjob_type Type (process, thread, task)
    #' @return Subjob ID
    track_subjob = function(subjob_name, subjob_type = "process") {
      subjob_id <- paste0(subjob_name, "-", as.integer(Sys.time()), "-", private$generate_id())
      subjob_id <- substr(subjob_id, 1, 32)  # Truncate to 32 chars
      
      subjob_info <- list(
        subjob_id = subjob_id,
        subjob_name = subjob_name,
        subjob_type = subjob_type,
        start_time = Sys.time(),
        pid = Sys.getpid(),
        parent_pid = Sys.getpid()  # R doesn't have easy parent PID access
      )
      
      private$.subjob_tracker[[subjob_id]] <- subjob_info
      private$.job_metrics$subjobs <- append(private$.job_metrics$subjobs, list(subjob_info))
      
      # Log subjob start
      self$log_event("info", paste("Subjob started:", subjob_name), list(
        subjob_id = subjob_id,
        subjob_type = subjob_type,
        parent_job_id = private$.job_metrics$job_id %||% "unknown"
      ))
      
      return(subjob_id)
    },
    
    #' @description End tracking a subjob
    #' @param subjob_id Subjob ID returned by track_subjob
    #' @param status Completion status
    end_subjob = function(subjob_id, status = "completed") {
      if (subjob_id %in% names(private$.subjob_tracker)) {
        subjob_info <- private$.subjob_tracker[[subjob_id]]
        subjob_info$end_time <- Sys.time()
        subjob_info$duration <- as.numeric(subjob_info$end_time - subjob_info$start_time, units = "secs")
        subjob_info$status <- status
        
        # Log subjob completion
        self$log_event("info", paste("Subjob completed:", subjob_info$subjob_name), list(
          subjob_id = subjob_id,
          duration = subjob_info$duration,
          status = status
        ))
        
        private$.subjob_tracker[[subjob_id]] <- NULL
      }
    },
    
    #' @description End job analysis and log summary
    #' @param status Completion status
    end_job_analysis = function(status = "completed") {
      if (is.null(private$.job_start_time)) {
        return(invisible())
      }
      
      end_time <- Sys.time()
      total_duration <- as.numeric(end_time - private$.job_start_time, units = "secs")
      
      # Calculate final metrics
      final_metrics <- private$analyze_current_job()
      final_metrics$end_time <- end_time
      final_metrics$total_duration <- total_duration
      final_metrics$status <- status
      final_metrics$completed_subjobs <- length(Filter(function(sj) !is.null(sj$end_time), private$.job_metrics$subjobs))
      final_metrics$active_subjobs <- length(private$.subjob_tracker)
      
      # Log job completion
      self$log_event("info", paste("Job analysis completed:", private$.job_metrics$job_name), final_metrics)
      
      # Log job summary metrics
      self$log_metric("job_duration_seconds", total_duration, "seconds", list(
        job_name = private$.job_metrics$job_name,
        job_type = private$.job_metrics$job_type,
        status = status
      ))
      
      self$log_metric("job_subjobs_count", final_metrics$completed_subjobs, "count", list(
        job_name = private$.job_metrics$job_name,
        job_type = private$.job_metrics$job_type
      ))
      
      # Reset job tracking
      private$.job_start_time <- NULL
      private$.job_metrics <- list()
      private$.subjob_tracker <- list()
    },
    
    #' @description Enable or disable automatic job analysis
    #' @param enabled TRUE to enable, FALSE to disable
    enable_job_analysis = function(enabled = TRUE) {
      private$.job_analysis_enabled <- enabled
      if (enabled) {
        private$log("Job analysis enabled")
      } else {
        private$log("Job analysis disabled")
      }
    },
    
    #' @description Close connection and cleanup
    close = function() {
      # Send goodbye message
      if (private$.state == "connected" && !is.null(private$.socket)) {
        tryCatch({
          private$send_message(list(type = "goodbye", data = list()))
        }, error = function(e) {})
      }
      
      # Close socket
      if (!is.null(private$.socket)) {
        tryCatch({
          close(private$.socket)
        }, error = function(e) {})
        private$.socket <- NULL
      }
      
      private$.state <- "disconnected"
      
      if (self$debug) {
        message(sprintf("[MonitoringSDK] Closed. Messages sent: %d, buffered: %d, dropped: %d",
                       private$.messages_sent, private$.messages_buffered, private$.messages_dropped))
      }
    }
  ),
  
  private = list(
    .timeout = NULL,
    .state = NULL,
    .socket = NULL,
    .buffer = NULL,
    .overflow_count = NULL,
    .reconnect_delay = NULL,
    .last_reconnect = NULL,
    
    .trace_id = NULL,
    .span_id = NULL,
    .context = NULL,
    
    .messages_sent = NULL,
    .messages_buffered = NULL,
    .messages_dropped = NULL,
    .reconnect_count = NULL,
    
    MAX_BUFFER_SIZE = 1000,
    MAX_MESSAGE_SIZE = 65536,
    MAX_RECONNECT_DELAY = 30,
    
    connect = function() {
      # Already connected
      if (private$.state == "connected" && !is.null(private$.socket)) {
        return(TRUE)
      }
      
      # Throttle reconnection attempts
      now <- as.numeric(Sys.time())
      if (now - private$.last_reconnect < private$.reconnect_delay) {
        return(FALSE)
      }
      private$.last_reconnect <- now
      
      tryCatch({
        private$.socket <- socketConnection(
          host = self$tcp_host,
          port = self$tcp_port,
          blocking = FALSE,
          open = "w+b",
          timeout = private$.timeout
        )
        
        private$.state <- "connected"
        private$.reconnect_delay <- 1.0
        private$.reconnect_count <- private$.reconnect_count + 1
        
        if (self$debug) {
          message(sprintf("[MonitoringSDK] Connected to %s:%d", self$tcp_host, self$tcp_port))
        }
        
        # Flush buffer
        private$flush_buffer()
        
        return(TRUE)
        
      }, error = function(e) {
        private$.state <- "disconnected"
        
        if (self$debug) {
          message(sprintf("[MonitoringSDK] Connection failed: %s", e$message))
        }
        
        # Exponential backoff
        private$.reconnect_delay <- min(private$.reconnect_delay * 2, private$MAX_RECONNECT_DELAY)
        
        if (!is.null(private$.socket)) {
          tryCatch(close(private$.socket), error = function(e) {})
          private$.socket <- NULL
        }
        
        return(FALSE)
      })
    },
    
    send_message = function(msg) {
      # Add protocol fields
      msg$v <- 1
      msg$src <- self$source
      msg$ts <- as.numeric(Sys.time()) * 1000  # Unix millis
      
      # Add trace context if available
      if (!is.null(private$.trace_id)) {
        msg$tid <- private$.trace_id
      }
      if (!is.null(private$.span_id)) {
        msg$sid <- private$.span_id
      }
      
      # Serialize to JSON
      json_msg <- tryCatch({
        jsonlite::toJSON(msg, auto_unbox = TRUE)
      }, error = function(e) {
        if (self$debug) {
          message(sprintf("[MonitoringSDK] Serialization error: %s", e$message))
        }
        private$.messages_dropped <- private$.messages_dropped + 1
        return(NULL)
      })
      
      if (is.null(json_msg)) {
        return(FALSE)
      }
      
      message_str <- paste0(json_msg, "\n")
      
      # Check message size
      if (nchar(message_str) > private$MAX_MESSAGE_SIZE) {
        if (self$debug) {
          message(sprintf("[MonitoringSDK] Message too large: %d bytes", nchar(message_str)))
        }
        private$.messages_dropped <- private$.messages_dropped + 1
        return(FALSE)
      }
      
      # Try to send
      if (private$.state == "connected" && !is.null(private$.socket)) {
        tryCatch({
          writeLines(message_str, private$.socket, sep = "")
          flush(private$.socket)
          private$.messages_sent <- private$.messages_sent + 1
          return(TRUE)
        }, error = function(e) {
          private$.state <- "disconnected"
          if (self$debug) {
            message(sprintf("[MonitoringSDK] Send failed: %s", e$message))
          }
          private$buffer_message(msg)
          private$connect()
          return(FALSE)
        })
      } else {
        # Not connected, buffer message
        private$buffer_message(msg)
        private$connect()
        return(FALSE)
      }
    },
    
    buffer_message = function(msg) {
      if (length(private$.buffer) < private$MAX_BUFFER_SIZE) {
        private$.buffer[[length(private$.buffer) + 1]] <- msg
        private$.messages_buffered <- private$.messages_buffered + 1
      } else {
        # Buffer overflow
        private$.state <- "overflow"
        private$.overflow_count <- private$.overflow_count + 1
        private$.messages_dropped <- private$.messages_dropped + 1
        
        if (private$.overflow_count %% 100 == 0 && self$debug) {
          message(sprintf("[MonitoringSDK] Buffer overflow! Dropped %d messages",
                         private$.overflow_count))
        }
      }
    },
    
    flush_buffer = function() {
      if (private$.state != "connected" || is.null(private$.socket)) {
        return()
      }
      
      flushed <- 0
      while (length(private$.buffer) > 0 && private$.state == "connected") {
        msg <- private$.buffer[[1]]
        private$.buffer[[1]] <- NULL
        
        if (private$send_message(msg)) {
          flushed <- flushed + 1
        } else {
          # Failed, put back
          private$.buffer <- c(list(msg), private$.buffer)
          break
        }
      }
      
      if (flushed > 0 && self$debug) {
        message(sprintf("[MonitoringSDK] Flushed %d buffered messages", flushed))
      }
      
      # Reset overflow state if buffer cleared
      if (length(private$.buffer) == 0 && private$.state == "overflow") {
        private$.state <- "connected"
        private$.overflow_count <- 0
      }
    },
    
    generate_id = function() {
      # Generate random 16-character ID
      paste0(sample(c(letters, LETTERS, 0:9), 16, replace = TRUE), collapse = "")
    },
    
    # Auto-collect CPU usage percentage
    get_cpu_percent = function() {
      tryCatch({
        if (file.exists("/proc/stat")) {
          lines <- readLines("/proc/stat", n = 1)
          vals <- as.numeric(strsplit(lines, "\\s+")[[1]][-1])
          if (length(vals) >= 4) {
            user <- vals[1]; nice <- vals[2]; system <- vals[3]; idle <- vals[4]
            total <- user + nice + system + idle
            used <- user + nice + system
            return(if (total > 0) (used / total) * 100 else 0)
          }
        }
        # Fallback: try system command
        cpu_info <- system("top -bn1 | grep 'Cpu(s)'", intern = TRUE)
        if (length(cpu_info) > 0) {
          # Parse CPU idle and calculate used
          idle <- as.numeric(sub(".*?([0-9.]+)%?.*id.*", "\\1", cpu_info[1]))
          return(100 - idle)
        }
        return(0)
      }, error = function(e) 0)
    },
    
    # Auto-collect memory usage in MB
    get_memory_mb = function() {
      tryCatch({
        if (file.exists("/proc/meminfo")) {
          lines <- readLines("/proc/meminfo")
          mem_total <- as.numeric(sub("MemTotal:\\s+(\\d+).*", "\\1", grep("MemTotal", lines, value = TRUE)))
          mem_available <- as.numeric(sub("MemAvailable:\\s+(\\d+).*", "\\1", grep("MemAvailable", lines, value = TRUE)))
          if (length(mem_total) > 0 && length(mem_available) > 0) {
            used_kb <- mem_total - mem_available
            return(used_kb / 1024)  # Convert to MB
          }
        }
        # Fallback: try free command
        mem_info <- system("free -m | grep Mem", intern = TRUE)
        if (length(mem_info) > 0) {
          vals <- as.numeric(strsplit(mem_info, "\\s+")[[1]])
          if (length(vals) >= 3) return(vals[3])  # Used memory
        }
        return(0)
      }, error = function(e) 0)
    },
    
    # Auto-collect disk I/O in MB
    get_disk_io_mb = function() {
      tryCatch({
        if (file.exists("/proc/diskstats")) {
          lines <- readLines("/proc/diskstats")
          total_sectors <- 0
          for (line in lines) {
            parts <- strsplit(trimws(line), "\\s+")[[1]]
            if (length(parts) >= 10) {
              read_sectors <- as.numeric(parts[6])
              write_sectors <- as.numeric(parts[10])
              total_sectors <- total_sectors + read_sectors + write_sectors
            }
          }
          # Convert sectors to MB (sector = 512 bytes)
          return((total_sectors * 512) / (1024 * 1024))
        }
        return(0)
      }, error = function(e) 0)
    },
    
    # Auto-collect network I/O in MB
    get_network_io_mb = function() {
      tryCatch({
        if (file.exists("/proc/net/dev")) {
          lines <- readLines("/proc/net/dev")
          total_bytes <- 0
          for (line in lines[-(1:2)]) {  # Skip header lines
            parts <- strsplit(trimws(line), "\\s+")[[1]]
            if (length(parts) >= 10) {
              # RX bytes (column 2) + TX bytes (column 10)
              rx_bytes <- as.numeric(sub(".*:", "", parts[1]))
              if (!is.na(rx_bytes)) {
                tx_bytes <- as.numeric(parts[9])
                total_bytes <- total_bytes + rx_bytes + tx_bytes
              }
            }
          }
          return(total_bytes / (1024 * 1024))  # Convert to MB
        }
        return(0)
      }, error = function(e) 0)
    },
    
    # Job analysis private methods
    analyze_current_job = function() {
      analysis <- list()
      
      tryCatch({
        # Process information
        analysis$process_cpu_percent <- private$get_cpu_percent()
        analysis$process_memory_mb <- private$get_memory_mb()
        analysis$process_threads <- 1  # R doesn't have easy thread counting
        analysis$process_fds <- 0      # Not easily available in R
        analysis$process_status <- "running"
        
        # Children processes (subjobs) - simplified for R
        analysis$children_count <- 0  # Would need more complex logic
        analysis$children_cpu_total <- 0
        analysis$children_memory_total_mb <- 0
        
        # System load
        load_avg <- private$get_load_average()
        analysis$load_avg_1m <- load_avg[1] %||% 0
        analysis$load_avg_5m <- load_avg[2] %||% 0
        analysis$load_avg_15m <- load_avg[3] %||% 0
        
        # Job-specific metrics
        if (length(private$.job_metrics) > 0) {
          analysis$job_id <- private$.job_metrics$job_id
          analysis$job_name <- private$.job_metrics$job_name
          analysis$job_type <- private$.job_metrics$job_type
          analysis$job_runtime <- as.numeric(Sys.time() - private$.job_start_time, units = "secs") %||% 0
          analysis$active_subjobs <- length(private$.subjob_tracker)
        }
      }, error = function(e) {
        if (private$.debug) {
          private$log(paste("Job analysis error:", e$message))
        }
      })
      
      return(analysis)
    },
    
    get_total_memory_mb = function() {
      tryCatch({
        if (file.exists("/proc/meminfo")) {
          lines <- readLines("/proc/meminfo")
          for (line in lines) {
            if (grepl("^MemTotal:", line)) {
              mem_kb <- as.numeric(gsub("^MemTotal:\\s+(\\d+).*", "\\1", line))
              return(mem_kb / 1024)  # Convert KB to MB
            }
          }
        }
        return(1024)  # Fallback
      }, error = function(e) 1024)
    },
    
    get_load_average = function() {
      tryCatch({
        if (file.exists("/proc/loadavg")) {
          line <- readLines("/proc/loadavg", n = 1)
          parts <- strsplit(line, "\\s+")[[1]]
          if (length(parts) >= 3) {
            return(c(as.numeric(parts[1]), as.numeric(parts[2]), as.numeric(parts[3])))
          }
        }
        return(c(0, 0, 0))  # Fallback
      }, error = function(e) c(0, 0, 0))
    }
  ),
  
  active = list(
    #' @field connected Check if connected
    connected = function() {
      private$.state == "connected"
    }
  )
)

# Example usage
if (FALSE) {
  # Create SDK
  sdk <- MonitoringSDK$new(source = "test-r-service", debug = TRUE)
  
  # Log events
  sdk$log_event("info", "Service started")
  sdk$log_event("error", "Connection failed", list(host = "db.example.com"))
  
  # Log metrics
  sdk$log_metric("requests_total", 42, "count")
  sdk$log_metric("response_time_ms", 125.5, "milliseconds")
  
  # Job progress
  sdk$log_progress("job-123", 50, "processing")
  
  # Resource usage
  sdk$log_resource(45.2, 2048, 100, 50)
  
  # Distributed tracing
  span_id <- sdk$start_span("process_request")
  Sys.sleep(0.1)
  sdk$end_span(span_id, "success")
  
  # Show stats
  print(sdk$get_stats())
  
  # Cleanup
  sdk$close()
}

