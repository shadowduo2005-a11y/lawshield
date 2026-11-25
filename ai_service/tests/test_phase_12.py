"""
Comprehensive test suite for Phase 12 (Workflow Engine).

Tests are fully mocked so they run without real LLM keys or network access.
"""
from __future__ import annotations

import json
import time
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from main import app
from workflow.state import WorkflowInstance, WorkflowStep
from workflow.templates import WORKFLOW_TEMPLATES
from workflow.executor import WorkflowExecutor
from workflow.scheduler import WorkflowScheduler


def _ai_msg(content: str) -> AIMessage:
    m = MagicMock()
    m.content = content
    m.type = "ai"
    m.tool_calls = []
    return m


class TestWorkflowState(unittest.TestCase):
    def test_workflow_step_initial_values(self):
        step = WorkflowStep(id="s1", name="Step One", input_keys=["a"], output_keys=["b"])
        self.assertEqual(step.status, "pending")
        self.assertEqual(step.outputs, {})
        self.assertIsNone(step.error)

    def test_workflow_instance_touch(self):
        inst = WorkflowInstance(workflow_id="w1", template_name="test")
        old_time = inst.updated_at
        time.sleep(0.01)
        inst.touch()
        self.assertGreater(inst.updated_at, old_time)


class TestWorkflowTemplates(unittest.TestCase):
    def test_contract_review_template_exists(self):
        self.assertIn("contract_review", WORKFLOW_TEMPLATES)
        cfg = WORKFLOW_TEMPLATES["contract_review"]
        self.assertEqual(len(cfg["steps"]), 5)
        self.assertEqual(cfg["steps"][0]["id"], "extract_clauses")
        self.assertEqual(cfg["steps"][-1]["id"], "generate_report")


class TestWorkflowExecutor(unittest.TestCase):
    @patch("workflow.executor.get_llm_provider")
    def test_execute_step_success(self, mock_provider):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _ai_msg("Extracted: Liability clause.")
        mock_provider.return_value.get_model.return_value = mock_model

        executor = WorkflowExecutor()
        instance = WorkflowInstance(
            workflow_id="w-123",
            template_name="contract_review",
            global_context={"contract_text": "Unlimited liability applies."}
        )
        step = WorkflowStep(
            id="extract_clauses",
            name="Extract",
            input_keys=["contract_text"],
            output_keys=["extracted_clauses"]
        )

        executor.execute_step(instance, step)

        self.assertEqual(step.status, "completed")
        self.assertEqual(step.outputs["extracted_clauses"], "Extracted: Liability clause.")
        self.assertEqual(instance.global_context["extracted_clauses"], "Extracted: Liability clause.")
        self.assertIsNone(step.error)

    def test_execute_step_missing_input_fails(self):
        executor = WorkflowExecutor()
        instance = WorkflowInstance(
            workflow_id="w-123",
            template_name="contract_review",
            global_context={}  # Missing "contract_text"
        )
        step = WorkflowStep(
            id="extract_clauses",
            name="Extract",
            input_keys=["contract_text"],
            output_keys=["extracted_clauses"]
        )

        executor.execute_step(instance, step)

        self.assertEqual(step.status, "failed")
        self.assertIn("Missing required input key", step.error)


class TestWorkflowScheduler(unittest.TestCase):
    def test_create_workflow_and_run_sync(self):
        scheduler = WorkflowScheduler()
        
        # Mock executor to avoid calling LLM during scheduler tests
        mock_executor = MagicMock()
        scheduler.executor = mock_executor

        # Setup step logic execution mock
        def fake_execute(instance, step):
            step.status = "completed"
            for out_key in step.output_keys:
                instance.global_context[out_key] = "mocked output"

        mock_executor.execute_step.side_effect = fake_execute

        instance = scheduler.create_workflow("contract_review", {"contract_text": "Sample text"})
        
        self.assertEqual(instance.status, "pending")
        self.assertEqual(len(instance.steps), 5)

        # Run scheduler sync execution
        scheduler.run_workflow_sync(instance.workflow_id)

        self.assertEqual(instance.status, "completed")
        self.assertEqual(mock_executor.execute_step.call_count, 5)


class TestWorkflowRouter(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_list_templates(self):
        response = self.client.get("/workflows/templates/list")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("contract_review", data)
        self.assertEqual(data["contract_review"]["step_count"], 5)

    @patch("workflow.router.scheduler")
    def test_start_workflow_success(self, mock_scheduler):
        # Setup mock scheduler behavior
        mock_instance = WorkflowInstance(
            workflow_id="wf-abc",
            template_name="contract_review",
            status="pending",
            steps=[WorkflowStep(id="s1", name="Step 1")]
        )
        mock_scheduler.create_workflow.return_value = mock_instance

        payload = {
            "template_name": "contract_review",
            "inputs": {"contract_text": "Indemnity applies."}
        }
        
        response = self.client.post("/workflows/start", json=payload)
        
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["workflow_id"], "wf-abc")
        self.assertEqual(data["status"], "pending")
        mock_scheduler.create_workflow.assert_called_once_with("contract_review", {"contract_text": "Indemnity applies."})
        mock_scheduler.run_workflow_async.assert_called_once_with("wf-abc")

    @patch("workflow.router.scheduler")
    def test_get_workflow_status_not_found(self, mock_scheduler):
        mock_scheduler.get_workflow.return_value = None
        response = self.client.get("/workflows/non-existent-id")
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"])

    @patch("workflow.router.scheduler")
    def test_get_workflow_status_success(self, mock_scheduler):
        mock_instance = WorkflowInstance(
            workflow_id="wf-abc",
            template_name="contract_review",
            status="completed"
        )
        mock_scheduler.get_workflow.return_value = mock_instance
        
        response = self.client.get("/workflows/wf-abc")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["workflow_id"], "wf-abc")
        self.assertEqual(data["status"], "completed")


if __name__ == "__main__":
    unittest.main()
