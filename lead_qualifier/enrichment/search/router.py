from typing import List
from lead_qualifier.config import SETTINGS

from .serper_client import serper_search, SearchResult
from .searxng_client import searxng_search


def web_search(q: str, num: int = 8) -> List[SearchResult]:
    p = SETTINGS.search_provider

    if p == "searxng":
        return searxng_search(
            q,
            num=num,
            base_url=SETTINGS.searxng_url,
            timeout_s=SETTINGS.searxng_timeout_s,
        )

    if p == "serper":
        return serper_search(
            q,
            num=num,
            endpoint=SETTINGS.serper_endpoint,
            api_key=SETTINGS.serper_api_key,
        )

    raise ValueError(f"Unknown SEARCH_PROVIDER={p!r}. Use searxng or serper.")
