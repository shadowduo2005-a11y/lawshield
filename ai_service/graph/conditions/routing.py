from graph.state import AgentState
from typing import Literal
import logging

logger = logging.getLogger(__name__)

# Maximum number of research iterations before the reviewer is forced to
# approve (belt-and-suspenders alongside the review node's own cap).
_MAX_RESEARCH_ITERATIONS = 2


def route_supervisor(
    state: AgentState,
) -> Literal["planner", "contract", "summarizer", "compliance", "calculator", "reasoning", "qa", "rag", "__end__"]:
    """Route based on Supervisor's decision."""
    next_node = state.get("next_node", "")
    if next_node in ("FINISH", "__end__"):
        logger.debug("route_supervisor: routing to __end__ (next_node=%r)", next_node)
        return "__end__"
    if next_node in ("contract", "summarizer", "compliance", "calculator", "reasoning", "qa", "rag"):
        logger.debug("route_supervisor: routing to %r", next_node)
        return next_node
    # Default: planner for multi-step research pipelines or any unrecognised value
    logger.debug("route_supervisor: defaulting to planner (next_node=%r)", next_node)
    return "planner"


def route_reviewer(state: AgentState) -> Literal["planner", "__end__"]:
    """Route based on Reviewer's status.

    Returns ``"planner"`` only when:
      1. The reviewer explicitly rejected the draft, AND
      2. The number of completed research iterations is still below the cap.

    In all other cases (approved, parse failure, cap reached) routes to ``"__end__"``.
    """
    status = state.get("review_status", "approved")
    research_count = len(state.get("research_data") or [])

    if status == "rejected" and research_count < _MAX_RESEARCH_ITERATIONS:
        logger.info(
            "route_reviewer: rejected — routing back to planner (iteration %d/%d)",
            research_count,
            _MAX_RESEARCH_ITERATIONS,
        )
        return "planner"

    if status == "rejected":
        logger.warning(
            "route_reviewer: rejected but cap reached (%d iterations) — routing to __end__",
            research_count,
        )

    return "__end__"
