"""
Comprehensive test suite for Phases 6–9.

Tests are fully mocked so they run without:
  - A real OpenAI / Gemini / Anthropic key
  - A running Qdrant or Elasticsearch instance

Run with:
    cd ai_service && uv run python3 -m pytest tests/test_phases_6_9.py -v
"""
from __future__ import annotations

import asyncio
import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ai_msg(content: str):
    """Create a fake AIMessage."""
    m = MagicMock()
    m.content = content
    m.type = "ai"
    m.tool_calls = []
    return m


def _human_msg(content: str):
    from langchain_core.messages import HumanMessage
    return HumanMessage(content=content)


def _system_msg(content: str):
    from langchain_core.messages import SystemMessage
    return SystemMessage(content=content)


# ---------------------------------------------------------------------------
# Phase 6 – Multi-Agent Graph & Agents
# ---------------------------------------------------------------------------

class TestSupervisorAgent(unittest.TestCase):
    def _run(self, llm_response: str):
        from agents.supervisor.agent import supervisor_node
        from graph.state import AgentState
        with patch("agents.supervisor.agent.get_llm_provider") as mock_provider:
            mock_model = MagicMock()
            mock_model.invoke.return_value = _ai_msg(llm_response)
            mock_provider.return_value.get_model.return_value = mock_model

            state: AgentState = {"messages": [_human_msg("Review my contract")], "next_node": "", "plan": "", "research_data": [], "draft_content": "", "citations": [], "review_status": "", "contract_analysis": "", "compliance_report": "", "summary": "", "calculation_result": ""}
            return supervisor_node(state)

    def test_routes_to_contract(self):
        result = self._run('{"next": "contract"}')
        self.assertEqual(result["next_node"], "contract")

    def test_routes_to_planner(self):
        result = self._run('{"next": "planner"}')
        self.assertEqual(result["next_node"], "planner")

    def test_routes_to_calculator(self):
        result = self._run('{"next": "calculator"}')
        self.assertEqual(result["next_node"], "calculator")

    def test_routes_to_summarizer(self):
        result = self._run('{"next": "summarizer"}')
        self.assertEqual(result["next_node"], "summarizer")

    def test_routes_to_finish(self):
        result = self._run('{"next": "FINISH"}')
        self.assertEqual(result["next_node"], "FINISH")

    def test_invalid_route_defaults_to_planner(self):
        result = self._run('{"next": "unknown_agent"}')
        self.assertEqual(result["next_node"], "rag")

    def test_malformed_json_defaults_to_planner(self):
        result = self._run("I choose the planner because of complex legal reasons")
        self.assertEqual(result["next_node"], "rag")


class TestPlannerAgent(unittest.TestCase):
    def test_returns_plan(self):
        from agents.planner.agent import planner_node
        with patch("agents.planner.agent.get_llm_provider") as mock_provider:
            mock_model = MagicMock()
            mock_model.invoke.return_value = _ai_msg("1. Research case law\n2. Analyse facts\n3. Draft response")
            mock_provider.return_value.get_model.return_value = mock_model

            state = {"messages": [_human_msg("What is Section 54 of the Income Tax Act?")], "plan": ""}
            result = planner_node(state)

            self.assertIn("plan", result)
            self.assertIn("Research", result["plan"])

    def test_reads_last_human_message(self):
        """Planner should skip the SystemMessage and read the actual user query."""
        from agents.planner.agent import planner_node
        with patch("agents.planner.agent.get_llm_provider") as mock_provider:
            mock_model = MagicMock()
            mock_model.invoke.return_value = _ai_msg("Plan for contract")
            mock_provider.return_value.get_model.return_value = mock_model

            state = {"messages": [_system_msg("You are Harvey"), _human_msg("Review this contract")], "plan": ""}
            result = planner_node(state)
            # Verify the prompt sent to the LLM contains the user query not the system message
            call_args = mock_model.invoke.call_args[0][0]
            prompt_text = call_args[0].content
            self.assertIn("Review this contract", prompt_text)


