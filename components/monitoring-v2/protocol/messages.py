"""
Wire Protocol Message Definitions
Version: 2.0.0

Line-delimited JSON (LDJSON) format for high-performance streaming.
"""

from enum import Enum
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import json


class MessageType(str, Enum):
    """Message types supported by the protocol"""
    EVENT = "event"
    METRIC = "metric"
    PROGRESS = "progress"
    RESOURCE = "resource"
    SPAN = "span"
    HEARTBEAT = "heartbeat"
    GOODBYE = "goodbye"


class LogLevel(str, Enum):
    """Log levels for event messages"""
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"


@dataclass
class Message:
    """Base message structure"""
    v: int  # Protocol version
    src: str  # Source name (service/script)
    ts: int  # Timestamp (unix millis)
    type: str  # Message type
    tid: Optional[str] = None  # Trace ID
    sid: Optional[str] = None  # Span ID
    pid: Optional[str] = None  # Parent span ID
    data: Optional[Dict[str, Any]] = None  # Payload
    
    def to_json(self) -> str:
        """Serialize to JSON string"""
        return json.dumps(asdict(self), separators=(',', ':'))
    
    def to_ldjson(self) -> str:
        """Serialize to line-delimited JSON (with newline)"""
        return self.to_json() + '\n'
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Deserialize from JSON string"""
        data = json.loads(json_str)
        return cls(**data)
    
    @classmethod
    def from_ldjson(cls, ldjson_str: str) -> 'Message':
        """Deserialize from line-delimited JSON"""
        return cls.from_json(ldjson_str.rstrip('\n'))


@dataclass
class EventMessage(Message):
    """Log event message"""
    
    @staticmethod
    def create(
        source: str,
        level: LogLevel,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None
    ) -> 'EventMessage':
        return EventMessage(
            v=1,
            src=source,
            ts=int(datetime.now().timestamp() * 1000),
            type=MessageType.EVENT,
            tid=trace_id,
            sid=span_id,
            data={
                'level': level,
                'msg': message,
                'ctx': context or {}
            }
        )


@dataclass
class MetricMessage(Message):
    """Metric message"""
    
    @staticmethod
    def create(
        source: str,
        name: str,
        value: Union[int, float],
        unit: str,
        tags: Optional[Dict[str, str]] = None,
        trace_id: Optional[str] = None
    ) -> 'MetricMessage':
        return MetricMessage(
            v=1,
            src=source,
            ts=int(datetime.now().timestamp() * 1000),
            type=MessageType.METRIC,
            tid=trace_id,
            data={
                'name': name,
                'value': value,
                'unit': unit,
                'tags': tags or {}
            }
        )


@dataclass
class ProgressMessage(Message):
    """Job progress message"""
    
    @staticmethod
    def create(
        source: str,
        job_id: str,
        percent: int,
        status: str,
        trace_id: Optional[str] = None
    ) -> 'ProgressMessage':
        return ProgressMessage(
            v=1,
            src=source,
            ts=int(datetime.now().timestamp() * 1000),
            type=MessageType.PROGRESS,
            tid=trace_id,
            data={
                'job_id': job_id,
                'percent': percent,
                'status': status
            }
        )


@dataclass
class ResourceMessage(Message):
    """Resource usage message"""
    
    @staticmethod
    def create(
        source: str,
        cpu_percent: float,
        memory_mb: float,
        disk_io_mb: float,
        network_io_mb: float,
        trace_id: Optional[str] = None
    ) -> 'ResourceMessage':
        return ResourceMessage(
            v=1,
            src=source,
            ts=int(datetime.now().timestamp() * 1000),
            type=MessageType.RESOURCE,
            tid=trace_id,
            data={
                'cpu': cpu_percent,
                'mem': memory_mb,
                'disk': disk_io_mb,
                'net': network_io_mb
            }
        )


@dataclass
class SpanMessage(Message):
    """Distributed tracing span message"""
    
    @staticmethod
    def create(
        source: str,
        span_id: str,
        trace_id: str,
        parent_span_id: Optional[str],
        name: str,
        start_time: int,
        end_time: Optional[int],
        status: str,
        tags: Optional[Dict[str, Any]] = None
    ) -> 'SpanMessage':
        return SpanMessage(
            v=1,
            src=source,
            ts=int(datetime.now().timestamp() * 1000),
            type=MessageType.SPAN,
            tid=trace_id,
            sid=span_id,
            pid=parent_span_id,
            data={
                'name': name,
                'start': start_time,
                'end': end_time,
                'status': status,
                'tags': tags or {}
            }
        )


@dataclass
class HeartbeatMessage(Message):
    """Heartbeat/keepalive message"""
    
    @staticmethod
    def create(source: str) -> 'HeartbeatMessage':
        return HeartbeatMessage(
            v=1,
            src=source,
            ts=int(datetime.now().timestamp() * 1000),
            type=MessageType.HEARTBEAT,
            data={}
        )


@dataclass
class GoodbyeMessage(Message):
    """Goodbye message (graceful disconnect)"""
    
    @staticmethod
    def create(source: str) -> 'GoodbyeMessage':
        return GoodbyeMessage(
            v=1,
            src=source,
            ts=int(datetime.now().timestamp() * 1000),
            type=MessageType.GOODBYE,
            data={}
        )


class MessageParser:
    """Parse and validate messages"""
    
    MAX_MESSAGE_SIZE = 64 * 1024  # 64KB
    
    @staticmethod
    def parse(line: str) -> Optional[Message]:
        """
        Parse a line-delimited JSON message
        
        Returns:
            Message object or None if invalid
        """
        line = line.strip()
        
        if not line:
            return None
        
        if len(line) > MessageParser.MAX_MESSAGE_SIZE:
            raise ValueError(f"Message exceeds max size: {len(line)} > {MessageParser.MAX_MESSAGE_SIZE}")
        
        try:
            data = json.loads(line)
            
            # Validate required fields
            if 'v' not in data or 'src' not in data or 'ts' not in data or 'type' not in data:
                raise ValueError("Missing required fields")
            
            # Validate protocol version
            if data['v'] != 1:
                raise ValueError(f"Unsupported protocol version: {data['v']}")
            
            # Validate message type
            if data['type'] not in [t.value for t in MessageType]:
                raise ValueError(f"Unknown message type: {data['type']}")
            
            return Message(**data)
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        except Exception as e:
            raise ValueError(f"Parse error: {e}")
    
    @staticmethod
    def validate_message(msg: Message) -> bool:
        """Validate message structure"""
        # Check required fields
        if not msg.src or not msg.type:
            return False
        
        # Check timestamp is reasonable
        now = int(datetime.now().timestamp() * 1000)
        if msg.ts > now + 60000:  # Not more than 1 minute in future
            return False
        if msg.ts < now - 86400000:  # Not more than 1 day in past
            return False
        
        # Type-specific validation
        if msg.type == MessageType.EVENT:
            if not msg.data or 'level' not in msg.data or 'msg' not in msg.data:
                return False
        
        elif msg.type == MessageType.METRIC:
            if not msg.data or 'name' not in msg.data or 'value' not in msg.data:
                return False
        
        elif msg.type == MessageType.PROGRESS:
            if not msg.data or 'job_id' not in msg.data or 'percent' not in msg.data:
                return False
            if not 0 <= msg.data['percent'] <= 100:
                return False
        
        elif msg.type == MessageType.SPAN:
            if not msg.tid or not msg.sid:
                return False
        
        return True


# Example usage and tests
if __name__ == '__main__':
    # Create messages
    event = EventMessage.create(
        source='test-service',
        level=LogLevel.INFO,
        message='Test event',
        context={'user_id': '12345'}
    )
    print("Event:", event.to_ldjson())
    
    metric = MetricMessage.create(
        source='test-service',
        name='requests_total',
        value=42,
        unit='count',
        tags={'endpoint': '/api/users'}
    )
    print("Metric:", metric.to_ldjson())
    
    # Parse message
    parser = MessageParser()
    parsed = parser.parse(event.to_json())
    print("Parsed:", parsed)
    
    # Validate
    is_valid = parser.validate_message(parsed)
    print("Valid:", is_valid)

