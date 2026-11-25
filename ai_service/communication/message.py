"""
message.py – defines the structured AgentMessage schema.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from .protocol import MessagePriority, MessageStatus

class AgentMessage(BaseModel):
    """
    Standard schema for all agent-to-agent messages.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender: str
    receiver: str
    task: str
    correlation_id: Optional[str] = None
    priority: MessagePriority = MessagePriority.MEDIUM
    payload: Dict[str, Any] = Field(default_factory=dict)
    status: MessageStatus = MessageStatus.PENDING
    timestamp: float = Field(default_factory=time.time)
    reply_to: Optional[str] = None
    error: Optional[str] = None
