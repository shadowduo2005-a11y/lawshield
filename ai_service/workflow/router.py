"""
router.py – FastAPI endpoints for creating, running, and monitoring legal workflows.

Fixes vs previous version:
- WorkflowScheduler is now lazy-initialised (created on first request, not at module
  import time). Previously `scheduler = WorkflowScheduler()` at module level triggered
  LLM provider initialisation during startup, crashing if env vars weren't set yet.
- /start endpoint now returns a structured response including step names and
  required_inputs metadata so the caller knows what the workflow expects.
- /templates/list now returns required_inputs per template.
- Added /cancel endpoint to allow aborting a running workflow.
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel

from .state import WorkflowInstance
from .templates import WORKFLOW_TEMPLATES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["Workflow Engine"])

# ── Lazy singleton ────────────────────────────────────────────────────────────
# Do NOT instantiate at module level — that triggers LLM init at startup.
_scheduler = None


def _get_scheduler():
    """Return (or lazily create) the module-level WorkflowScheduler singleton."""
    global _scheduler
    if _scheduler is None:
        from .scheduler import WorkflowScheduler
        _scheduler = WorkflowScheduler()
        logger.info("WorkflowScheduler lazily initialised.")
    return _scheduler


# ── Request / Response Models ─────────────────────────────────────────────────

class WorkflowStartRequest(BaseModel):
    template_name: str
    inputs: Dict[str, Any]


class WorkflowStartResponse(BaseModel):
    workflow_id: str
    template_name: str
    status: str
    step_count: int
    step_names: list[str]
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/start",
    response_model=WorkflowStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new legal workflow run",
)
async def start_workflow(request: WorkflowStartRequest) -> WorkflowStartResponse:
    """
    Spin up a new workflow run from the specified template.

    The workflow executes asynchronously in a background thread.
    Poll ``GET /workflows/{workflow_id}`` to track progress.

    Returns immediately with the workflow ID and step list.
    """
    try:
        scheduler = _get_scheduler()
        instance = scheduler.create_workflow(request.template_name, request.inputs)
        scheduler.run_workflow_async(instance.workflow_id)

        return WorkflowStartResponse(
            workflow_id=instance.workflow_id,
            template_name=instance.template_name,
            status=instance.status,
            step_count=len(instance.steps),
            step_names=[s.name for s in instance.steps],
            message=(
                f"Workflow '{request.template_name}' started with {len(instance.steps)} steps. "
                f"Poll GET /workflows/{instance.workflow_id} for status."
            ),
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except Exception as exc:
        logger.exception("Unexpected error starting workflow")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "/templates/list",
    summary="List all available legal workflow templates",
)
async def list_templates() -> Dict[str, Any]:
    """Return metadata of all configured workflow templates including required inputs."""
    return {
        name: {
            "name": cfg["name"],
            "description": cfg["description"],
            "step_count": len(cfg["steps"]),
            "required_inputs": cfg.get("required_inputs", []),
            "steps": [
                {"id": s["id"], "name": s["name"]}
                for s in cfg["steps"]
            ],
        }
        for name, cfg in WORKFLOW_TEMPLATES.items()
    }


@router.get(
    "/{workflow_id}",
    response_model=WorkflowInstance,
    summary="Get the execution status of a workflow run",
)
async def get_workflow_status(workflow_id: str) -> WorkflowInstance:
    """
    Poll the current execution state, step statuses, context, and outputs.

    Step statuses: ``pending`` | ``running`` | ``completed`` | ``failed``
    Workflow status: ``pending`` | ``running`` | ``completed`` | ``failed``
    """
    scheduler = _get_scheduler()
    instance = scheduler.get_workflow(workflow_id)
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Workflow run '{workflow_id}' not found. "
                "It may have been evicted after completion (TTL: 1 hour)."
            ),
        )
    return instance


@router.delete(
    "/{workflow_id}/cancel",
    summary="Mark a pending workflow as cancelled",
)
async def cancel_workflow(workflow_id: str) -> Dict[str, str]:
    """
    Marks a pending workflow as failed/cancelled.

    Note: This does NOT interrupt a step that is already running (background
    thread cannot be cleanly interrupted mid-LLM call). It prevents future
    steps from starting by marking the instance as failed.
    """
    scheduler = _get_scheduler()
    instance = scheduler.get_workflow(workflow_id)
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow run '{workflow_id}' not found.",
        )
    if instance.status in ("completed", "failed"):
        return {
            "status": instance.status,
            "message": f"Workflow already in terminal state: {instance.status}",
        }

    instance.status = "failed"
    instance.touch()
    # Mark all pending steps as failed
    for step in instance.steps:
        if step.status == "pending":
            step.status = "failed"
            step.error = "Cancelled by user request."

    logger.info("Workflow %s cancelled by user request.", workflow_id)
    return {"status": "cancelled", "workflow_id": workflow_id}
