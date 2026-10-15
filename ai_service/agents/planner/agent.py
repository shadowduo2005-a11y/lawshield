"""
Planner node – builds a concise step-by-step research plan.
"""
from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage

from graph.state import AgentState
from llm.providers.factory import get_llm_provider

logger = logging.getLogger(__name__)


def planner_node(state: AgentState) -> dict:
    """Generate a research plan from the user's request."""
    model = get_llm_provider().get_model()

    # Always read the last HUMAN message – messages[0] could now be SystemMessage
    user_req = next(
        (m.content for m in reversed(state["messages"]) if m.type == "human"),
        "",
    )

    prompt = f"""You are a Legal Planner specialised in Indian law.
Create a numbered, step-by-step research plan that will allow a researcher to fully answer the following legal request under Indian law.
Prioritise: Constitution of India, IPC/BNS, CrPC/BNSS, CPC, Contract Act, Companies Act, GST, SEBI, Supreme Court of India judgments, and relevant High Court decisions.
Be concise (max 5 steps).

Request: {user_req}
"""

    response = model.invoke([HumanMessage(content=prompt)])
    logger.info("Planner produced plan (%d chars)", len(response.content))
    return {"plan": response.content}
