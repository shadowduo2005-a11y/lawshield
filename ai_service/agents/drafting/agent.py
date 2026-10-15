from langchain_core.messages import HumanMessage
from graph.state import AgentState
from llm.providers.factory import get_llm_provider

def drafting_node(state: AgentState) -> dict:
    """Drafts a legal document/response based on research."""
    model = get_llm_provider().get_model()
    
    plan = state.get("plan", "")
    latest_research = state["research_data"][-1] if state.get("research_data") else ""
    user_req = next(
        (m.content for m in reversed(state["messages"]) if m.type == "human"),
        "",
    )
    
    prompt = f"""You are a Legal Drafting agent.
Based on the following research and plan, draft a comprehensive and formal legal response to the user's request.

Request: {user_req}
Plan: {plan}
Research: {latest_research}

Write the draft:
"""
    response = model.invoke([HumanMessage(content=prompt)])
    
    return {"draft_content": response.content}
