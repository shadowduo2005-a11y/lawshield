from langchain_core.messages import HumanMessage, AIMessage
from graph.state import AgentState
from llm.providers.factory import get_llm_provider

def compliance_node(state: AgentState) -> dict:
    """Specialized agent for compliance checks."""
    model = get_llm_provider().get_model()
    
    user_req = next(
        (m.content for m in reversed(state["messages"]) if m.type == "human"),
        "",
    )
    
    prompt = f"""You are a Legal Compliance agent.
Check the following text or request against standard legal compliance rules.
Highlight any regulatory risks or non-compliance issues.

Request: {user_req}

Write your compliance report.
"""
    response = model.invoke([HumanMessage(content=prompt)])
    
    return {
        "compliance_report": response.content,
        "messages": [AIMessage(content=response.content)]
    }
