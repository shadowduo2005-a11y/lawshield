"""
scheduler.py – schedules, runs, and monitors legal workflow instances.

Fixes vs previous version:
- _active_workflows now evicts entries older than _TTL_SECONDS after completion/failure,
  preventing unbounded memory growth in long-running services.
- create_workflow now validates required_inputs defined in the template before creating
  the instance, returning a clear error instead of a confusing step failure later.
- WorkflowExecutor is still instantiated in __init__ but the executor's model is now
  lazy-loaded (fixed in executor.py), so WorkflowScheduler() no longer triggers LLM init.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Dict, Any, Optional

from .state import WorkflowInstance, WorkflowStep
from .templates import WORKFLOW_TEMPLATES
from .executor import WorkflowExecutor

logger = logging.getLogger(__name__)

# Completed/failed workflows are evicted from memory after this many seconds
_TTL_SECONDS = 3600  # 1 hour

# Thread-safe in-memory database of active workflow runs
_active_workflows: Dict[str, WorkflowInstance] = {}
_workflows_lock = threading.Lock()


def _evict_expired() -> None:
    """Remove completed/failed workflow entries older than _TTL_SECONDS."""
    now = time.time()
    expired = [
        wid
        for wid, inst in _active_workflows.items()
        if inst.status in ("completed", "failed") and (now - inst.updated_at) > _TTL_SECONDS
    ]
    for wid in expired:
        del _active_workflows[wid]
        logger.debug("Evicted expired workflow %s from memory.", wid)


class WorkflowScheduler:
    """
    Schedules and runs workflows in the background.
    """

    def __init__(self, provider_name: str | None = None) -> None:
        self.executor = WorkflowExecutor(provider_name)
        # Note: executor.model is lazy — no LLM init happens here at startup.

    def create_workflow(self, template_name: str, inputs: Dict[str, Any]) -> WorkflowInstance:
        """
        Creates a new workflow instance from a template and registers it in memory.

        Validates that all required_inputs declared in the template are present and
        non-empty before creating the instance — gives callers a clear error instead
        of a cryptic step failure.
        """
        if template_name not in WORKFLOW_TEMPLATES:
            raise ValueError(
                f"Template '{template_name}' does not exist. "
                f"Available templates: {list(WORKFLOW_TEMPLATES.keys())}"
            )

        config = WORKFLOW_TEMPLATES[template_name]

        # Validate required inputs upfront
        required = config.get("required_inputs", [])
        missing = [k for k in required if not inputs.get(k) or not str(inputs[k]).strip()]
        if missing:
            raise ValueError(
                f"Template '{template_name}' requires the following non-empty input(s): "
                f"{missing}. Please provide them in the 'inputs' field."
            )

        workflow_id = str(uuid.uuid4())

        steps = [
            WorkflowStep(
                id=step_cfg["id"],
                name=step_cfg["name"],
                input_keys=step_cfg["input_keys"],
                output_keys=step_cfg["output_keys"],
            )
            for step_cfg in config["steps"]
        ]

        instance = WorkflowInstance(
            workflow_id=workflow_id,
            template_name=template_name,
            steps=steps,
            global_context=inputs,
        )

        with _workflows_lock:
            _evict_expired()  # housekeeping on every create
            _active_workflows[workflow_id] = instance

        logger.info(
            "Created workflow instance %s (template: %s, steps: %d)",
            workflow_id, template_name, len(steps),
        )
        return instance

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowInstance]:
        """Retrieves a workflow run from memory."""
        with _workflows_lock:
            return _active_workflows.get(workflow_id)

    def run_workflow_sync(self, workflow_id: str) -> None:
        """Executes a workflow synchronously step-by-step."""
        instance = self.get_workflow(workflow_id)
        if not instance:
            logger.error("Workflow run %s not found.", workflow_id)
            return

        instance.status = "running"
        instance.touch()
        logger.info("Starting execution of workflow %s", workflow_id)

        for i, step in enumerate(instance.steps):
            instance.current_step_index = i
            self.executor.execute_step(instance, step)

            if step.status == "failed":
                instance.status = "failed"
                instance.touch()
                logger.error(
                    "Workflow %s aborted at step '%s': %s",
                    workflow_id, step.id, step.error,
                )
                return

        instance.status = "completed"
        instance.touch()
        logger.info("Workflow %s completed successfully.", workflow_id)

    def run_workflow_async(self, workflow_id: str) -> None:
        """Spins off a background thread to execute the workflow."""
        thread = threading.Thread(
            target=self.run_workflow_sync,
            args=(workflow_id,),
            name=f"workflow-{workflow_id[:8]}",
            daemon=True,
        )
        thread.start()
        logger.info(
            "Workflow %s dispatched to background thread '%s'.", workflow_id, thread.name
        )
