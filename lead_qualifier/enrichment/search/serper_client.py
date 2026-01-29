from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


@dataclass
class SearchResult:
    title: str
    link: str
    snippet: str
    source: str = "serper"


class SerperError(RuntimeError):
    pass


def serper_search(
    query: str,
    *,
    api_key: Optional[str] = None,
    endpoint: str = "https://google.serper.dev/search",
    num: int = 5,
    country: str = "in",
    lang: str = "en",
    timeout: int = 30,
    max_retries: int = 3,
) -> List[SearchResult]:
    """
    Calls Serper (Google Search API) and returns normalized results.

    Note: This is only "URL discovery". You must still robots-check before fetching pages.
    """
    api_key = api_key or os.environ.get("SERPER_API_KEY")
    if not api_key:
        raise SerperError("Missing SERPER_API_KEY (set it in .env or environment).")

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    payload: Dict[str, Any] = {
        "q": query,
        "num": num,
        "gl": country,  # geographic location
        "hl": lang,     # language
    }

    last_err: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
            if r.status_code == 429:
                # rate limit: backoff
                time.sleep(1.5 * attempt)
                continue
            if r.status_code >= 400:
                raise SerperError(f"Serper HTTP {r.status_code}: {r.text[:300]}")

            data = r.json()
            out: List[SearchResult] = []

            # Serper typically returns `organic` results
            for item in data.get("organic", [])[:num]:
                out.append(
                    SearchResult(
                        title=item.get("title", "") or "",
                        link=item.get("link", "") or "",
                        snippet=item.get("snippet", "") or "",
                    )
                )

            return out

        except Exception as e:
            last_err = e
            time.sleep(0.8 * attempt)

    raise SerperError(f"Serper search failed after retries. Last error: {last_err}")
