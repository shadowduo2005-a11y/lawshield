"""
broker.py – coordinates registry, queue, events, and log memory.
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Callable, List, Optional

from .message import AgentMessage
from .protocol import MessageStatus
from .registry import AgentRegistry
from .queue import AgentMessageQueue
from .events import EventBus
from .memory import MessageMemory

logger = logging.getLogger(__name__)

class MessageBroker:
    """
    Central broker orchestrating agent registration, event pub/sub, message queuing, and logging.
    """
    def __init__(self) -> None:
        self.registry = AgentRegistry()
        self.queue = AgentMessageQueue()
        self.events = EventBus()
        self.memory = MessageMemory()

    def register_agent(self, agent_name: str, handler: Callable[[Dict[str, Any]], Dict[str, Any]], capabilities: Optional[List[str]] = None) -> None:
        """
        Registers an agent with the broker.
        """
        self.registry.register(agent_name, handler, capabilities)

    def send_message(self, message: AgentMessage) -> None:
        """
        Routes and logs an outbound AgentMessage.
        """
        logger.info("Broker routing message %s from %s to %s", message.id, message.sender, message.receiver)
        
        # 1. Record message in logs
        self.memory.record(message)

        # 2. Check if receiver is registered in our dynamic registry
        handler = self.registry.get_handler(message.receiver)
        if handler:
            # Direct queue push
            self.queue.push(message)
        else:
            # Fallback to check if it's a Pub/Sub topic event
            # We assume receivers starting with 'topic:' represent events
            if message.receiver.startswith("topic:"):
                topic = message.receiver.split(":", 1)[1]
                self.events.publish(topic, message)
            else:
                message.status = MessageStatus.FAILED
                message.error = f"Receiver '{message.receiver}' is not registered and is not a valid topic."
                logger.error("Routing failed: %s", message.error)

    def subscribe_to_topic(self, topic: str, callback: Callable[[AgentMessage], None]) -> None:
        """
        Registers a listener for event topics.
        """
        self.events.subscribe(topic, callback)
