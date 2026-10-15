"""
Calculator node – uses bound tools to perform legal maths.
"""
from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from graph.state import AgentState
from llm.providers.factory import get_llm_provider
from tools.calculator import calculate_math
from tools.timeline import court_timeline

logger = logging.getLogger(__name__)

_TOOLS = [calculate_math, court_timeline]
_TOOL_MAP = {t.name: t for t in _TOOLS}


def calculator_node(state: AgentState) -> dict:
    """Perform legal calculations with tool support."""
    base_model = get_llm_provider().get_model()
    model = base_model.bind_tools(_TOOLS)

    user_req = next(
        (m.content for m in reversed(state["messages"]) if m.type == "human"),
        "",
    )

    prompt = f"""You are a Legal Calculator.
Use calculate_math for arithmetic/percentages and court_timeline for date-based deadlines.
Show your working clearly.

Request: {user_req}
"""

    ai_msg = model.invoke([HumanMessage(content=prompt)])
    extra_messages = [ai_msg]

    if hasattr(ai_msg, "tool_calls") and ai_msg.tool_calls:
        for tc in ai_msg.tool_calls:
            tool_fn = _TOOL_MAP.get(tc["name"])
            try:
                result = tool_fn.invoke(tc["args"]) if tool_fn else f"Unknown tool: {tc['name']}"
            except Exception as exc:
                result = f"Tool error: {exc}"
            extra_messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

        synthesis = model.invoke([HumanMessage(content=prompt)] + extra_messages)
        answer = synthesis.content
    else:
        answer = ai_msg.content

    logger.info("Calculator produced answer (%d chars)", len(answer))
    return {
        "calculation_result": answer,
        "messages": [AIMessage(content=answer)],
    }