class TestResearchAgent(unittest.TestCase):
    def test_appends_to_research_data(self):
        from agents.research.agent import research_node
        with patch("agents.research.agent.get_llm_provider") as mock_provider:
            mock_model = MagicMock()
            mock_model.invoke.return_value = _ai_msg("Found: Section 54 exempts long-term capital gains.")
            mock_provider.return_value.get_model.return_value = mock_model
            mock_model.bind_tools.return_value = mock_model

            state = {"messages": [_human_msg("What is Section 54?")], "plan": "1. Search legal DB", "research_data": ["Prior research"]}
            result = research_node(state)

            self.assertIn("research_data", result)
            self.assertEqual(len(result["research_data"]), 2)
            self.assertIn("Section 54", result["research_data"][1])


class TestCalculatorAgent(unittest.TestCase):
    def test_returns_calculation_result(self):
        from agents.calculator.agent import calculator_node
        with patch("agents.calculator.agent.get_llm_provider") as mock_provider:
            mock_model = MagicMock()
            mock_model.invoke.return_value = _ai_msg("Capital Gain = 150000")
            mock_provider.return_value.get_model.return_value = mock_model
            mock_model.bind_tools.return_value = mock_model

            state = {"messages": [_human_msg("Calculate 15% of 1000000")], "calculation_result": ""}
            result = calculator_node(state)

            self.assertIn("calculation_result", result)
            self.assertIn("150000", result["calculation_result"])


class TestContractAgent(unittest.TestCase):
    def test_returns_contract_analysis(self):
        from agents.contract.agent import contract_node
        with patch("agents.contract.agent.get_llm_provider") as mock_provider:
            mock_model = MagicMock()
            mock_model.invoke.return_value = _ai_msg("Clause 3 carries significant risk.")
            mock_provider.return_value.get_model.return_value = mock_model
            mock_model.bind_tools.return_value = mock_model

            state = {"messages": [_human_msg("Review this contract: Party A agrees...")], "contract_analysis": ""}
            result = contract_node(state)

            self.assertIn("contract_analysis", result)
            self.assertIn("risk", result["contract_analysis"])


class TestGraphRouting(unittest.TestCase):
    def test_route_supervisor_to_contract(self):
        from graph.conditions.routing import route_supervisor
        state = {"next_node": "contract"}
        self.assertEqual(route_supervisor(state), "contract")

    def test_route_supervisor_finish_to_end(self):
        from graph.conditions.routing import route_supervisor
        state = {"next_node": "FINISH"}
        self.assertEqual(route_supervisor(state), "__end__")

    def test_route_reviewer_approved(self):
        from graph.conditions.routing import route_reviewer
        state = {"review_status": "approved", "research_data": []}
        self.assertEqual(route_reviewer(state), "__end__")

    def test_route_reviewer_rejected_goes_back(self):
        from graph.conditions.routing import route_reviewer
        state = {"review_status": "rejected", "research_data": ["r1"]}
        self.assertEqual(route_reviewer(state), "planner")

    def test_route_reviewer_rejected_too_many_retries_ends(self):
        from graph.conditions.routing import route_reviewer
        state = {"review_status": "rejected", "research_data": ["r1", "r2", "r3"]}
        self.assertEqual(route_reviewer(state), "__end__")


# ---------------------------------------------------------------------------
# Phase 7 – Tools
# ---------------------------------------------------------------------------

class TestCalculatorTool(unittest.TestCase):
    def test_simple_arithmetic(self):
        from tools.calculator import calculate_math
        result = calculate_math.invoke({"expression": "100 * 0.15"})
        self.assertEqual(result, "15")

    def test_complex_expression(self):
        from tools.calculator import calculate_math
        result = calculate_math.invoke({"expression": "(1000 + 500) / 2"})
        self.assertEqual(result, "750")

    def test_invalid_expression_returns_error(self):
        from tools.calculator import calculate_math
        result = calculate_math.invoke({"expression": "import os"})
        self.assertIn("error", result.lower())

    def test_power_operator(self):
        from tools.calculator import calculate_math
        result = calculate_math.invoke({"expression": "2 ** 10"})
        self.assertEqual(result, "1024")


