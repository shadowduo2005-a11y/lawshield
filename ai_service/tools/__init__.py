"""
tools/ – LangGraph-compatible tools for LawShield legal agents.

Available tools:
    - legal_search      : Hybrid RAG retrieval from the internal legal knowledge base
    - web_search        : Live web search via DuckDuckGo
    - calculate_math    : Safe mathematical expression evaluator
    - format_citation   : Bluebook and Indian legal citation formatter
    - compare_documents : Unified diff comparison between two legal documents
    - court_timeline    : Procedural deadline calculator
"""
from tools.search import legal_search
from tools.web import web_search
from tools.calculator import calculate_math
from tools.citation import format_citation
from tools.compare import compare_documents
from tools.timeline import court_timeline

# Convenience list for agent tool registration
ALL_TOOLS = [
    legal_search,
    web_search,
    calculate_math,
    format_citation,
    compare_documents,
    court_timeline,
]

__all__ = [
    "legal_search",
    "web_search",
    "calculate_math",
    "format_citation",
    "compare_documents",
    "court_timeline",
    "ALL_TOOLS",
]
