"""
protocol.py – defines constant values, routing patterns, enums for agent communication.
"""
from __future__ import annotations

from enum import Enum

class MessagePriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class MessageStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"

class RoutingPattern(str, Enum):
    REQUEST_RESPONSE = "request_response"
    BROADCAST = "broadcast"
    EVENT = "event"
    PIPELINE = "pipeline"
    PARALLEL = "parallel"
