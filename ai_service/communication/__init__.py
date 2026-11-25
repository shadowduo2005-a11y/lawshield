"""
communication package init.
Exposes protocol, messaging model, broker, queue, registry, dispatcher, and routing patterns.
"""
from .protocol import MessagePriority, MessageStatus, RoutingPattern
from .message import AgentMessage
from .registry import AgentRegistry, VALID_AGENTS
from .queue import AgentMessageQueue
from .events import EventBus
from .memory import MessageMemory
from .broker import MessageBroker
from .dispatcher import MessageDispatcher
from .router import run_pipeline, run_parallel

__all__ = [
    "MessagePriority",
    "MessageStatus",
    "RoutingPattern",
    "AgentMessage",
    "AgentRegistry",
    "VALID_AGENTS",
    "AgentMessageQueue",
    "EventBus",
    "MessageMemory",
    "MessageBroker",
    "MessageDispatcher",
    "run_pipeline",
    "run_parallel",
]
