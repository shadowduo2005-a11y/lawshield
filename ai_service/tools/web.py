"""
tools/web.py – Defines the web search tool for live data retrieval.
"""
from langchain_core.tools import tool

try:
    from langchain_community.tools import DuckDuckGoSearchRun
    HAS_DDG = True
except ImportError:
    HAS_DDG = False


@tool
def web_search(query: str, max_results: int = 3) -> str:
    """
    Perform a live web search using a free search API (like DuckDuckGo or similar).
    This allows agents to find up-to-date public information.
    For this phase, this wraps a public search endpoint.
    """
    try:
        if HAS_DDG:
            search = DuckDuckGoSearchRun()
            # Note: DuckDuckGoSearchRun might not natively support max_results via invoke
            # but we accept the parameter to conform to general tool signatures.
            return str(search.invoke(query))
        
        return (
            f"Mock Search Result for '{query}': Current laws or regulations are constantly "
            f"evolving. Please ensure `duckduckgo-search` is installed for real results "
            f"(max_results={max_results} ignored in mock)."
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"Error executing web search: {str(e)}"
