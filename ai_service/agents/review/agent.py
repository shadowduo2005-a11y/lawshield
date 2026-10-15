from langchain_core.messages import HumanMessage, AIMessage
from graph.state import AgentState
from llm.providers.factory import get_llm_provider
import json
import logging
import re

logger = logging.getLogger(__name__)

# Hard cap on rejection loops — after this many total research iterations,
# the reviewer is forced to approve regardless of quality, preventing an
# infinite planner → research → drafting → citation → review → planner cycle.
_MAX_REVIEW_REJECTIONS = 2


def review_node(state: AgentState) -> dict:
    """Reviews the final drafted and cited content against the plan and request.

    Returns ``review_status`` of ``"approved"`` or ``"rejected"``, and appends
    the synthesised final answer to ``messages`` as an AIMessage.

    Infinite-loop guard: if the pipeline has already run ``_MAX_REVIEW_REJECTIONS``
    rejection cycles (measured by the number of accumulated research_data entries),
    the reviewer is forced to approve the current draft.
    """
    # ── Infinite-loop guard ───────────────────────────────────────────────────
    research_iterations = len(state.get("research_data") or [])
    if research_iterations >= _MAX_REVIEW_REJECTIONS:
        logger.warning(
            "Review node: reached max rejection cap (%d iterations) — "
            "force-approving draft to prevent infinite loop.",
            research_iterations,
        )
        draft = state.get("draft_content", "")
        return {
            "review_status": "approved",
            "messages": [AIMessage(content=draft or "I was unable to produce a complete answer. Please try rephrasing your question.")],
        }

    model = get_llm_provider().get_model()

    plan = state.get("plan", "")
    draft = state.get("draft_content", "")
    # Use the first message as the original user request context
    user_req = ""
    messages = state.get("messages") or []
    for m in messages:
        if hasattr(m, "type") and m.type == "human":
            user_req = m.content
            break

    prompt = f"""You are a Legal Reviewer agent.
Review the following drafted response against the original request and plan.
Determine if it fully answers the user's request and is legally sound.
Return a JSON object with:
  - "status": must be exactly "approved" or "rejected"
  - "final_answer": the synthesised final response to show the user

Only reject if the draft has serious factual errors or completely misses the request.
When in doubt, approve.

Request: {user_req}
Plan: {plan}
Drafted Response: {draft}
"""

    response = model.invoke([HumanMessage(content=prompt)])

    try:
        # Extract JSON robustly
        from utils.json import parse_json_object
        data = parse_json_object(response.content)

        status = data.get("status", "approved")
        # Normalise — only accept exact "approved" / "rejected"
        if status not in ("approved", "rejected"):
            logger.warning("Unexpected review status %r — defaulting to 'approved'", status)
            status = "approved"

        final_answer = data.get("final_answer") or draft

    except Exception as exc:
        # Parse failure → approve with full draft so we don't loop
        logger.warning("Review node failed to parse LLM JSON (%s) — defaulting to approved.", exc)
        status = "approved"
        final_answer = response.content or draft

    logger.info("Review node: status=%s", status)
    return {
        "review_status": status,
        "messages": [AIMessage(content=final_answer)],
    }
