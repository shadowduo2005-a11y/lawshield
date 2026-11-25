"""
state.py – defines the data models for the Workflow Engine.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class WorkflowStep(BaseModel):
    """
    Represents a single step in a legal workflow.
    """
    id: str
    name: str
    status: str = "pending"  # "pending" | "running" | "completed" | "failed"
    input_keys: List[str] = Field(default_factory=list)
    output_keys: List[str] = Field(default_factory=list)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None

class WorkflowInstance(BaseModel):
    """
    Represents an executing instance of a legal workflow.
    """
    workflow_id: str
    template_name: str
    status: str = "pending"  # "pending" | "running" | "completed" | "failed"
    current_step_index: int = 0
    steps: List[WorkflowStep] = Field(default_factory=list)
    global_context: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    def touch(self) -> None:
        """Updates the updated_at timestamp."""
        self.updated_at = time.time()
