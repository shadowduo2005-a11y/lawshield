"""
Comprehensive test suite for Phase 10 (Legal Reasoning).

Tests are fully mocked so they run without real LLM keys.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from langchain_core.messages import AIMessage, HumanMessage

from graph.state import AgentState
from agents.reasoning.chain_of_thought import LegalReasoningAgent
from agents.reasoning.reviewer import LegalReviewerAgent
from agents.reasoning.verifier import LegalVerifierAgent
from agents.reasoning.confidence import LegalConfidenceScorer


def _ai_msg(content: str) -> AIMessage:
    m = MagicMock()
    m.content = content
    m.type = "ai"
    m.tool_calls = []
    return m


def _human_msg(content: str) -> HumanMessage:
    return HumanMessage(content=content)


def _make_state(**overrides) -> AgentState:
    """Helper that returns a minimal valid AgentState."""
    base: AgentState = {
        "messages": [_human_msg("Analyse my contract.")],
        "next_node": "",
        "plan": "",
        "research_data": [],
        "draft_content": "",
        "citations": [],
        "review_status": "",
        "contract_analysis": "",
        "compliance_report": "",
        "summary": "",
        "calculation_result": "",
        "reasoning_output": "",
        "reasoning_confidence": 0.0,
        "reasoning_iterations": 0,
    }
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# LegalReasoningAgent – think()
# ══════════════════════════════════════════════════════════════════════════════

class TestLegalReasoningAgent(unittest.TestCase):
    @patch("agents.reasoning.chain_of_thought.get_llm_provider")
    def test_think_returns_structured_analysis(self, mock_provider):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _ai_msg(
            "1. ANALYSIS\n"
            "Contract details.\n"
            "2. RISKS FOUND\n"
            "Liability is unlimited.\n"
            "3. RISK EXPLANATIONS\n"
            "The client faces massive financial exposure.\n"
            "4. SUGGESTED CHANGES\n"
            "Cap liability at 100%."
        )
        mock_provider.return_value.get_model.return_value = mock_model

        agent = LegalReasoningAgent()
        result = agent.think("Party A agrees to unlimited liability.")

        self.assertIn("ANALYSIS", result)
        self.assertIn("RISKS FOUND", result)
        self.assertIn("RISK EXPLANATIONS", result)
        self.assertIn("SUGGESTED CHANGES", result)
        mock_model.invoke.assert_called_once()

    @patch("agents.reasoning.chain_of_thought.get_llm_provider")
    def test_think_includes_focus_instruction(self, mock_provider):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _ai_msg("ANALYSIS RISKS FOUND RISK EXPLANATIONS SUGGESTED CHANGES")
        mock_provider.return_value.get_model.return_value = mock_model

        agent = LegalReasoningAgent()
        agent.think("Some contract.", user_query="Focus on indemnity clauses.")

        # Verify the user_query was included in the prompt
        call_args = mock_model.invoke.call_args[0][0]
        human_msg_content = call_args[-1].content
        self.assertIn("indemnity clauses", human_msg_content)


# ══════════════════════════════════════════════════════════════════════════════
# LegalReasoningAgent – refine()
# ══════════════════════════════════════════════════════════════════════════════

class TestLegalReasoningAgentRefine(unittest.TestCase):
    @patch("agents.reasoning.chain_of_thought.get_llm_provider")
    def test_refine_includes_feedback_in_prompt(self, mock_provider):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _ai_msg(
            "ANALYSIS RISKS FOUND RISK EXPLANATIONS SUGGESTED CHANGES Refined."
        )
        mock_provider.return_value.get_model.return_value = mock_model

        agent = LegalReasoningAgent()
        result = agent.refine(
            context="Contract text here.",
            initial_analysis="Initial draft.",
            feedback="Missed the indemnity clause.",
            suggestions=["Add indemnity analysis"],
            grounding_warnings=["No evidence for claim X."],
        )

        # Check that the refine prompt carries the feedback
        call_args = mock_model.invoke.call_args[0][0]
        human_content = call_args[-1].content
        self.assertIn("Missed the indemnity clause.", human_content)
        self.assertIn("Add indemnity analysis", human_content)
        self.assertIn("No evidence for claim X.", human_content)
        # The original contract should be present
        self.assertIn("Contract text here.", human_content)
        # The result should be the mocked output
        self.assertIn("Refined.", result)

    @patch("agents.reasoning.chain_of_thought.get_llm_provider")
    def test_refine_works_with_no_optional_args(self, mock_provider):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _ai_msg("Refined output.")
        mock_provider.return_value.get_model.return_value = mock_model

        agent = LegalReasoningAgent()
        # Should not raise even with all optional args omitted
        result = agent.refine(context="Contract.", initial_analysis="Draft.")
        self.assertEqual(result, "Refined output.")

    @patch("agents.reasoning.chain_of_thought.get_llm_provider")
    def test_model_is_lazy_loaded(self, mock_provider):
        """Model should not be instantiated until actually needed."""
        mock_provider.return_value.get_model.return_value = MagicMock()

        agent = LegalReasoningAgent()
        # No model access yet
        mock_provider.assert_not_called()

        # Trigger lazy load
        _ = agent.model
        mock_provider.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# JSON parsing helper
# ══════════════════════════════════════════════════════════════════════════════

class TestParseJsonObject(unittest.TestCase):
    def test_plain_json(self):
        from utils.json import parse_json_object
        raw = '{"review_status": "approved", "feedback": "ok", "suggestions": []}'
        result = parse_json_object(raw)
        self.assertEqual(result["review_status"], "approved")

    def test_json_with_markdown_fence(self):
        from utils.json import parse_json_object
        raw = "```json\n{\"review_status\": \"approved\", \"feedback\": \"ok\", \"suggestions\": []}\n```"
        result = parse_json_object(raw)
        self.assertEqual(result["review_status"], "approved")

    def test_json_embedded_in_prose(self):
        from utils.json import parse_json_object
        raw = 'Here is my assessment:\n{"review_status": "needs_revision", "feedback": "Missed risk.", "suggestions": ["Fix clause 3"]}\nEnd of assessment.'
        result = parse_json_object(raw)
        self.assertEqual(result["review_status"], "needs_revision")
        self.assertEqual(result["suggestions"], ["Fix clause 3"])

    def test_json_with_nested_array(self):
        from utils.json import parse_json_object
        raw = '{"grounded": true, "warnings": ["w1", "w2"], "verification_report": "Report text."}'
        result = parse_json_object(raw)
        self.assertTrue(result["grounded"])
        self.assertEqual(len(result["warnings"]), 2)

    def test_raises_on_garbage(self):
        from utils.json import parse_json_object
        with self.assertRaises(ValueError):
            parse_json_object("This is definitely not JSON at all.")


# ══════════════════════════════════════════════════════════════════════════════
# LegalReviewerAgent
# ══════════════════════════════════════════════════════════════════════════════

class TestLegalReviewerAgent(unittest.TestCase):
    @patch("agents.reasoning.reviewer.get_llm_provider")
    def test_reviewer_parses_json(self, mock_provider):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _ai_msg(
            '{"review_status": "approved", "feedback": "Logical analysis.", "suggestions": []}'
        )
        mock_provider.return_value.get_model.return_value = mock_model

        agent = LegalReviewerAgent()
        result = agent.review("Original text", "Reasoning output")

        self.assertEqual(result["review_status"], "approved")
        self.assertEqual(result["feedback"], "Logical analysis.")
        self.assertEqual(result["suggestions"], [])

    @patch("agents.reasoning.reviewer.get_llm_provider")
    def test_reviewer_parses_json_with_markdown_fence(self, mock_provider):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _ai_msg(
            "```json\n"
            '{"review_status": "needs_revision", "feedback": "Missed risk.", "suggestions": ["Add section 3"]}\n'
            "```"
        )
        mock_provider.return_value.get_model.return_value = mock_model

        agent = LegalReviewerAgent()
        result = agent.review("Original text", "Reasoning output")

        self.assertEqual(result["review_status"], "needs_revision")
        self.assertEqual(result["suggestions"], ["Add section 3"])

    @patch("agents.reasoning.reviewer.get_llm_provider")
    def test_reviewer_fallback_on_malformed_json(self, mock_provider):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _ai_msg("This is not JSON text")
        mock_provider.return_value.get_model.return_value = mock_model

        agent = LegalReviewerAgent()
        result = agent.review("Original text", "Reasoning output")

        self.assertEqual(result["review_status"], "approved")
        self.assertIn("fallback", result["feedback"])


# ══════════════════════════════════════════════════════════════════════════════
# LegalVerifierAgent
# ══════════════════════════════════════════════════════════════════════════════

class TestLegalVerifierAgent(unittest.TestCase):
    @patch("agents.reasoning.verifier.get_llm_provider")
    def test_verifier_parses_json(self, mock_provider):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _ai_msg(
            '{"grounded": true, "warnings": ["No warning"], "verification_report": "Verified."}'
        )
        mock_provider.return_value.get_model.return_value = mock_model

        agent = LegalVerifierAgent()
        result = agent.verify("Original text", "Reasoning output")

        self.assertTrue(result["grounded"])
        self.assertEqual(result["warnings"], ["No warning"])
        self.assertEqual(result["verification_report"], "Verified.")

    @patch("agents.reasoning.verifier.get_llm_provider")
    def test_verifier_parses_json_with_surrounding_prose(self, mock_provider):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _ai_msg(
            'Based on my analysis:\n'
            '{"grounded": false, "warnings": ["Hallucinated clause"], "verification_report": "Fails."}\n'
            'Please review the above.'
        )
        mock_provider.return_value.get_model.return_value = mock_model

        agent = LegalVerifierAgent()
        result = agent.verify("Original text", "Reasoning output")

        self.assertFalse(result["grounded"])
        self.assertIn("Hallucinated clause", result["warnings"])


# ══════════════════════════════════════════════════════════════════════════════
# LegalConfidenceScorer
# ══════════════════════════════════════════════════════════════════════════════

class TestLegalConfidenceScorer(unittest.TestCase):
    def test_perfect_score(self):
        reasoning = "ANALYSIS RISKS FOUND RISK EXPLANATIONS SUGGESTED CHANGES"
        reviewer = {"review_status": "approved"}
        verifier = {"grounded": True, "warnings": []}
        score = LegalConfidenceScorer.score(reasoning, reviewer, verifier)
        self.assertEqual(score, 1.0)

    def test_imperfect_score_due_to_revision_and_warnings(self):
        reasoning = "ANALYSIS RISKS FOUND RISK EXPLANATIONS SUGGESTED CHANGES"
        reviewer = {"review_status": "needs_revision"}
        # 2 warnings → warning score = 0.20 − 0.10 = 0.10
        verifier = {"grounded": True, "warnings": ["w1", "w2"]}
        score = LegalConfidenceScorer.score(reasoning, reviewer, verifier)
        # grounding: 0.30 + reviewer: 0.15 + warnings: 0.10 + structure: 0.20 = 0.75
        self.assertEqual(score, 0.75)

    def test_zero_grounding_reduces_score(self):
        reasoning = "ANALYSIS RISKS FOUND RISK EXPLANATIONS SUGGESTED CHANGES"
        reviewer = {"review_status": "approved"}
        verifier = {"grounded": False, "warnings": []}
        score = LegalConfidenceScorer.score(reasoning, reviewer, verifier)
        # grounding: 0.00 + reviewer: 0.30 + warnings: 0.20 + structure: 0.20 = 0.70
        self.assertEqual(score, 0.70)

    def test_empty_reasoning_output_handled(self):
        """Empty output should not raise — structural score is 0.0."""
        reviewer = {"review_status": "approved"}
        verifier = {"grounded": True, "warnings": []}
        score = LegalConfidenceScorer.score("", reviewer, verifier)
        # grounding: 0.30 + reviewer: 0.30 + warnings: 0.20 + structure: 0.00 = 0.80
        self.assertEqual(score, 0.80)

    def test_detailed_breakdown_keys(self):
        reasoning = "ANALYSIS RISKS FOUND RISK EXPLANATIONS SUGGESTED CHANGES"
        reviewer = {"review_status": "approved"}
        verifier = {"grounded": True, "warnings": []}
        breakdown = LegalConfidenceScorer.detailed_breakdown(reasoning, reviewer, verifier)

        self.assertIn("total", breakdown)
        self.assertIn("grounding", breakdown)
        self.assertIn("reviewer", breakdown)
        self.assertIn("warnings", breakdown)
        self.assertIn("structure", breakdown)
        self.assertIn("sections_found", breakdown)
        self.assertIn("warning_count", breakdown)
        self.assertEqual(breakdown["total"], 1.0)
        self.assertEqual(breakdown["warning_count"], 0)
        self.assertEqual(len(breakdown["sections_found"]), 4)

    def test_detailed_breakdown_with_warnings(self):
        reasoning = "ANALYSIS RISKS FOUND"
        reviewer = {"review_status": "needs_revision"}
        verifier = {"grounded": False, "warnings": ["w1"]}
        breakdown = LegalConfidenceScorer.detailed_breakdown(reasoning, reviewer, verifier)

        self.assertEqual(breakdown["warning_count"], 1)
        self.assertEqual(breakdown["reviewer_status"], "needs_revision")
        self.assertEqual(len(breakdown["sections_found"]), 2)


# ══════════════════════════════════════════════════════════════════════════════
# Reasoning Agent Node
# ══════════════════════════════════════════════════════════════════════════════

class TestReasoningAgentNode(unittest.TestCase):
    @patch("agents.reasoning.agent.LegalReasoningAgent")
    @patch("agents.reasoning.agent.LegalReviewerAgent")
    @patch("agents.reasoning.agent.LegalVerifierAgent")
    def test_reasoning_node_successful_pass(self, mock_verifier_cls, mock_reviewer_cls, mock_reasoning_cls):
        # Set up reasoning agent mock
        mock_reasoning = MagicMock()
        mock_reasoning.think.return_value = "ANALYSIS RISKS FOUND RISK EXPLANATIONS SUGGESTED CHANGES"
        mock_reasoning_cls.return_value = mock_reasoning

        # Set up reviewer mock (approved)
        mock_reviewer = MagicMock()
        mock_reviewer.review.return_value = {"review_status": "approved", "feedback": "Good job."}
        mock_reviewer_cls.return_value = mock_reviewer

        # Set up verifier mock (grounded)
        mock_verifier = MagicMock()
        mock_verifier.verify.return_value = {"grounded": True, "warnings": []}
        mock_verifier_cls.return_value = mock_verifier

        from agents.reasoning.agent import reasoning_node

        result = reasoning_node(_make_state())

        self.assertIn("reasoning_output", result)
        self.assertEqual(result["reasoning_confidence"], 1.0)
        self.assertEqual(result["reasoning_iterations"], 1)
        self.assertIn("✅ Grounded", result["reasoning_output"])
        self.assertIn("APPROVED", result["reasoning_output"])
        # refine() must NOT be called when approved + grounded
        mock_reasoning.refine.assert_not_called()

    @patch("agents.reasoning.agent.LegalReasoningAgent")
    @patch("agents.reasoning.agent.LegalReviewerAgent")
    @patch("agents.reasoning.agent.LegalVerifierAgent")
    def test_reasoning_node_self_correction_trigger(self, mock_verifier_cls, mock_reviewer_cls, mock_reasoning_cls):
        # Set up reasoning agent mock
        mock_reasoning = MagicMock()
        mock_reasoning.think.return_value = "ANALYSIS RISKS FOUND RISK EXPLANATIONS SUGGESTED CHANGES Initial draft"
        mock_reasoning.refine.return_value = "ANALYSIS RISKS FOUND RISK EXPLANATIONS SUGGESTED CHANGES Refined draft"
        mock_reasoning_cls.return_value = mock_reasoning

        # Set up reviewer mock (1st needs_revision, 2nd approved)
        mock_reviewer = MagicMock()
        mock_reviewer.review.side_effect = [
            {"review_status": "needs_revision", "feedback": "Clarify clause 3.", "suggestions": ["Add more detail."]},
            {"review_status": "approved", "feedback": "Excellent correction."},
        ]
        mock_reviewer_cls.return_value = mock_reviewer

        # Set up verifier mock (always grounded)
        mock_verifier = MagicMock()
        mock_verifier.verify.return_value = {"grounded": True, "warnings": []}
        mock_verifier_cls.return_value = mock_verifier

        from agents.reasoning.agent import reasoning_node

        result = reasoning_node(_make_state())

        # think() once, refine() once
        self.assertEqual(mock_reasoning.think.call_count, 1)
        self.assertEqual(mock_reasoning.refine.call_count, 1)
        # Verify refine was called with the correct feedback
        refine_kwargs = mock_reasoning.refine.call_args[1]
        self.assertEqual(refine_kwargs["feedback"], "Clarify clause 3.")

        self.assertEqual(result["reasoning_iterations"], 2)
        self.assertIn("[REFINED]", result["reasoning_output"])
        self.assertIn("Refined draft", result["reasoning_output"])
        self.assertEqual(result["reasoning_confidence"], 1.0)

    @patch("agents.reasoning.agent.LegalReasoningAgent")
    @patch("agents.reasoning.agent.LegalReviewerAgent")
    @patch("agents.reasoning.agent.LegalVerifierAgent")
    def test_reasoning_node_uses_draft_content_as_context(
        self, mock_verifier_cls, mock_reviewer_cls, mock_reasoning_cls
    ):
        """If draft_content is in state, it should be used as context."""
        mock_reasoning = MagicMock()
        mock_reasoning.think.return_value = "ANALYSIS RISKS FOUND RISK EXPLANATIONS SUGGESTED CHANGES"
        mock_reasoning_cls.return_value = mock_reasoning

        mock_reviewer = MagicMock()
        mock_reviewer.review.return_value = {"review_status": "approved", "feedback": "Good."}
        mock_reviewer_cls.return_value = mock_reviewer

        mock_verifier = MagicMock()
        mock_verifier.verify.return_value = {"grounded": True, "warnings": []}
        mock_verifier_cls.return_value = mock_verifier

        from agents.reasoning.agent import reasoning_node

        state = _make_state(draft_content="DRAFT CONTRACT CONTENT HERE")
        reasoning_node(state)

        # The context passed to think() should include draft_content
        think_call_context = mock_reasoning.think.call_args[1]["context"]
        self.assertIn("DRAFT CONTRACT CONTENT HERE", think_call_context)


# ══════════════════════════════════════════════════════════════════════════════
# Supervisor routing
# ══════════════════════════════════════════════════════════════════════════════

class TestSupervisorReasoningRoute(unittest.TestCase):
    @patch("agents.supervisor.agent.get_llm_provider")
    def test_supervisor_routes_to_reasoning(self, mock_provider):
        from agents.supervisor.agent import supervisor_node

        mock_model = MagicMock()
        mock_model.invoke.return_value = _ai_msg('{"next": "reasoning"}')
        mock_provider.return_value.get_model.return_value = mock_model

        result = supervisor_node(
            _make_state(
                messages=[_human_msg("Explain the risks in this contract and suggest changes")]
            )
        )
        self.assertEqual(result["next_node"], "reasoning")


if __name__ == "__main__":
    unittest.main()
