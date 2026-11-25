from langgraph.graph import StateGraph, END
from graph.state import AgentState

# Import nodes from the new agents directories
from agents.supervisor.agent import supervisor_node
from agents.planner.agent import planner_node
from agents.research.agent import research_node
from agents.drafting.agent import drafting_node
from agents.citation.agent import citation_node
from agents.review.agent import review_node
from agents.contract.agent import contract_node
from agents.summarizer.agent import summarizer_node
from agents.compliance.agent import compliance_node
from agents.calculator.agent import calculator_node
from agents.reasoning.agent import reasoning_node
from agents.qa.agent import qa_node
from agents.rag.agent import rag_node

from graph.conditions.routing import route_supervisor, route_reviewer

def create_graph():
    """Compiles and returns the multi-agent state graph."""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("research", research_node)
    workflow.add_node("drafting", drafting_node)
    workflow.add_node("citation", citation_node)
    workflow.add_node("review", review_node)
    
    workflow.add_node("contract", contract_node)
    workflow.add_node("summarizer", summarizer_node)
    workflow.add_node("compliance", compliance_node)
    workflow.add_node("calculator", calculator_node)
    workflow.add_node("reasoning", reasoning_node)
    workflow.add_node("qa", qa_node)           # lightweight Q&A — no document analysis
    workflow.add_node("rag", rag_node)         # answers queries using uploaded docs
    
    # Set entry point
    workflow.set_entry_point("supervisor")
    
    # Supervisor conditionally routes to specific tasks
    workflow.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "planner": "planner",
            "contract": "contract",
            "summarizer": "summarizer",
            "compliance": "compliance",
            "calculator": "calculator",
            "reasoning": "reasoning",
            "qa": "qa",
            "rag": "rag",
            "__end__": END,
        }
    )
    
    # Planner -> Research -> Drafting -> Citation -> Review
    workflow.add_edge("planner", "research")
    workflow.add_edge("research", "drafting")
    workflow.add_edge("drafting", "citation")
    workflow.add_edge("citation", "review")
    
    # Reviewer conditionally goes back to Planner or END
    workflow.add_conditional_edges(
        "review",
        route_reviewer,
        {"planner": "planner", "__end__": END}
    )
    
    # All terminal nodes go directly to END
    workflow.add_edge("contract", END)
    workflow.add_edge("summarizer", END)
    workflow.add_edge("compliance", END)
    workflow.add_edge("calculator", END)
    workflow.add_edge("reasoning", END)
    workflow.add_edge("qa", END)              # QA also terminates after answering
    workflow.add_edge("rag", END)
    
    return workflow.compile()
