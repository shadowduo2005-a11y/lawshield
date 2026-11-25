"""
memory.py – maintains thread-safe logs of all exchanged messages (MessageMemory).
"""
from __future__ import annotations

import threading
from typing import List, Optional

from .message import AgentMessage

class MessageMemory:
    """
    In-memory audit log of all communications for status tracing and audits.
    """
    _instance: Optional[MessageMemory] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls, *args, **kwargs)
                cls._instance._history = []
                cls._instance._history_lock = threading.Lock()
        return cls._instance

    def record(self, message: AgentMessage) -> None:
        """
        Appends a message to history.
        """
        with self._history_lock:
            # We record a snapshot/copy of the message
            self._history.append(message.model_copy())

    def get_history(self, sender: Optional[str] = None, receiver: Optional[str] = None, correlation_id: Optional[str] = None) -> List[AgentMessage]:
        """
        Retrieves matching message records from history.
        """
        with self._history_lock:
            results = list(self._history)
            
        if sender:
            results = [m for m in results if m.sender == sender]
        if receiver:
            results = [m for m in results if m.receiver == receiver]
        if correlation_id:
            results = [m for m in results if m.correlation_id == correlation_id]
            
        return results

    def clear(self) -> None:
        """
        Wipes all message logs.
        """
        with self._history_lock:
            self._history.clear()
