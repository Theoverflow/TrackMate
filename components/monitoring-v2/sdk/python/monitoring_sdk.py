"""
MonitoringSDK - Python
Lightweight TCP-based monitoring instrumentation

Version: 2.0.0
"""

import socket
import json
import time
import threading
import os
import psutil
from enum import Enum
from typing import Optional, Dict, Any, List
from collections import deque
import random
import string
import multiprocessing
import subprocess


class State(Enum):
    """SDK connection states"""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    OVERFLOW = "overflow"


class MonitoringSDK:
    """
    Lightweight monitoring SDK for Python
    
    Features:
    - TCP socket communication
    - Local buffering (1000 messages)
    - Circuit breaker pattern
    - Automatic reconnection
    - <1ms overhead per call
    
    Example:
        sdk = MonitoringSDK(source='my-service')
        sdk.log_event('info', 'Service started')
        sdk.log_metric('requests_total', 42, 'count')
        sdk.close()
    """
    
    # Constants
    PROTOCOL_VERSION = 1
    MAX_MESSAGE_SIZE = 65536  # 64KB
    MAX_BUFFER_SIZE = 1000
    MAX_RECONNECT_DELAY = 30
    
    def __init__(self, source: str, tcp_host: str = 'localhost', 
                 tcp_port: int = 17000, timeout: float = 5.0, debug: bool = False):
        self.source = source
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.timeout = timeout
        self.debug = debug
        
        # State
        self.state = State.DISCONNECTED
        self.socket: Optional[socket.socket] = None
        self.buffer: deque = deque(maxlen=self.MAX_BUFFER_SIZE)
        self.overflow_count = 0
        self.reconnect_delay = 1.0
        self.last_reconnect = 0
        
        # Context (for tracing)
        self.trace_id: Optional[str] = None
        self.span_id: Optional[str] = None
        self.context: Dict[str, Any] = {}
        
        # Job analysis
        self.job_analysis_enabled = True
        self.job_start_time: Optional[float] = None
        self.job_metrics: Dict[str, Any] = {}
        self.subjob_tracker: Dict[str, Dict[str, Any]] = {}
        
        # Statistics
        self.messages_sent = 0
        self.messages_buffered = 0
        self.messages_dropped = 0
        self.reconnect_count = 0
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Initial connection
        self._connect()
    
    def _connect(self) -> bool:
        """Establish TCP connection"""
        with self._lock:
            # Already connected
            if self.state == State.CONNECTED and self.socket:
                return True
            
            # Throttle reconnection attempts
            now = time.time()
            if now - self.last_reconnect < self.reconnect_delay:
                return False
            
            self.last_reconnect = now
            
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(self.timeout)
                self.socket.connect((self.tcp_host, self.tcp_port))
                
                self.state = State.CONNECTED
                self.reconnect_delay = 1.0  # Reset backoff
                self.reconnect_count += 1
                
                self._log(f"Connected to {self.tcp_host}:{self.tcp_port}")
                
                # Flush buffer
                self._flush_buffer()
                
                return True
            
            except Exception as e:
                self.state = State.DISCONNECTED
                self._log(f"Connection failed: {e}")
                
                # Exponential backoff
                self.reconnect_delay = min(self.reconnect_delay * 2, self.MAX_RECONNECT_DELAY)
                
                if self.socket:
                    try:
                        self.socket.close()
                    except:
                        pass
                    self.socket = None
                
                return False
    
    def _send_message(self, msg: Dict[str, Any]) -> bool:
        """Send message to sidecar"""
        with self._lock:
            # Add protocol fields
            msg['v'] = self.PROTOCOL_VERSION
            msg['src'] = self.source
            msg['ts'] = int(time.time() * 1000)  # Unix millis
            
            # Add trace context if available
            if self.trace_id:
                msg['tid'] = self.trace_id
            if self.span_id:
                msg['sid'] = self.span_id
            
            # Serialize to JSON
            try:
                json_msg = json.dumps(msg, separators=(',', ':'))
                message = (json_msg + '\n').encode('utf-8')
            except Exception as e:
                self._log(f"Serialization error: {e}")
                self.messages_dropped += 1
                return False
            
            # Check message size
            if len(message) > self.MAX_MESSAGE_SIZE:
                self._log(f"Message too large: {len(message)} bytes")
                self.messages_dropped += 1
                return False
            
            # Try to send
            if self.state == State.CONNECTED and self.socket:
                try:
                    self.socket.sendall(message)
                    self.messages_sent += 1
                    return True
                
                except Exception as e:
                    # Send failed, buffer message
                    self.state = State.DISCONNECTED
                    self._log(f"Send failed: {e}")
                    self._buffer_message(msg)
                    self._connect()  # Attempt reconnect
                    return False
            
            else:
                # Not connected, buffer message
                self._buffer_message(msg)
                self._connect()  # Attempt reconnect
                return False
    
    def _buffer_message(self, msg: Dict[str, Any]):
        """Buffer message locally"""
        if len(self.buffer) < self.MAX_BUFFER_SIZE:
            self.buffer.append(msg)
            self.messages_buffered += 1
        else:
            # Buffer overflow
            self.state = State.OVERFLOW
            self.overflow_count += 1
            self.messages_dropped += 1
            
            if self.overflow_count % 100 == 0:
                self._log(f"Buffer overflow! Dropped {self.overflow_count} messages")
    
    def _flush_buffer(self):
        """Flush buffered messages"""
        if self.state != State.CONNECTED or not self.socket:
            return
        
        flushed = 0
        while self.buffer and self.state == State.CONNECTED:
            msg = self.buffer.popleft()
            if self._send_message(msg):
                flushed += 1
            else:
                # Failed, put back
                self.buffer.appendleft(msg)
                break
        
        if flushed > 0:
            self._log(f"Flushed {flushed} buffered messages")
        
        # Reset overflow state if buffer cleared
        if not self.buffer and self.state == State.OVERFLOW:
            self.state = State.CONNECTED
            self.overflow_count = 0
    
    # Public API
    
    def log_event(self, level: str, message: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Log an event"""
        return self._send_message({
            'type': 'event',
            'data': {
                'level': level,
                'msg': message,
                'ctx': context or {}
            }
        })
    
    def log_metric(self, name: str, value: float, unit: str = '', 
                   tags: Optional[Dict[str, str]] = None) -> bool:
        """Log a metric"""
        return self._send_message({
            'type': 'metric',
            'data': {
                'name': name,
                'value': float(value),
                'unit': unit,
                'tags': tags or {}
            }
        })
    
    def log_progress(self, job_id: str, percent: int, status: str = 'running') -> bool:
        """Log job progress"""
        percent = max(0, min(100, int(percent)))
        return self._send_message({
            'type': 'progress',
            'data': {
                'job_id': job_id,
                'percent': percent,
                'status': status
            }
        })
    
    def log_resource(self, cpu_percent: Optional[float] = None, memory_mb: Optional[float] = None, 
                     disk_io_mb: Optional[float] = None, network_io_mb: Optional[float] = None) -> bool:
        """
        Log resource usage
        
        If parameters are not provided, automatically collects current system metrics
        """
        # Auto-collect metrics if not provided
        if cpu_percent is None:
            cpu_percent = psutil.cpu_percent(interval=0.1)
        
        if memory_mb is None:
            mem = psutil.virtual_memory()
            memory_mb = mem.used / (1024 * 1024)  # Convert to MB
        
        if disk_io_mb is None:
            try:
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    # Read + Write in MB
                    disk_io_mb = (disk_io.read_bytes + disk_io.write_bytes) / (1024 * 1024)
                else:
                    disk_io_mb = 0.0
            except:
                disk_io_mb = 0.0
        
        if network_io_mb is None:
            try:
                net_io = psutil.net_io_counters()
                if net_io:
                    # Sent + Received in MB
                    network_io_mb = (net_io.bytes_sent + net_io.bytes_recv) / (1024 * 1024)
                else:
                    network_io_mb = 0.0
            except:
                network_io_mb = 0.0
        
        # Auto-collect metrics if not provided
        if cpu_percent is None:
            cpu_percent = psutil.cpu_percent(interval=0.1)
        
        if memory_mb is None:
            mem = psutil.virtual_memory()
            memory_mb = mem.used / (1024 * 1024)  # Convert to MB
        
        if disk_io_mb is None:
            try:
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    # Read + Write in MB
                    disk_io_mb = (disk_io.read_bytes + disk_io.write_bytes) / (1024 * 1024)
                else:
                    disk_io_mb = 0.0
            except:
                disk_io_mb = 0.0
        
        if network_io_mb is None:
            try:
                net_io = psutil.net_io_counters()
                if net_io:
                    # Sent + Received in MB
                    network_io_mb = (net_io.bytes_sent + net_io.bytes_recv) / (1024 * 1024)
                else:
                    network_io_mb = 0.0
            except:
                network_io_mb = 0.0
        
        # Enhanced resource data with job analysis
        resource_data = {
            'cpu': float(cpu_percent),
            'mem': float(memory_mb),
            'disk': float(disk_io_mb),
            'net': float(network_io_mb),
            'pid': os.getpid()
        }
        
        # Add job analysis if enabled
        if self.job_analysis_enabled:
            job_analysis = self._analyze_current_job()
            resource_data.update(job_analysis)
        
        return self._send_message({
            'type': 'resource',
            'data': resource_data
        })
    
    def start_span(self, name: str, trace_id: Optional[str] = None) -> str:
        """Start a distributed trace span"""
        # Generate span ID
        span_id = self._generate_id()
        
        # Set trace ID if provided
        if trace_id:
            self.trace_id = trace_id
        
        # Generate trace ID if not set
        if not self.trace_id:
            self.trace_id = self._generate_id()
        
        # Store current span as parent
        parent_span_id = self.span_id
        
        # Set new span as current
        self.span_id = span_id
        
        # Send span start event
        msg = {
            'type': 'span',
            'tid': self.trace_id,
            'sid': span_id,
            'data': {
                'name': name,
                'start': int(time.time() * 1000),
                'end': None,
                'status': 'started',
                'tags': {}
            }
        }
        
        if parent_span_id:
            msg['pid'] = parent_span_id
        
        self._send_message(msg)
        return span_id
    
    def end_span(self, span_id: str, status: str = 'success', 
                 tags: Optional[Dict[str, Any]] = None) -> bool:
        """End a distributed trace span"""
        result = self._send_message({
            'type': 'span',
            'tid': self.trace_id,
            'sid': span_id,
            'data': {
                'name': '',
                'start': 0,
                'end': int(time.time() * 1000),
                'status': status,
                'tags': tags or {}
            }
        })
        
        # Clear current span if it matches
        if self.span_id == span_id:
            self.span_id = None
        
        return result
    
    def set_context(self, key: str, value: Any):
        """Set context variable"""
        self.context[key] = value
    
    def set_trace_id(self, trace_id: str):
        """Set trace ID for correlation"""
        self.trace_id = trace_id
    
    def close(self):
        """Close connection and cleanup"""
        with self._lock:
            # Send goodbye message
            if self.state == State.CONNECTED and self.socket:
                try:
                    self._send_message({'type': 'goodbye', 'data': {}})
                except:
                    pass
            
            # Close socket
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
                self.socket = None
            
            self.state = State.DISCONNECTED
            
            self._log(f"Closed. Messages sent: {self.messages_sent}, "
                     f"buffered: {self.messages_buffered}, "
                     f"dropped: {self.messages_dropped}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get SDK statistics"""
        return {
            'source': self.source,
            'state': self.state.value,
            'messages_sent': self.messages_sent,
            'messages_buffered': self.messages_buffered,
            'messages_dropped': self.messages_dropped,
            'buffer_size': len(self.buffer),
            'overflow_count': self.overflow_count,
            'reconnect_count': self.reconnect_count
        }
    
    def _generate_id(self) -> str:
        """Generate random ID"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    
    def _log(self, message: str):
        """Internal logging"""
        if self.debug:
            print(f"[MonitoringSDK] {message}")
    
    # Job Analysis Methods
    
    def start_job_analysis(self, job_name: str, job_type: str = "main") -> str:
        """
        Start analyzing a business job/process
        
        Args:
            job_name: Name of the job/process
            job_type: Type of job (main, subjob, multiprocess)
        
        Returns:
            Job ID for tracking
        """
        job_id = f"{job_name}-{int(time.time())}-{self._generate_id()[:8]}"
        
        self.job_start_time = time.time()
        self.job_metrics = {
            'job_id': job_id,
            'job_name': job_name,
            'job_type': job_type,
            'start_time': self.job_start_time,
            'process_count': 1,
            'thread_count': threading.active_count(),
            'cpu_cores': multiprocessing.cpu_count(),
            'memory_total_mb': psutil.virtual_memory().total / (1024 * 1024),
            'subjobs': []
        }
        
        # Log job start
        self.log_event('info', f'Job analysis started: {job_name}', {
            'job_id': job_id,
            'job_type': job_type,
            'process_count': self.job_metrics['process_count'],
            'thread_count': self.job_metrics['thread_count']
        })
        
        return job_id
    
    def track_subjob(self, subjob_name: str, subjob_type: str = "process") -> str:
        """
        Track a subjob (child process, thread, or task)
        
        Args:
            subjob_name: Name of the subjob
            subjob_type: Type (process, thread, task)
        
        Returns:
            Subjob ID
        """
        subjob_id = f"{subjob_name}-{int(time.time())}-{self._generate_id()[:8]}"
        
        subjob_info = {
            'subjob_id': subjob_id,
            'subjob_name': subjob_name,
            'subjob_type': subjob_type,
            'start_time': time.time(),
            'pid': os.getpid(),
            'parent_pid': os.getppid()
        }
        
        self.subjob_tracker[subjob_id] = subjob_info
        self.job_metrics['subjobs'].append(subjob_info)
        
        # Log subjob start
        self.log_event('info', f'Subjob started: {subjob_name}', {
            'subjob_id': subjob_id,
            'subjob_type': subjob_type,
            'parent_job_id': self.job_metrics.get('job_id', 'unknown')
        })
        
        return subjob_id
    
    def end_subjob(self, subjob_id: str, status: str = "completed"):
        """End tracking a subjob"""
        if subjob_id in self.subjob_tracker:
            subjob_info = self.subjob_tracker[subjob_id]
            subjob_info['end_time'] = time.time()
            subjob_info['duration'] = subjob_info['end_time'] - subjob_info['start_time']
            subjob_info['status'] = status
            
            # Log subjob completion
            self.log_event('info', f'Subjob completed: {subjob_info["subjob_name"]}', {
                'subjob_id': subjob_id,
                'duration': subjob_info['duration'],
                'status': status
            })
            
            del self.subjob_tracker[subjob_id]
    
    def end_job_analysis(self, status: str = "completed"):
        """End job analysis and log summary"""
        if not self.job_start_time:
            return
        
        end_time = time.time()
        total_duration = end_time - self.job_start_time
        
        # Calculate final metrics
        final_metrics = self._analyze_current_job()
        final_metrics.update({
            'end_time': end_time,
            'total_duration': total_duration,
            'status': status,
            'completed_subjobs': len([sj for sj in self.job_metrics['subjobs'] if 'end_time' in sj]),
            'active_subjobs': len(self.subjob_tracker)
        })
        
        # Log job completion
        self.log_event('info', f'Job analysis completed: {self.job_metrics["job_name"]}', final_metrics)
        
        # Log job summary metrics
        self.log_metric('job_duration_seconds', total_duration, 'seconds', {
            'job_name': self.job_metrics['job_name'],
            'job_type': self.job_metrics['job_type'],
            'status': status
        })
        
        self.log_metric('job_subjobs_count', final_metrics['completed_subjobs'], 'count', {
            'job_name': self.job_metrics['job_name'],
            'job_type': self.job_metrics['job_type']
        })
        
        # Reset job tracking
        self.job_start_time = None
        self.job_metrics = {}
        self.subjob_tracker = {}
    
    def _analyze_current_job(self) -> Dict[str, Any]:
        """Analyze current job/process state"""
        analysis = {}
        
        try:
            current_process = psutil.Process()
            
            # Process information
            analysis.update({
                'process_cpu_percent': current_process.cpu_percent(),
                'process_memory_mb': current_process.memory_info().rss / (1024 * 1024),
                'process_threads': current_process.num_threads(),
                'process_fds': current_process.num_fds() if hasattr(current_process, 'num_fds') else 0,
                'process_status': current_process.status()
            })
            
            # Children processes (subjobs)
            children = current_process.children(recursive=True)
            analysis.update({
                'children_count': len(children),
                'children_cpu_total': sum(child.cpu_percent() for child in children),
                'children_memory_total_mb': sum(child.memory_info().rss for child in children) / (1024 * 1024)
            })
            
            # System load
            load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
            analysis.update({
                'load_avg_1m': load_avg[0],
                'load_avg_5m': load_avg[1],
                'load_avg_15m': load_avg[2]
            })
            
            # Job-specific metrics
            if self.job_metrics:
                analysis.update({
                    'job_id': self.job_metrics.get('job_id'),
                    'job_name': self.job_metrics.get('job_name'),
                    'job_type': self.job_metrics.get('job_type'),
                    'job_runtime': time.time() - self.job_start_time if self.job_start_time else 0,
                    'active_subjobs': len(self.subjob_tracker)
                })
            
        except Exception as e:
            if self.debug:
                self._log(f"Job analysis error: {e}")
        
        return analysis
    
    def enable_job_analysis(self, enabled: bool = True):
        """Enable or disable automatic job analysis"""
        self.job_analysis_enabled = enabled
        if enabled:
            self._log("Job analysis enabled")
        else:
            self._log("Job analysis disabled")
    
    def __enter__(self):
        """Context manager support"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        if self.job_start_time:
            self.end_job_analysis("completed" if exc_type is None else "error")
        self.close()
        return False
    
    def __del__(self):
        """Destructor"""
        try:
            if hasattr(self, 'job_start_time') and self.job_start_time:
                self.end_job_analysis("terminated")
            self.close()
        except:
            pass


# Example usage
if __name__ == '__main__':
    # Create SDK
    with MonitoringSDK(source='test-service', debug=True) as sdk:
        # Log events
        sdk.log_event('info', 'Service started')
        sdk.log_event('error', 'Connection failed', {'host': 'db.example.com'})
        
        # Log metrics
        sdk.log_metric('requests_total', 42, 'count')
        sdk.log_metric('response_time_ms', 125.5, 'milliseconds')
        
        # Job progress
        sdk.log_progress('job-123', 50, 'processing')
        
        # Resource usage
        sdk.log_resource(45.2, 2048, 100, 50)
        
        # Distributed tracing
        span_id = sdk.start_span('process_request')
        time.sleep(0.1)
        sdk.end_span(span_id, 'success')
        
        # Show stats
        print(f"Stats: {sdk.get_stats()}")

