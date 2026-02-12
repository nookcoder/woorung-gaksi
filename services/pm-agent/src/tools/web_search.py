import httpx
from langchain_core.tools import tool
from src.shared.config import config

@tool
def web_search(query: str) -> str:
    """
    Search the web for information using Tavily API.
    Use this when you need current events, documentation, or facts.
    """
    if not config.TAVILY_API_KEY:
        # Fallback for now if key is missing, to avoid crashing the whole agent
        return "Error: TAVILY_API_KEY not found in configuration. Please add it to your .env file."

    api_key = config.TAVILY_API_KEY
    url = "https://api.tavily.com/search"
    
    try:
        # Using sync client for simplicity in this synchronous node
        with httpx.Client() as client:
            response = client.post(
                url, 
                json={
                    "api_key": api_key, 
                    "query": query, 
                    "search_depth": "basic",
                    "max_results": 3
                },
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            
            results = data.get("results", [])
            if not results:
                return "No results found."
                
            formatted_results = []
            for result in results:
                formatted_results.append(f"- **{result['title']}**: {result['content']} ({result['url']})")
                
            return "\n".join(formatted_results)
            
    except Exception as e:
        return f"Error executing search: {str(e)}"
