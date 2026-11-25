"""
router.py – implements standard communication patterns and exposes API endpoints for message operations.
"""
from __future__ import annotations

import logging
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from .message import AgentMessage
from .broker import MessageBroker
from .dispatcher import MessageDispatcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/communication", tags=["Agent Communication"])
broker = MessageBroker()
dispatcher = MessageDispatcher(broker)

# Register self as valid agents to receive responses
broker.register_agent("PipelineRouter", lambda payload: payload)
broker.register_agent("ParallelRouter", lambda payload: payload)

# ── Pattern Routing Helpers ────────────────────────────────────────────────
import uuid

def run_pipeline(agents: List[str], initial_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes a pipeline pattern: Agent 1 -> Agent 2 -> Agent 3.
    """
    if not agents:
        return initial_payload

    current_payload = initial_payload
    correlation_id = str(uuid.uuid4())
    
    for i in range(len(agents)):
        agent_name = agents[i]
        msg = AgentMessage(
            sender="PipelineRouter",
            receiver=agent_name,
            task=f"Pipeline step {i+1}",
            correlation_id=correlation_id,
            payload=current_payload,
            reply_to="PipelineRouter"
        )
        broker.send_message(msg)
        dispatcher.process_all_available()
        
        # Look up matching logs to fetch result using the explicit correlation_id
        history = broker.memory.get_history(sender=agent_name, receiver="PipelineRouter", correlation_id=correlation_id)
        if history:
            # We matched the exact response
            current_payload = history[-1].payload
        else:
            logger.warning("Pipeline step failed: No response payload from agent '%s'", agent_name)

    return current_payload

def run_parallel(agents: List[str], payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes parallel pattern: dispatches message to multiple agents, merges results.
    """
    correlation_id = str(uuid.uuid4())
    for agent_name in agents:
        msg = AgentMessage(
            sender="ParallelRouter",
            receiver=agent_name,
            task="Parallel Task",
            correlation_id=correlation_id,
            payload=payload,
            reply_to="ParallelRouter"
        )
        broker.send_message(msg)

    # Process all queued messages
    dispatcher.process_all_available()
    
    # Merge results
    merged_results = {}
    for agent_name in agents:
        history = broker.memory.get_history(sender=agent_name, receiver="ParallelRouter", correlation_id=correlation_id)
        if history:
            merged_results[agent_name] = history[-1].payload

    return merged_results

# ── Request Models ────────────────────────────────────────────────────────
class MessageSendRequest(BaseModel):
    sender: str
    receiver: str
    task: str
    payload: Dict[str, Any]
    priority: str = "MEDIUM"

class PipelineRequest(BaseModel):
    agents: List[str]
    payload: Dict[str, Any]

class ParallelRequest(BaseModel):
    agents: List[str]
    payload: Dict[str, Any]

# ── FastAPI Router Endpoints ──────────────────────────────────────────────
@router.post(
    "/send",
    status_code=status.HTTP_201_CREATED,
    summary="Send a message between agents"
)
async def send_agent_message(request: MessageSendRequest) -> Dict[str, Any]:
    """
    Routes a message to an agent or broadcast topic.
    Runs the dispatcher automatically to process queued messages.
    """
    from .protocol import MessagePriority
    
    try:
        prio = MessagePriority(request.priority.upper())
    except ValueError:
        prio = MessagePriority.MEDIUM

    msg = AgentMessage(
        sender=request.sender,
        receiver=request.receiver,
        task=request.task,
        priority=prio,
        payload=request.payload
    )

    broker.send_message(msg)
    # Process queued messages synchronously for test predictability
    dispatcher.process_all_available()

    return {
        "message_id": msg.id,
        "status": msg.status.value,
        "error": msg.error
    }

@router.get(
    "/history",
    summary="Get communication message logs"
)
async def get_message_history(sender: str | None = None, receiver: str | None = None) -> List[Dict[str, Any]]:
    """
    Retrieves the history logs of sent messages.
    """
    logs = broker.memory.get_history(sender=sender, receiver=receiver)
    return [log.model_dump() for log in logs]

@router.post(
    "/pipeline",
    summary="Run sequential agent-to-agent pipeline"
)
async def trigger_pipeline(request: PipelineRequest) -> Dict[str, Any]:
    """
    Triggers a sequential execution pattern: Agent A -> Agent B -> Agent C.
    """
    try:
        res = run_pipeline(request.agents, request.payload)
        return {"result": res}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc)
        )

@router.post(
    "/parallel",
    summary="Run parallel agent execution with merged output"
)
async def trigger_parallel(request: ParallelRequest) -> Dict[str, Any]:
    """
    Triggers a parallel merge pattern: dispatches same task to multiple agents.
    """
    try:
        res = run_parallel(request.agents, request.payload)
        return {"results": res}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc)
        )
