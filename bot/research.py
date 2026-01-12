"""
AnyArchie Web Search
Uses Exa API for web search
"""
from exa_py import Exa
from typing import List, Dict, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import EXA_API_KEY


def search(query: str, num_results: int = 5) -> List[Dict]:
    """
    Search the web using Exa.
    
    Args:
        query: Search query
        num_results: Number of results to return
    
    Returns:
        List of results with title, url, and snippet
    """
    if not EXA_API_KEY:
        return []
    
    try:
        exa = Exa(api_key=EXA_API_KEY)
        results = exa.search_and_contents(
            query,
            type="auto",
            num_results=num_results,
            text={"max_characters": 500}
        )
        
        return [
            {
                "title": r.title or "No title",
                "url": r.url,
                "snippet": r.text[:500] if r.text else ""
            }
            for r in results.results
        ]
    except Exception as e:
        print(f"Search error: {e}")
        return []


def format_search_results(results: List[Dict]) -> str:
    """Format search results for display"""
    if not results:
        return "No results found."
    
    output = []
    for i, r in enumerate(results, 1):
        output.append(f"{i}. **{r['title']}**")
        output.append(f"   {r['url']}")
        if r['snippet']:
            # Truncate long snippets
            snippet = r['snippet'][:200] + "..." if len(r['snippet']) > 200 else r['snippet']
            output.append(f"   {snippet}")
        output.append("")
    
    return "\n".join(output)


def search_and_summarize(query: str, num_results: int = 5) -> str:
    """
    Search the web and return formatted results.
    For LLM summarization, pass these results to the chat function.
    """
    results = search(query, num_results)
    return format_search_results(results)
