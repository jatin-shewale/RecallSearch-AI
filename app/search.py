import requests
from app.config import TAVILY_API_KEY, MAX_SEARCH_RESULTS

class SearchError(RuntimeError):
    pass

def web_search(query: str):
    """The agent's sole external tool: Tavily web search."""
    if not TAVILY_API_KEY:
        raise SearchError("TAVILY_API_KEY is missing. Add it to your .env file.")
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "topic": "general",
                "max_results": MAX_SEARCH_RESULTS,
                "include_answer": False,
                "include_raw_content": False
            },
            timeout=12
        )
        response.raise_for_status()
        payload = response.json()
        results = []
        for item in payload.get("results", []):
            results.append({
                "title": item.get("title", "Untitled"),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": item.get("score")
            })
        return results
    except requests.RequestException as exc:
        raise SearchError(f"Web search failed: {exc}") from exc
