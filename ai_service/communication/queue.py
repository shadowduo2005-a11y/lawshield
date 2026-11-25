"""
queue.py – defines the priority message queue for agent communication.
"""
from __future__ import annotations

import queue
import logging
from typing import Optional

from .message import AgentMessage
from .protocol import MessagePriority

logger = logging.getLogger(__name__)

class AgentMessageQueue:
    """
    Thread-safe Priority Queue for delivering messages between agents.
    """
    def __init__(self) -> None:
        self._queue: queue.PriorityQueue = queue.PriorityQueue()

    def push(self, message: AgentMessage) -> None:
        """
        Pushes a message onto the queue according to its priority score.
        """
        # Map priority string to integer value where lower means higher priority
        priority_map = {
            MessagePriority.HIGH: 0,
            MessagePriority.MEDIUM: 1,
            MessagePriority.LOW: 2
        }
        priority_val = priority_map.get(message.priority, 1)
        
        # PriorityQueue elements are sorted by the first element of the tuple
        # To avoid comparing AgentMessage itself, we include timestamp and ID
        self._queue.put((priority_val, message.timestamp, message.id, message))
        logger.info("Message %s pushed to queue (Priority: %s)", message.id, message.priority)

    def pop(self, block: bool = True, timeout: Optional[float] = None) -> Optional[AgentMessage]:
        """
        Retrieves a message from the queue. Blocks by default.
        """
        try:
            _, _, _, msg = self._queue.get(block=block, timeout=timeout)
            return msg
        except queue.Empty:
            return None

    def size(self) -> int:
        """
        Returns the number of messages currently in the queue.
        """
        return self._queue.qsize()
