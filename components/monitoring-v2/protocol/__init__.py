"""
Monitoring Protocol V2
"""

from .messages import (
    Message,
    MessageType,
    LogLevel,
    EventMessage,
    MetricMessage,
    ProgressMessage,
    ResourceMessage,
    SpanMessage,
    HeartbeatMessage,
    GoodbyeMessage,
    MessageParser
)

__all__ = [
    'Message',
    'MessageType',
    'LogLevel',
    'EventMessage',
    'MetricMessage',
    'ProgressMessage',
    'ResourceMessage',
    'SpanMessage',
    'HeartbeatMessage',
    'GoodbyeMessage',
    'MessageParser'
]

__version__ = '2.0.0'

