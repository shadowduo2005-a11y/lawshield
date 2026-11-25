"""
events.py – implements Publish-Subscribe patterns and event dispatch buses.
"""
from __future__ import annotations

import logging
import threading
from typing import Dict, List, Callable, Optional

from .message import AgentMessage

logger = logging.getLogger(__name__)

class EventBus:
    """
    Thread-safe Publish-Subscribe Bus for event-driven agent routing.
    """
    _instance: Optional[EventBus] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls, *args, **kwargs)
                cls._instance._subscribers = {}
                cls._instance._subscribers_lock = threading.Lock()
        return cls._instance

    def subscribe(self, topic: str, callback: Callable[[AgentMessage], None]) -> None:
        """
        Subscribes a callback handler to a given topic.
        """
        with self._subscribers_lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(callback)
        logger.info("New subscriber registered for topic: '%s'", topic)

    def publish(self, topic: str, message: AgentMessage) -> None:
        """
        Publishes a message to all subscribers of a given topic.
        """
        with self._subscribers_lock:
            subscribers = list(self._subscribers.get(topic, []))
        
        if not subscribers:
            logger.warning("Published message to topic '%s' but no subscribers found.", topic)
            return

        logger.info("Publishing event on topic '%s' to %d subscribers.", topic, len(subscribers))
        for callback in subscribers:
            try:
                # Dispatched in a thread or inline. We run inline/sync for simplicity and trace stability
                # or dispatch in daemon threads. Let's run inline and capture errors safely.
                callback(message)
            except Exception as exc:
                logger.error("Error in subscriber callback for topic '%s': %s", topic, exc)

    def clear(self) -> None:
        """
        Clears all subscribers.
        """
        with self._subscribers_lock:
            self._subscribers.clear()
