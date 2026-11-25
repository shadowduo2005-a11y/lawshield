from typing import TypedDict, List, Annotated, Optional
import operator
from langchain_core.messages import BaseMessage


class AgentState(TypedDict, total=False):
    """The shared state of the multi-agent graph.

    ``total=False`` means all keys are optional at the TypedDict level, which
    lets LangGraph merge partial state dictionaries returned by each node
    without raising a KeyError for fields the node didn't touch.

    The ``messages`` field uses ``operator.add`` so every node can safely append
    new messages without overwriting the full list. All other fields are replaced
    (not merged) on each update — LangGraph's default behaviour for plain fields.
    """

    # Full conversation (system + history + new turn)
    messages: Annotated[List[BaseMessage], operator.add]

    # Routing decision made by the Supervisor
    next_node: str

    # ── Research pipeline fields ──────────────────────────────────────────────

    # Step-by-step resolution plan produced by Planner
    plan: str

    # Accumulated research snippets (one entry per Research iteration)
    research_data: List[str]

    # Draft produced by Drafting
    draft_content: str

    # Citations appended by Citation
    citations: List[str]

    # "approved" | "rejected" – set by Reviewer
    review_status: str

    # ── Specialised agent output fields ───────────────────────────────────────

    contract_analysis: str
    compliance_report: str
    summary: str
    calculation_result: str

    # ── Legal Reasoning outputs ──────────────────────────────────────────────

    # Full formatted reasoning output from the reasoning pipeline
    reasoning_output: str

    # Confidence score in [0.0, 1.0] from LegalConfidenceScorer
    reasoning_confidence: float

    # How many reasoning passes ran (1 = no refinement, 2 = refined once)
    reasoning_iterations: int
