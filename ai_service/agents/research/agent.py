"""
Research node – executes the Planner's plan using bound tools.

Tools available
───────────────
legal_search    – semantic search over internal Qdrant/ES index
web_search      – live internet search via DuckDuckGo
format_citation – formats Indian/Bluebook legal citations found during research
"""
from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage, ToolMessage

from graph.state import AgentState
from llm.providers.factory import get_llm_provider
from tools.search import legal_search
from tools.web import web_search
from tools.citation import format_citation

logger = logging.getLogger(__name__)

_TOOLS = [legal_search, web_search, format_citation]
_TOOL_MAP = {t.name: t for t in _TOOLS}


def research_node(state: AgentState) -> dict:
    """Execute the research plan with tool-calling."""
    base_model = get_llm_provider().get_model()
    model = base_model.bind_tools(_TOOLS)

    plan = state.get("plan", "")
    user_req = next(
        (m.content for m in reversed(state["messages"]) if m.type == "human"),
        "",
    )

    prompt = f"""You are an Indian Legal Researcher.
Execute the plan below using your tools (legal_search / web_search / format_citation).
Collect relevant Indian case law (Supreme Court of India, High Courts), statutes (IPC/BNS, CrPC/BNSS, CPC,
Contract Act, Companies Act, GST, SEBI, IT Act, etc.), and facts to support the final answer.
Always prefer Indian primary sources over foreign law.
When you find a specific case or statute citation, use format_citation to format it in proper Indian legal style.

Plan:
{plan}

Original Request: {user_req}
"""

    # First LLM call – may include tool_calls
    ai_msg = model.invoke([HumanMessage(content=prompt)])
    messages_to_add = [ai_msg]

    # Execute any requested tools and collect results
    if hasattr(ai_msg, "tool_calls") and ai_msg.tool_calls:
        for tc in ai_msg.tool_calls:
            tool_fn = _TOOL_MAP.get(tc["name"])
            if tool_fn:
                try:
                    result = tool_fn.invoke(tc["args"])
                except Exception as exc:
                    result = f"Tool error: {exc}"
            else:
                result = f"Unknown tool: {tc['name']}"

            messages_to_add.append(
                ToolMessage(content=str(result), tool_call_id=tc["id"])
            )

        # Second pass: let LLM synthesise tool results into research findings
        synthesis_msg = model.invoke(
            [HumanMessage(content=prompt)] + messages_to_add
        )
        research_text = synthesis_msg.content
    else:
        research_text = ai_msg.content

    existing = state.get("research_data") or []
    logger.info("Research produced %d chars", len(research_text))
    return {"research_data": existing + [research_text]}
