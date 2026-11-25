from langchain_core.messages import HumanMessage, AIMessage
from graph.state import AgentState
from llm.providers.factory import get_llm_provider

def summarizer_node(state: AgentState) -> dict:
    """Specialized agent for summarizing text."""
    model = get_llm_provider().get_model()
    
    user_req = next(
        (m.content for m in reversed(state["messages"]) if m.type == "human"),
        "",
    )
    
    prompt = f"""You are a Legal Summarizer agent.
Provide a concise, accurate summary of the following legal text or request.

Request: {user_req}

Write your summary.
"""
    response = model.invoke([HumanMessage(content=prompt)])
    
    return {
        "summary": response.content,
        "messages": [AIMessage(content=response.content)]
    }