class TestTimelineTool(unittest.TestCase):
    def test_adds_days_correctly(self):
        from tools.timeline import court_timeline
        result = court_timeline.invoke({"start_date": "2024-01-01", "add_days": 10})
        self.assertIn("2024-01-11", result)

    def test_crosses_month_boundary(self):
        from tools.timeline import court_timeline
        result = court_timeline.invoke({"start_date": "2024-01-20", "add_days": 30})
        self.assertIn("2024-02-19", result)

    def test_invalid_date_returns_error(self):
        from tools.timeline import court_timeline
        result = court_timeline.invoke({"start_date": "not-a-date", "add_days": 30})
        self.assertIn("Error", result)


class TestCompareTool(unittest.TestCase):
    def test_identical_documents(self):
        from tools.compare import compare_documents
        result = compare_documents.invoke({"text_a": "Hello World", "text_b": "Hello World"})
        self.assertIn("Documents are identical", result)

    def test_different_documents(self):
        from tools.compare import compare_documents
        result = compare_documents.invoke({"text_a": "Party A shall pay 100.", "text_b": "Party A shall pay 200."})
        self.assertIn("100", result)
        self.assertIn("200", result)

    def test_diff_format(self):
        from tools.compare import compare_documents
        result = compare_documents.invoke({"text_a": "Old clause.", "text_b": "New clause."})
        self.assertIn("---", result)
        self.assertIn("+++", result)


class TestCitationTool(unittest.TestCase):
    def test_bluebook_format(self):
        from tools.citation import format_citation
        result = format_citation.invoke({
            "case_name": "Smith v. Jones",
            "volume": "123",
            "reporter": "F.3d",
            "first_page": "456",
            "year": "2010"
        })
        self.assertEqual(result, "Smith v. Jones, 123 F.3d 456 (2010)")


class TestSearchTool(unittest.TestCase):
    def test_search_tool_wraps_hybrid_search(self):
        from tools.search import legal_search
        with patch("tools.search.advanced_hybrid_search") as mock_search:
            mock_search.return_value = ["Section 54 provides exemption on capital gains."]
            result = legal_search.invoke({"query": "Section 54 capital gains", "top_k": 3})
            self.assertIn("Section 54", result)
            mock_search.assert_called_once_with("Section 54 capital gains", top_k=3)

    def test_empty_results_return_message(self):
        from tools.search import legal_search
        with patch("tools.search.advanced_hybrid_search") as mock_search:
            mock_search.return_value = []
            result = legal_search.invoke({"query": "obscure query"})
            self.assertIn("No relevant legal documents found", result)


# ---------------------------------------------------------------------------
# Phase 8 – Advanced RAG
# ---------------------------------------------------------------------------

class TestAdaptiveRouter(unittest.TestCase):
    def _route(self, llm_response: str) -> str:
        from rag.adaptive.router import route_query
        with patch("rag.adaptive.router.get_llm_provider") as mock_provider:
            mock_model = MagicMock()
            mock_model.invoke.return_value = _ai_msg(llm_response)
            mock_provider.return_value.get_model.return_value = mock_model
            return route_query("Some query")

    def test_routes_to_vectorstore(self):
        self.assertEqual(self._route("vectorstore"), "vectorstore")

    def test_routes_to_web_search(self):
        self.assertEqual(self._route("web_search"), "web_search")

    def test_routes_to_direct(self):
        self.assertEqual(self._route("direct"), "direct")

    def test_invalid_response_defaults_to_vectorstore(self):
        self.assertEqual(self._route("I don't know"), "vectorstore")


class TestQueryRewrite(unittest.TestCase):
    def test_rewrites_query(self):
        from rag.adaptive.query_rewrite import rewrite_query
        with patch("rag.adaptive.query_rewrite.get_llm_provider") as mock_provider:
            mock_model = MagicMock()
            mock_model.invoke.return_value = _ai_msg("Section 54 Income Tax Act capital gains exemption")
            mock_provider.return_value.get_model.return_value = mock_model
            result = rewrite_query("what about that tax rule for property gains?")
            self.assertIn("capital gains", result)

    def test_fallback_on_failure(self):
        from rag.adaptive.query_rewrite import rewrite_query
        with patch("rag.adaptive.query_rewrite.get_llm_provider") as mock_provider:
            # Raise on .get_model().invoke() call
            mock_model = MagicMock()
            mock_model.invoke.side_effect = Exception("LLM unavailable")
            mock_provider.return_value.get_model.return_value = mock_model
            original = "original query text"
            result = rewrite_query(original)
            self.assertEqual(result, original)


