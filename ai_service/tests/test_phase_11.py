"""
Comprehensive test suite for Phase 11 (Citation Engine).

Tests are fully mocked so they run without real LLM keys.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from graph.state import AgentState
from agents.citation.builder import Citation, CitationBuilder
from agents.citation.formatter import CitationFormatter
from agents.citation.verifier import CitationVerifier
from agents.citation.exporter import CitationExporter


def _ai_msg(content: str) -> AIMessage:
    m = MagicMock()
    m.content = content
    m.type = "ai"
    m.tool_calls = []
    return m


def _make_state(**overrides) -> AgentState:
    base: AgentState = {
        "messages": [],
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
# CitationBuilder – Regex Extraction
# ══════════════════════════════════════════════════════════════════════════════

class TestCitationBuilder(unittest.TestCase):
    def test_regex_statutory_extraction(self):
        builder = CitationBuilder()
        text = "Under Section 54 of the Income Tax Act, capital gains are exempt."
        results = builder.extract_from_text(text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source_title, "Income Tax Act")
        self.assertEqual(results[0].section, "54")

    def test_regex_statutory_with_page_and_paragraph(self):
        builder = CitationBuilder()
        text = "Refer to Section 80C, Income Tax Act, Page 12, Paragraph 3."
        results = builder.extract_from_text(text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source_title, "Income Tax Act")
        self.assertEqual(results[0].section, "80C")
        self.assertEqual(results[0].page, "12")
        self.assertEqual(results[0].paragraph, "3")

    def test_regex_case_law_extraction(self):
        builder = CitationBuilder()
        text = "See Smith v. Jones, 123 F.3d 456 (2010)."
        results = builder.extract_from_text(text)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source_title, "Smith v. Jones")
        self.assertEqual(results[0].volume, "123")
        self.assertEqual(results[0].reporter, "F.3d")
        self.assertEqual(results[0].first_page, "456")
        self.assertEqual(results[0].year, "2010")

    def test_deduplication_of_identical_citations(self):
        builder = CitationBuilder()
        # Both sentences reference the same statutory citation
        text = (
            "Section 54 of the Income Tax Act applies here. "
            "As noted, Section 54 of the Income Tax Act provides the exemption."
        )
        results = builder.extract_from_text(text)
        # Should be deduplicated to 1
        self.assertEqual(len(results), 1)

    @patch("agents.citation.builder.get_llm_provider")
    def test_llm_fallback_extraction(self, mock_provider):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _ai_msg(
            '[\n'
            '  {\n'
            '    "source_title": "Companies Act",\n'
            '    "section": "135",\n'
            '    "page": null,\n'
            '    "paragraph": null,\n'
            '    "volume": null,\n'
            '    "reporter": null,\n'
            '    "first_page": null,\n'
            '    "year": "2013"\n'
            '  }\n'
            ']'
        )
        mock_provider.return_value.get_model.return_value = mock_model

        builder = CitationBuilder()
        # Text with no matching regex patterns
        results = builder.extract_from_text("Let's look at the CSR rule under Companies Act section 135.")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source_title, "Companies Act")
        self.assertEqual(results[0].section, "135")
        self.assertEqual(results[0].year, "2013")

    @patch("agents.citation.builder.get_llm_provider")
    def test_llm_not_called_when_regex_succeeds(self, mock_provider):
        """LLM should NOT be initialised if regex extraction finds citations."""
        builder = CitationBuilder()
        text = "Under Section 54 of the Income Tax Act, capital gains are exempt."
        builder.extract_from_text(text)

        # LLM provider must NOT have been called
        mock_provider.assert_not_called()

    @patch("agents.citation.builder.get_llm_provider")
    def test_llm_handles_markdown_fenced_response(self, mock_provider):
        mock_model = MagicMock()
        mock_model.invoke.return_value = _ai_msg(
            "```json\n"
            '[{"source_title": "Companies Act", "section": "135", "page": null, '
            '"paragraph": null, "volume": null, "reporter": null, "first_page": null, "year": null}]\n'
            "```"
        )
        mock_provider.return_value.get_model.return_value = mock_model

        builder = CitationBuilder()
        results = builder.extract_from_text("No standard citation here.")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source_title, "Companies Act")


# ══════════════════════════════════════════════════════════════════════════════
# CitationFormatter
# ══════════════════════════════════════════════════════════════════════════════

class TestCitationFormatter(unittest.TestCase):
    def test_format_bluebook_case(self):
        c = Citation(source_title="Smith v. Jones", volume="123", reporter="F.3d", first_page="456", year="2010")
        formatted = CitationFormatter.format_bluebook(c)
        self.assertEqual(formatted, "Smith v. Jones, 123 F.3d 456 (2010)")

    def test_format_bluebook_statute(self):
        c = Citation(source_title="Income Tax Act", section="54", page="324", year="2020")
        formatted = CitationFormatter.format_bluebook(c)
        self.assertEqual(formatted, "Income Tax Act, § 54, at 324 (2020)")

    def test_format_statutory(self):
        c = Citation(source_title="Income Tax Act", section="54", page="324", paragraph="5")
        formatted = CitationFormatter.format_statutory(c)
        self.assertEqual(formatted, "Section 54, Income Tax Act, Page 324, Paragraph 5")

    def test_format_indian_statute(self):
        c = Citation(source_title="Income Tax Act", section="54")
        formatted = CitationFormatter.format_indian(c)
        self.assertEqual(formatted, "Section 54 of the Income Tax Act")

    def test_format_indian_case(self):
        c = Citation(source_title="State v. Sen", volume="3", reporter="SCC", first_page="456", year="2012")
        formatted = CitationFormatter.format_indian(c)
        self.assertEqual(formatted, "State v. Sen, (2012) 3 SCC 456")


# ══════════════════════════════════════════════════════════════════════════════
# CitationVerifier
# ══════════════════════════════════════════════════════════════════════════════

class TestCitationVerifier(unittest.TestCase):
    def test_verify_fully_grounded(self):
        c = Citation(source_title="Income Tax Act", section="54", page="324")
        source = "We read Section 54 of the Income Tax Act on page 324."
        res = CitationVerifier.verify(c, source)

        self.assertTrue(res["verified"])
        self.assertEqual(len(res["warnings"]), 0)
        self.assertEqual(res["confidence"], 1.0)

    def test_verify_missing_section(self):
        c = Citation(source_title="Income Tax Act", section="100", page="324")
        source = "We read Section 54 of the Income Tax Act on page 324."
        res = CitationVerifier.verify(c, source)

        self.assertFalse(res["verified"])
        self.assertEqual(len(res["warnings"]), 1)
        self.assertIn("Section '100'", res["warnings"][0])

    def test_verify_empty_source_text(self):
        c = Citation(source_title="Income Tax Act", section="54")
        res = CitationVerifier.verify(c, "")
        self.assertFalse(res["verified"])
        self.assertEqual(res["confidence"], 0.0)
        self.assertIn("empty", res["warnings"][0].lower())

    def test_section_word_boundary_no_false_positive(self):
        """Section '54' should NOT match text that only contains '154' or '540'."""
        c = Citation(source_title="Income Tax Act", section="54")
        source = "We discuss provisions 154 and 5400 of the Income Tax Act."
        res = CitationVerifier.verify(c, source)

        # Section 54 is not grounded — should have a warning for it
        section_warnings = [w for w in res["warnings"] if "Section" in w]
        self.assertEqual(len(section_warnings), 1)

    def test_page_word_boundary_no_false_positive(self):
        """Page '5' should NOT match text that only contains '50', '500', etc."""
        c = Citation(source_title="Income Tax Act", section="54", page="5")
        source = "We read Section 54 of the Income Tax Act on page 50."
        res = CitationVerifier.verify(c, source)

        page_warnings = [w for w in res["warnings"] if "Page" in w]
        self.assertEqual(len(page_warnings), 1)


# ══════════════════════════════════════════════════════════════════════════════
# CitationExporter
# ══════════════════════════════════════════════════════════════════════════════

class TestCitationExporter(unittest.TestCase):
    def test_export_table_of_authorities(self):
        citations = [
            Citation(source_title="Income Tax Act", section="54"),
            Citation(source_title="Income Tax Act", section="54"),  # Duplicate
            Citation(source_title="Smith v. Jones", volume="123", reporter="F.3d", first_page="456", year="2010")
        ]

        table = CitationExporter.export_table_of_authorities(citations, style="statutory")

        self.assertIn("Table of Authorities", table)
        # Deduplication check: "Section 54, Income Tax Act" should only appear once
        self.assertEqual(table.count("Income Tax Act"), 1)

    def test_export_json(self):
        citations = [Citation(source_title="Income Tax Act", section="54")]
        json_str = CitationExporter.export_json(citations)
        data = json.loads(json_str)

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["source_title"], "Income Tax Act")
        self.assertEqual(data[0]["section"], "54")

    def test_append_to_document(self):
        citations = [Citation(source_title="Income Tax Act", section="54")]
        doc = "Draft content."
        result = CitationExporter.append_to_document(doc, citations, style="statutory")

        self.assertTrue(result.startswith("Draft content."))
        self.assertIn("Table of Authorities", result)

    def test_append_to_document_empty_citations(self):
        doc = "Draft content."
        result = CitationExporter.append_to_document(doc, [], style="statutory")
        # No changes when no citations
        self.assertEqual(result, doc)

    def test_export_footnotes_basic(self):
        citations = [
            Citation(source_title="Income Tax Act", section="54"),
            Citation(source_title="Smith v. Jones", volume="123", reporter="F.3d", first_page="456", year="2010"),
        ]
        markers, footnote_block = CitationExporter.export_footnotes(citations, style="statutory")

        self.assertEqual(len(markers), 2)
        self.assertEqual(markers[0], "[^1]")
        self.assertEqual(markers[1], "[^2]")
        self.assertIn("[^1]:", footnote_block)
        self.assertIn("Income Tax Act", footnote_block)
        self.assertIn("[^2]:", footnote_block)

    def test_export_footnotes_deduplication(self):
        """Duplicate citations should share the same footnote marker."""
        c = Citation(source_title="Income Tax Act", section="54")
        markers, footnote_block = CitationExporter.export_footnotes([c, c, c], style="statutory")

        self.assertEqual(len(markers), 3)
        # All should point to footnote 1
        self.assertEqual(markers, ["[^1]", "[^1]", "[^1]"])
        # Only one footnote definition
        self.assertEqual(footnote_block.count("[^1]:"), 1)

    def test_export_footnotes_empty(self):
        markers, footnote_block = CitationExporter.export_footnotes([])
        self.assertEqual(markers, [])
        self.assertEqual(footnote_block, "")

    def test_export_footnotes_bluebook_style(self):
        citations = [
            Citation(source_title="Smith v. Jones", volume="123", reporter="F.3d", first_page="456", year="2010"),
        ]
        markers, footnote_block = CitationExporter.export_footnotes(citations, style="bluebook")
        self.assertIn("Smith v. Jones, 123 F.3d 456 (2010)", footnote_block)


# ══════════════════════════════════════════════════════════════════════════════
# Citation Agent Node
# ══════════════════════════════════════════════════════════════════════════════

class TestCitationAgentNode(unittest.TestCase):
    @patch("agents.citation.agent.CitationBuilder")
    @patch("agents.citation.agent.CitationVerifier")
    def test_citation_node_execution(self, mock_verifier_cls, mock_builder_cls):
        # Setup builder mock
        mock_builder = MagicMock()
        mock_builder.extract_from_text.return_value = [
            Citation(source_title="Income Tax Act", section="54")
        ]
        mock_builder_cls.return_value = mock_builder

        # Setup verifier mock
        mock_verifier = MagicMock()
        mock_verifier.verify.return_value = {"verified": True, "confidence": 1.0, "warnings": []}
        mock_verifier_cls.return_value = mock_verifier

        from agents.citation.agent import citation_node

        state = _make_state(
            research_data=["Section 54 of the Income Tax Act."],
            draft_content="Drafting legal letter.",
        )
        result = citation_node(state)

        self.assertIn("draft_content", result)
        self.assertIn("Table of Authorities", result["draft_content"])
        self.assertEqual(len(result["citations"]), 1)
        self.assertEqual(result["citations"][0], "Section 54, Income Tax Act")


if __name__ == "__main__":
    unittest.main()
