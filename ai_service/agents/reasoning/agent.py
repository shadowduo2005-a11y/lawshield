"""
reasoning agent node – orchestrates the three-agent reasoning pipeline
(Reasoning Agent, Reviewer Agent, Verifier Agent) and computes the confidence score.

Pipeline:
  1. Initial chain-of-thought analysis via LegalReasoningAgent.think()
  2. Parallel audit by LegalReviewerAgent and LegalVerifierAgent
  3. Self-correction via LegalReasoningAgent.refine() if issues detected
  4. Re-audit on the refined output
  5. Confidence scoring via LegalConfidenceScorer
"""
from __future__ import annotations

import logging
from langchain_core.messages import AIMessage

from graph.state import AgentState
from .chain_of_thought import LegalReasoningAgent
from .reviewer import LegalReviewerAgent
from .verifier import LegalVerifierAgent
from .confidence import LegalConfidenceScorer

logger = logging.getLogger(__name__)


def _build_context(state: AgentState) -> str:
    """
    Assembles the richest possible contract context from the current state.

    Prioritises ``draft_content`` if available (it may contain refined clause
    text), then falls back to any research snippets, then to the last human
    message in the conversation history.
    """
    parts: list[str] = []

    # Highest fidelity: pre-drafted document content
    draft = state.get("draft_content", "")
    if draft:
        parts.append(f"[DRAFT DOCUMENT]\n{draft}")

    # Supplementary research data (retrieved chunks, retrieved statutes, etc.)
    research = state.get("research_data") or []
    if research:
        parts.append("[RESEARCH DATA]\n" + "\n---\n".join(research))

    # Planning context
    plan = state.get("plan", "")
    if plan:
        parts.append(f"[ANALYSIS PLAN]\n{plan}")

    if parts:
        return "\n\n".join(parts)

    # Fallback: extract the most recent human turn
    human_text = next(
        (m.content for m in reversed(state["messages"]) if m.type == "human"),
        "",
    )
    return human_text


def reasoning_node(state: AgentState) -> dict:
    """
    Executes the multi-agent legal reasoning pipeline on the user request/contract.

    Returns
    -------
    dict
        State updates including ``reasoning_output``, ``reasoning_confidence``,
        ``reasoning_iterations``, and an ``AIMessage`` appended to ``messages``.
    """
    logger.info("Starting Legal Reasoning multi-agent node…")

    # --- Build the richest possible context ---
    context = _build_context(state)

    # Extract the user's specific focus question (latest human message)
    user_query = next(
        (m.content for m in reversed(state["messages"]) if m.type == "human"),
        "",
    )

    # Initialise agents (models are lazy-loaded)
    reasoning_agent = LegalReasoningAgent()
    reviewer_agent = LegalReviewerAgent()
    verifier_agent = LegalVerifierAgent()

    # ── Step 1: Initial chain-of-thought ──────────────────────────────────────
    initial_analysis = reasoning_agent.think(context=context, user_query=user_query)

    # ── Step 2: First-pass review and verification ────────────────────────────
    reviewed = reviewer_agent.review(context=context, reasoning_output=initial_analysis)
    verified = verifier_agent.verify(context=context, reasoning_output=initial_analysis)

    final_analysis = initial_analysis
    iterations = 1  # Track how many reasoning passes occurred

    # ── Step 3: Self-correction (if reviewer or verifier flag issues) ─────────
    needs_revision = reviewed.get("review_status") == "needs_revision"
    not_grounded = not verified.get("grounded", True)

    if needs_revision or not_grounded:
        logger.info(
            "Reasoning output requires refinement (needs_revision=%s, grounded=%s). "
            "Initiating self-correction pass…",
            needs_revision,
            not not_grounded,
        )

        final_analysis = reasoning_agent.refine(
            context=context,
            initial_analysis=initial_analysis,
            feedback=reviewed.get("feedback", ""),
            suggestions=reviewed.get("suggestions", []),
            grounding_warnings=verified.get("warnings", []),
        )
        iterations = 2

        # Re-audit the refined output
        reviewed = reviewer_agent.review(context=context, reasoning_output=final_analysis)
        verified = verifier_agent.verify(context=context, reasoning_output=final_analysis)

    is_refined = iterations > 1

    # ── Step 4: Confidence scoring ────────────────────────────────────────────
    confidence = LegalConfidenceScorer.score(
        reasoning_output=final_analysis,
        reviewer_result=reviewed,
        verifier_result=verified,
    )

    breakdown = LegalConfidenceScorer.detailed_breakdown(
        reasoning_output=final_analysis,
        reviewer_result=reviewed,
        verifier_result=verified,
    )

    # ── Step 5: Format final output ───────────────────────────────────────────
    refinement_badge = " [REFINED]" if is_refined else ""
    sections_found = ", ".join(breakdown["sections_found"]) or "none detected"

    formatted_output = (
        f"# LEGAL RISK ASSESSMENT & REASONING{refinement_badge}\n"
        f"**Confidence Score:** {confidence:.2f}/1.00  "
        f"*(grounding: {breakdown['grounding']:.2f}, "
        f"reviewer: {breakdown['reviewer']:.2f}, "
        f"warnings: {breakdown['warnings']:.2f}, "
        f"structure: {breakdown['structure']:.2f})*\n\n"
        f"{final_analysis}\n\n"
        f"---\n"
        f"### 🛡️ Audit & Verification Summary\n"
        f"- **Grounding Status:** {'✅ Grounded' if verified.get('grounded') else '⚠️ Grounding Warnings'}\n"
        f"- **Review Status:** {reviewed.get('review_status', 'needs_revision').upper().replace('_', ' ')}\n"
        f"- **Auditor Feedback:** {reviewed.get('feedback', 'No additional feedback.')}\n"
        f"- **Sections Validated:** {sections_found}\n"
        f"- **Reasoning Iterations:** {iterations}\n"
    )

    if verified.get("warnings"):
        formatted_output += f"- **Grounding Warnings:** {', '.join(verified['warnings'])}\n"
    if reviewed.get("suggestions"):
        formatted_output += f"- **Suggestions for next steps:** {', '.join(reviewed['suggestions'])}\n"

    logger.info(
        "Legal Reasoning node completed (iterations=%d, confidence=%.2f).",
        iterations,
        confidence,
    )

    return {
        "reasoning_output": formatted_output,
        "reasoning_confidence": confidence,
        "reasoning_iterations": iterations,
        "messages": [AIMessage(content=formatted_output)],
    }
