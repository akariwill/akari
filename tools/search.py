from langchain.tools import tool
from duckduckgo_search import DDGS

@tool
def search_web(query: str) -> str:
    """Searches the web for the given query and returns the results."""
    with DDGS() as ddgs:
        results = [r for r in ddgs.text(query, max_results=5)]
        return results if results else "No results found."