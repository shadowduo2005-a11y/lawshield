"""
Memory Conversation – sliding-window message store.
"""
from __future__ import annotations

from typing import Dict, List

from langchain_core.messages import BaseMessage


class SlidingWindowMemory:
    """Maintains a bounded list of messages per session.

    When the window overflows the ``max_messages`` limit the oldest *non-system*
    messages are dropped, preserving any leading SystemMessage.
    """

    def __init__(self, max_messages: int = 20) -> None:
        self.max_messages = max_messages
        self._messages: List[BaseMessage] = []

    # ── public API ────────────────────────────────────────────────────────────

    def add_message(self, message: BaseMessage) -> None:
        self._messages.append(message)
        self._enforce_limit()

    def get_messages(self) -> List[BaseMessage]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()

    # ── internal ──────────────────────────────────────────────────────────────

    def _enforce_limit(self) -> None:
        if len(self._messages) <= self.max_messages:
            return

        # Separate the (optional) leading SystemMessage from the rest
        if self._messages and self._messages[0].type == "system":
            system_msg = [self._messages[0]]
            rest = self._messages[1:]
        else:
            system_msg = []
            rest = self._messages

        # Keep the most recent (max_messages - len(system_msg)) messages
        keep = self.max_messages - len(system_msg)
        self._messages = system_msg + rest[-keep:]


# Global store – keyed by session_id
_store: Dict[str, SlidingWindowMemory] = {}


def get_conversation(session_id: str, max_messages: int = 20) -> SlidingWindowMemory:
    """Return (or create) a SlidingWindowMemory for the given session."""
    if session_id not in _store:
        _store[session_id] = SlidingWindowMemory(max_messages=max_messages)
    return _store[session_id]
