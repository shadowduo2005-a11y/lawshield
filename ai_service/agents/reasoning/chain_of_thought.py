"""
chain_of_thought.py – core reasoning agent conducting structured legal thinking.

This module prompts the LLM to think step-by-step:
1. Analyze the context/contract.
2. Find key risks or legal issues.
3. Explain the risks/issues and their implications.
4. Suggest concrete changes, clauses, or modifications to mitigate them.

A secondary `refine()` method handles self-correction passes when the initial
analysis is flagged by the Reviewer or Verifier agents.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from llm.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are an elite Indian legal reasoning engine specialised in the laws of India. "
    "Your task is to perform an exhaustive, step-by-step reasoning process (Chain-of-Thought) over legal texts.\n"
    "Apply Indian law as your primary framework: Constitution of India, IPC / Bharatiya Nyaya Sanhita (BNS), "
    "CrPC / BNSS, CPC, Indian Evidence Act / Bharatiya Sakshya Adhiniyam, Contract Act 1872, "
    "Companies Act 2013, Transfer of Property Act, SEBI Regulations, GST laws, IT Act 2000, "
    "Consumer Protection Act, RTI Act, and relevant judgments of the Supreme Court of India and High Courts.\n"
    "Use Indian legal terminology throughout (e.g., 'petition', 'FIR', 'writ', 'Magistrate', 'Sessions Court').\n\n"
    # -----------------------------------------------------------------------
    # Anti-hallucination instruction — CRITICAL for a legal AI
    # -----------------------------------------------------------------------
    "CRITICAL RULE — NO HALLUCINATION: You MUST cite a statute, section number, case name, "
    "or legal rule ONLY if it is explicitly mentioned or clearly referenced in the provided "
    "contract/document text. Do NOT invent, infer, or recall statutes from your training data "
    "to fill gaps. If the document does not reference a particular statute, do not cite it. "
    "When in doubt, describe the legal principle in plain language without a statute citation.\n\n"
    # -----------------------------------------------------------------------
    "You must structure your thinking into the following distinct sections:\n\n"
    "1. ANALYSIS: Break down the document, key provisions, parties, and obligations under applicable Indian law.\n"
    "2. RISKS FOUND: Identify hidden legal risks, liabilities, unfavourable clauses, or ambiguities under Indian law.\n"
    "3. RISK EXPLANATIONS: Explain the real-world operational and legal implications of each risk under Indian jurisdiction.\n"
    "4. SUGGESTED CHANGES: Provide specific redlines, revised clause text, or suggestions to mitigate the risks "
    "in compliance with Indian statutes and judicial precedents."
)


class LegalReasoningAgent:
    """
    Reasoning Agent responsible for executing the Legal Chain-of-Thought analysis.

    Provides two entrypoints:
    - ``think()``  – initial structured analysis of a contract/legal text.
    - ``refine()`` – targeted self-correction pass that incorporates auditor feedback.
    """

    def __init__(self, provider_name: str | None = None) -> None:
        self.provider_name = provider_name
        self._model = None  # Lazy-loaded

    @property
    def model(self):
        """Lazily initialises the LLM model on first access."""
        if self._model is None:
            self._model = get_llm_provider(self.provider_name).get_model()
        return self._model

    # ------------------------------------------------------------------
    # Primary reasoning pass
    # ------------------------------------------------------------------

    def think(self, context: str, user_query: str = "") -> str:
        """
        Executes a multi-stage reasoning process over the legal text/contract.

        Parameters
        ----------
        context : str
            The contract text or legal document content to analyze.
        user_query : str, optional
            A specific focus area or instruction from the user.

        Returns
        -------
        str
            Markdown text detailing the structured analysis, risk findings,
            explanations, and suggestions.
        """
        logger.info("Executing Legal Chain-of-Thought reasoning (initial pass)…")

        # Anti-hallucination guard: refuse to reason over trivially short context.
        # When context is near-empty the LLM will hallucinate statutes and clauses
        # to fill the void. 200 chars is a safe floor (a real clause is much longer).
        _MIN_CONTEXT_CHARS = 200
        if not context or len(context.strip()) < _MIN_CONTEXT_CHARS:
            logger.warning(
                "think() called with insufficient context (%d chars < %d min). "
                "Returning insufficiency notice to avoid hallucination.",
                len(context.strip()) if context else 0,
                _MIN_CONTEXT_CHARS,
            )
            return (
                "## Insufficient Document Context\n\n"
                "I cannot perform a legal risk analysis because the provided document content "
                "is too short or empty. Please upload the full legal document or contract and "
                "try again.\n\n"
                "_No statutes, clauses, or legal assessments have been generated to avoid "
                "hallucination on insufficient context._"
            )

        focus = (
            f"Focus particularly on: {user_query}"
            if user_query
            else "Conduct a general comprehensive risk review."
        )

        user_content = (
            f"Here is the legal text to analyze under Indian law:\n\n"
            f"--- START OF TEXT ---\n"
            f"{context}\n"
            f"--- END OF TEXT ---\n\n"
            f"{focus}\n\n"
            f"Please output your complete step-by-step reasoning under the four headers, "
            f"citing relevant Indian statutes, rules, and precedents ONLY where they are "
            f"explicitly referenced in the text above."
        )

        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]

        response = self.model.invoke(messages)
        return response.content

    # ------------------------------------------------------------------
    # Self-correction / refinement pass
    # ------------------------------------------------------------------

    def refine(
        self,
        context: str,
        initial_analysis: str,
        feedback: str = "",
        suggestions: Optional[List[str]] = None,
        grounding_warnings: Optional[List[str]] = None,
    ) -> str:
        """
        Produces a refined analysis by incorporating auditor feedback and
        grounding warnings from the Reviewer and Verifier agents.

        Parameters
        ----------
        context : str
            The original contract or legal text.
        initial_analysis : str
            The first-pass chain-of-thought output that needs correction.
        feedback : str
            High-level critique from the Reviewer Agent.
        suggestions : list[str], optional
            Specific improvement suggestions from the Reviewer Agent.
        grounding_warnings : list[str], optional
            Grounding / hallucination warnings from the Verifier Agent.

        Returns
        -------
        str
            A corrected, improved analysis respecting all four section headers.
        """
        logger.info("Executing Legal Chain-of-Thought reasoning (refinement pass)…")

        suggestions = suggestions or []
        grounding_warnings = grounding_warnings or []

        # Build a structured correction brief
        suggestion_block = (
            "\n".join(f"  • {s}" for s in suggestions)
            if suggestions
            else "  (none provided)"
        )
        warning_block = (
            "\n".join(f"  ⚠ {w}" for w in grounding_warnings)
            if grounding_warnings
            else "  (none)"
        )

        system_prompt = (
            _SYSTEM_PROMPT + "\n\n"
            "You are now performing a REFINEMENT PASS. "
            "You have been given your initial draft together with detailed auditor "
            "feedback. You must produce an improved analysis that:\n"
            "  1. Corrects every grounding warning by ensuring each claim is "
            "     directly supported by the contract text.\n"
            "  2. Addresses every suggestion from the reviewer.\n"
            "  3. Retains all four section headers (ANALYSIS, RISKS FOUND, "
            "     RISK EXPLANATIONS, SUGGESTED CHANGES).\n"
            "Do NOT repeat the original draft verbatim — produce genuine improvements."
        )

        user_content = (
            f"--- ORIGINAL CONTRACT ---\n"
            f"{context}\n\n"
            f"--- INITIAL ANALYSIS DRAFT ---\n"
            f"{initial_analysis}\n\n"
            f"--- REVIEWER FEEDBACK ---\n"
            f"{feedback or '(No general feedback provided.)'}\n\n"
            f"--- REVIEWER SUGGESTIONS ---\n"
            f"{suggestion_block}\n\n"
            f"--- GROUNDING WARNINGS (from Verifier) ---\n"
            f"{warning_block}\n\n"
            f"Please produce your refined legal analysis now."
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]

        response = self.model.invoke(messages)
        return response.content
