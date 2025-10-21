"""
MonitoringSDK - Python
Lightweight TCP-based monitoring instrumentation

Version: 2.0.0
"""

import socket
import json
import time
import threading
from enum import Enum
from typing import Optional, Dict, Any, List
from collections import deque
import random
import string


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
    
    def log_resource(self, cpu_percent: float, memory_mb: float, 
                     disk_io_mb: float, network_io_mb: float) -> bool:
        """Log resource usage"""
        return self._send_message({
            'type': 'resource',
            'data': {
                'cpu': float(cpu_percent),
                'mem': float(memory_mb),
                'disk': float(disk_io_mb),
                'net': float(network_io_mb)
            }
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
    
    def __enter__(self):
        """Context manager support"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.close()
        return False
    
    def __del__(self):
        """Destructor"""
        try:
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

