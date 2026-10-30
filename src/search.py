import os

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    return _client


def search_web(query, max_results=6, search_depth="advanced"):
    client = _get_client()
    response = client.search(query, max_results=max_results, search_depth=search_depth)
    return [
        {"title": r["title"], "url": r["url"], "content": r["content"]}
        for r in response["results"]
    ]
