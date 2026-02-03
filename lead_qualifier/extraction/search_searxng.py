import os
import requests

def searxng_search(query: str, k: int = 10) -> list[dict]:
    base = os.getenv("SEARXNG_URL", "http://localhost:8080").rstrip("/")
    timeout = int(os.getenv("SEARXNG_TIMEOUT_S", "20"))

    params = {
        "q": query,
        "format": "json",        # SearXNG Search API supports JSON format :contentReference[oaicite:3]{index=3}
        "categories": "general",
        "language": "en",
        "safesearch": "0",
    }

    r = requests.get(f"{base}/search", params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()

    results = []
    for item in data.get("results", [])[:k]:
        results.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "snippet": item.get("content"),
            "engine": item.get("engine"),
            "score": item.get("score"),
        })
    return results
