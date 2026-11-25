"""
Supervisor node – routes the user request to the correct specialist agent.

Routing table
─────────────
rag         → ALL questions about documents, contracts, agreements, policies, uploaded files,
              specific clauses, sections, notice periods, terms, liabilities, or document queries
planner     → full research pipeline (Planner → Research → Drafting → Citation → Review)
contract    → ContractReview agent
summarizer  → Summariser agent
compliance  → Compliance agent
calculator  → Date deadlines, damages, capital gain, or any maths
qa          → General factual / conversational Indian legal Q&A (e.g., "what is habeas corpus?")
reasoning   → Deep analysis of an actual legal document/contract pasted in the prompt
FINISH      → Pure greetings / small-talk with zero legal content
"""
from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage

from graph.state import AgentState
from llm.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)

_VALID_ROUTES = {
    "planner", "contract", "summarizer", "compliance",
    "calculator", "qa", "reasoning", "rag", "FINISH",
}


def supervisor_node(state: AgentState) -> dict:
    """Analyse the latest user message and pick the next agent."""
    model = get_llm_provider().get_model()

    last_human = next(
        (m.content for m in reversed(state["messages"]) if m.type == "human"),
        "",
    )

    recent_msgs = state.get("messages", [])[-6:]
    conv_history = "\n".join(
        f"{'User' if getattr(m, 'type', '') == 'human' else 'Assistant'}: {m.content}"
        for m in recent_msgs
        if getattr(m, "type", "") in ("human", "ai")
    )

    prompt = f"""You are a Supervisor in a legal AI system. Route the user's message to exactly one agent.

ROUTES:
- "rag"        → Default for ANY question about a document, contract, agreement, policy, uploaded file/PDF, 
                  specific clause, section, notice period, salary, liability, termination, terms, or document query.
                  Examples: "what is the termination clause?", "what are the payment terms?", "summarise the uploaded document",
                  "what is the notice period?", "what does section 5 say?", "what is the effective date of the contract?",
                  "who are the parties in the agreement?", "what are the liabilities under section 3?"
- "reasoning"  → ONLY when the user pastes the ACTUAL FULL TEXT of a legal contract or clause directly inside this message
                  AND asks for a risk analysis, redline review, or deep legal risk assessment.
- "qa"         → ONLY for general, abstract Indian legal knowledge questions that do NOT refer to any document or contract.
                  Examples: "what is habeas corpus?", "who drafted the Indian constitution?",
                  "what does GDPR stand for?", "explain force majeure in general", "what is Section 302 IPC?"
- "planner"    → Tasks requiring original multi-step research + drafting: "write me a motion to dismiss", "draft a cease and desist letter"
- "contract"   → Contract-specific comparison tasks: "compare these two agreements", "draft an NDA"
- "summarizer" → "summarise this legal document" (when document text is pasted in message)
- "compliance" → "does this policy comply with GDPR?" (when policy text is pasted in message)
- "calculator" → Any calculation: deadlines, damages, statute of limitations dates, percentages
- "FINISH"     → Pure greetings, small-talk, pleasantries, general introductions, or questions about past conversation history: "hi", "hello", "who are you", "what did I ask before?", "what is my name?"

DECISION RULES:
1. If the message contains "fromdocument", "from document", "according to document", "according to contract", "according to NDA", "based on uploaded document", or asks about a document, contract, agreement, PDF, clause, section, terms, notice period, salary, liability, termination, or uploaded file → MUST route to "rag".
2. If the user pasted multi-paragraph contract text in the message and asks for risk analysis → "reasoning"
3. If the user asks a general abstract legal theory/statute question (with NO reference to any document, contract, or "fromdocument") → "qa"
4. If the query is a calculation or date deadline → "calculator"
5. If pure greeting, small-talk, pleasantry, introduction, or asking about past conversation history → "FINISH"
6. Default when in doubt → "rag"

Respond with ONLY valid JSON: {{"next": "<route>"}}

Recent Conversation History:
{conv_history}

Latest User Message: {last_human}
"""

    response = model.invoke([HumanMessage(content=prompt)])
    next_node = _parse_next(response.content)
    logger.info("Supervisor routed to: %s", next_node)
    return {"next_node": next_node}


def _parse_next(raw: str) -> str:
    from utils.json import parse_json_object
    try:
        data = parse_json_object(raw)
        next_node = data.get("next", "rag")
        if next_node not in _VALID_ROUTES:
            logger.warning("Supervisor returned unknown route %r – defaulting to rag", next_node)
            return "rag"
        return next_node
    except Exception as exc:
        logger.error("Failed to parse Supervisor response: %s – defaulting to rag", exc)
        return "rag"
