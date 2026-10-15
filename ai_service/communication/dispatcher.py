"""
dispatcher.py – fetches messages from broker queues and executes target agent handlers.
"""
from __future__ import annotations

import logging
from typing import Optional

from .message import AgentMessage
from .protocol import MessageStatus
from .broker import MessageBroker
from observability.tracing import trace_agent

logger = logging.getLogger(__name__)

class MessageDispatcher:
    """
    Dispatcher polling the broker queue and invoking agent handler callables.
    """
    def __init__(self, broker: MessageBroker) -> None:
        self.broker = broker

    def process_next(self, block: bool = False, timeout: Optional[float] = None) -> bool:
        """
        Pops the next message from the priority queue and processes it.
        Returns True if a message was successfully processed, False if queue was empty.
        """
        message = self.broker.queue.pop(block=block, timeout=timeout)
        if not message:
            return False

        handler = self.broker.registry.get_handler(message.receiver)
        if not handler:
            message.status = MessageStatus.FAILED
            message.error = f"Handler not found for agent '{message.receiver}'."
            logger.error("Dispatch failed: %s", message.error)
            return True

        logger.info("Dispatching message %s to agent '%s'", message.id, message.receiver)
        try:
            # Wrap in OpenTelemetry trace using the correlation ID (if available) as session ID
            session_id = message.correlation_id or message.id
            with trace_agent(message.receiver, session_id=session_id, task=message.task):
                # Call registered callback
                result = handler(message.payload)
                message.status = MessageStatus.PROCESSED
            
            # If the callback returns data and a response destination (reply_to) is configured
            if result and message.reply_to:
                reply = AgentMessage(
                    sender=message.receiver,
                    receiver=message.reply_to,
                    task=f"Response to: {message.task}",
                    correlation_id=message.correlation_id or message.id,
                    priority=message.priority,
                    payload=result
                )
                self.broker.send_message(reply)
                
        except Exception as exc:
            message.status = MessageStatus.FAILED
            message.error = str(exc)
            logger.error("Exception occurred while dispatching to agent '%s': %s", message.receiver, exc)

        return True

    def process_all_available(self) -> int:
        """
        Processes all currently queued messages. Returns the count of processed messages.
        """
        count = 0
        while self.process_next(block=False):
            count += 1
        return count