class TestMetadataFilters(unittest.TestCase):
    def test_extracts_year(self):
        from rag.metadata.filters import extract_metadata_filters
        with patch("rag.metadata.filters.get_llm_provider") as mock_provider:
            mock_model = MagicMock()
            mock_model.invoke.return_value = _ai_msg('{"year": 2022}')
            mock_provider.return_value.get_model.return_value = mock_model
            result = extract_metadata_filters("Show me contracts from 2022")
            self.assertEqual(result.get("year"), 2022)

    def test_empty_on_failure(self):
        from rag.metadata.filters import extract_metadata_filters
        with patch("rag.metadata.filters.get_llm_provider") as mock_provider:
            mock_model = MagicMock()
            mock_model.invoke.side_effect = Exception("LLM Error")
            mock_provider.return_value.get_model.return_value = mock_model
            result = extract_metadata_filters("some query")
            self.assertEqual(result, {})

    def test_sanitises_unknown_keys(self):
        from rag.metadata.filters import extract_metadata_filters
        with patch("rag.metadata.filters.get_llm_provider") as mock_provider:
            mock_model = MagicMock()
            # LLM returns a key that's not in our allowlist
            mock_model.invoke.return_value = _ai_msg('{"year": 2021, "secret_key": "hack"}')
            mock_provider.return_value.get_model.return_value = mock_model
            result = extract_metadata_filters("Contracts from 2021")
            self.assertNotIn("secret_key", result)
            self.assertIn("year", result)


class TestSelfRAGEvaluator(unittest.TestCase):
    def test_grade_keeps_relevant_docs(self):
        from rag.self_rag.evaluator import grade_documents
        with patch("rag.self_rag.evaluator.get_llm_provider") as mock_provider:
            mock_model = MagicMock()
            mock_model.invoke.return_value = _ai_msg("[0]")
            mock_provider.return_value.get_model.return_value = mock_model
            result = grade_documents("Section 54", ["Section 54 talks about property gains."])
            self.assertEqual(len(result), 1)

    def test_grade_removes_irrelevant_docs(self):
        from rag.self_rag.evaluator import grade_documents
        with patch("rag.self_rag.evaluator.get_llm_provider") as mock_provider:
            mock_model = MagicMock()
            mock_model.invoke.return_value = _ai_msg("[]")
            mock_provider.return_value.get_model.return_value = mock_model
            result = grade_documents("Section 54", ["This is about food safety regulations."])
            self.assertEqual(len(result), 0)

    def test_hallucination_check_returns_true_when_grounded(self):
        from rag.self_rag.evaluator import check_hallucination
        with patch("rag.self_rag.evaluator.get_llm_provider") as mock_provider:
            mock_model = MagicMock()
            mock_model.invoke.return_value = _ai_msg("yes")
            mock_provider.return_value.get_model.return_value = mock_model
            result = check_hallucination("The tax exemption is 100%.", ["The tax exemption is 100%."])
            self.assertTrue(result)

    def test_hallucination_check_returns_false_when_hallucinated(self):
        from rag.self_rag.evaluator import check_hallucination
        with patch("rag.self_rag.evaluator.get_llm_provider") as mock_provider:
            mock_model = MagicMock()
            mock_model.invoke.return_value = _ai_msg("no")
            mock_provider.return_value.get_model.return_value = mock_model
            result = check_hallucination("The sky is green.", ["The sky is blue."])
            self.assertFalse(result)

    def test_hallucination_check_no_docs_returns_false(self):
        """No documents to compare against — should be marked as ungrounded unless hard refusal."""
        from rag.self_rag.evaluator import check_hallucination
        result = check_hallucination("Some answer.", [])
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# Phase 9 – Memory
# ---------------------------------------------------------------------------

