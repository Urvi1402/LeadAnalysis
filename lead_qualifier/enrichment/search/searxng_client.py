from __future__ import annotations

from typing import List, Optional
import requests

from .serper_client import SearchResult  # reuse the same dataclass


def searxng_search(
    query: str,
    *,
    base_url: str,
    num: int = 8,
    timeout_s: int = 20,
    categories: str = "general",
    language: str = "en",
) -> List[SearchResult]:
    """
    Calls local SearXNG and returns normalized results (same shape as Serper).
    """
    base_url = base_url.rstrip("/")
    url = f"{base_url}/search"

    params = {
        "q": query,
        "format": "json",
        "categories": categories,
        "language": language,
        "safesearch": 0,
    }

    r = requests.get(url, params=params, timeout=timeout_s)
    r.raise_for_status()

    data = r.json()
    results = data.get("results", []) or []

    out: List[SearchResult] = []
    for item in results[:num]:
        out.append(
            SearchResult(
                title=item.get("title", "") or "",
                link=item.get("url", "") or "",
                snippet=item.get("content", "") or "",
                source="searxng",
            )
        )

    return out
