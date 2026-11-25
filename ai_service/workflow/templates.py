"""
templates.py – defines predefined legal workflow templates.

Templates:
  contract_review   – Upload a contract, extract key clauses, identify risks, compile suggestions.
  legal_research    – Define research questions, gather Indian legal sources, synthesise findings.
  compliance_check  – Identify applicable Indian laws, check compliance, generate gap report.
"""
from __future__ import annotations

from typing import Any, Dict

WORKFLOW_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "contract_review": {
        "name": "Contract Risk & Mitigation Report",
        "description": (
            "Upload a contract, extract key clauses under Indian law, identify legal risks, "
            "and compile mitigation suggestions. Required input: 'contract_text'."
        ),
        "required_inputs": ["contract_text"],
        "steps": [
            {
                "id": "extract_clauses",
                "name": "Extract Clauses",
                "input_keys": ["contract_text"],
                "output_keys": ["extracted_clauses"],
            },
            {
                "id": "review_clauses",
                "name": "Review Clauses",
                "input_keys": ["extracted_clauses"],
                "output_keys": ["clause_reviews"],
            },
            {
                "id": "find_risks",
                "name": "Find Risks",
                "input_keys": ["clause_reviews"],
                "output_keys": ["identified_risks"],
            },
            {
                "id": "draft_suggestions",
                "name": "Draft Suggestions",
                "input_keys": ["identified_risks"],
                "output_keys": ["mitigation_suggestions"],
            },
            {
                "id": "generate_report",
                "name": "Generate Report",
                "input_keys": ["extracted_clauses", "identified_risks", "mitigation_suggestions"],
                "output_keys": ["final_report"],
            },
        ],
    },

    "legal_research": {
        "name": "Legal Research Memorandum",
        "description": (
            "Given a legal topic or question, define research questions, gather relevant "
            "Indian statutes and case law, synthesise findings, and produce a formal "
            "Legal Research Memorandum. Required input: 'research_topic'."
        ),
        "required_inputs": ["research_topic"],
        "steps": [
            {
                "id": "define_research_questions",
                "name": "Define Research Questions",
                "input_keys": ["research_topic"],
                "output_keys": ["research_questions"],
            },
            {
                "id": "gather_sources",
                "name": "Gather Legal Sources",
                "input_keys": ["research_questions"],
                "output_keys": ["gathered_sources"],
            },
            {
                "id": "synthesise_findings",
                "name": "Synthesise Findings",
                "input_keys": ["research_questions", "gathered_sources"],
                "output_keys": ["synthesis"],
            },
            {
                "id": "generate_research_memo",
                "name": "Generate Research Memo",
                "input_keys": ["research_topic", "synthesis"],
                "output_keys": ["research_memo"],
            },
        ],
    },

    "compliance_check": {
        "name": "Compliance Gap Report",
        "description": (
            "Review a policy or document against applicable Indian laws and regulations "
            "(SEBI, RBI, IT Act, DPDP Act 2023, GST, Labour Codes, etc.), identify gaps, "
            "and generate a prioritised Compliance Gap Report. Required input: 'policy_text'."
        ),
        "required_inputs": ["policy_text"],
        "steps": [
            {
                "id": "identify_applicable_laws",
                "name": "Identify Applicable Indian Laws",
                "input_keys": ["policy_text"],
                "output_keys": ["applicable_laws"],
            },
            {
                "id": "check_compliance",
                "name": "Check Compliance",
                "input_keys": ["policy_text", "applicable_laws"],
                "output_keys": ["compliance_gaps"],
            },
            {
                "id": "generate_compliance_report",
                "name": "Generate Compliance Gap Report",
                "input_keys": ["applicable_laws", "compliance_gaps"],
                "output_keys": ["compliance_report"],
            },
        ],
    },
}