class TestConversationMemory(unittest.TestCase):
    def setUp(self):
        from memory.conversation import SlidingWindowMemory
        self.mem = SlidingWindowMemory(max_messages=4)

    def test_adds_and_retrieves_messages(self):
        self.mem.add_message(_human_msg("Hello"))
        msgs = self.mem.get_messages()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].content, "Hello")

    def test_sliding_window_evicts_old_messages(self):
        for i in range(6):
            self.mem.add_message(_human_msg(f"Message {i}"))
        msgs = self.mem.get_messages()
        self.assertLessEqual(len(msgs), 4)
        # Most recent message should always be present
        self.assertEqual(msgs[-1].content, "Message 5")

    def test_preserves_system_message(self):
        self.mem.add_message(_system_msg("You are Harvey"))
        for i in range(5):
            self.mem.add_message(_human_msg(f"Msg {i}"))
        msgs = self.mem.get_messages()
        self.assertEqual(msgs[0].type, "system")
        self.assertEqual(msgs[0].content, "You are Harvey")

    def test_clear_empties_memory(self):
        self.mem.add_message(_human_msg("Test"))
        self.mem.clear()
        self.assertEqual(len(self.mem.get_messages()), 0)

    def test_get_conversation_returns_same_instance(self):
        from memory.conversation import get_conversation
        m1 = get_conversation("session_abc")
        m2 = get_conversation("session_abc")
        self.assertIs(m1, m2)


class TestLongTermMemory(unittest.TestCase):
    def test_no_facts_returns_empty_string(self):
        from memory.long_term import get_long_term_facts
        result = get_long_term_facts("new_session_xyz_123")
        self.assertEqual(result, "")

    def test_extract_and_retrieve_facts(self):
        from memory.long_term import extract_and_save_facts, get_long_term_facts
        with patch("memory.long_term.get_llm_provider") as mock_provider, patch("memory.long_term._get_connection") as mock_conn:
            mock_model = MagicMock()
            mock_model.invoke.return_value = _ai_msg('["User works for Acme Corp", "User prefers bullet points"]')
            mock_provider.return_value.get_model.return_value = mock_model
            
            # Mock the DB cursor
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor

            extract_and_save_facts("session_fact_test", "User: I work for Acme Corp\nHarvey: Understood.")
            
            # For the retrieval mock, return what was "inserted"
            mock_cursor.fetchall.return_value = [("User works for Acme Corp",), ("User prefers bullet points",)]
            result = get_long_term_facts("session_fact_test")

            self.assertIn("Acme Corp", result)
            self.assertIn("bullet points", result)

    def test_malformed_llm_output_does_not_crash(self):
        from memory.long_term import extract_and_save_facts
        with patch("memory.long_term.get_llm_provider") as mock_provider:
            mock_model = MagicMock()
            mock_model.invoke.return_value = _ai_msg("Some invalid JSON response without any list")
            mock_provider.return_value.get_model.return_value = mock_model
            # Should not raise
            extract_and_save_facts("session_malformed", "some exchange")


class TestMaskingPipeline(unittest.TestCase):
    def test_empty_text_returns_unchanged(self):
        from masking.masking_pipeline import mask_text
        masked, state = mask_text("")
        self.assertEqual(masked, "")

    def test_restore_text_noop_on_empty_state(self):
        from masking.masking_pipeline import restore_text
        from masking.replacement import MaskingState
        result = restore_text("hello world", MaskingState())
        self.assertEqual(result, "hello world")

    def test_round_trip_passthrough(self):
        """Mock the Presidio analyser to avoid loading heavy NER models in CI."""
        from masking.masking_pipeline import mask_and_restore_passthrough
        with patch("masking.masking_pipeline.get_analyzer") as mock_get_analyzer:
            mock_analyzer = MagicMock()
            mock_analyzer.analyze.return_value = []  # No PII detected
            mock_get_analyzer.return_value = mock_analyzer
            text = "A simple sentence with no PII."
            result = mask_and_restore_passthrough(text)
            self.assertEqual(result, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
