# lead_qualifier/enrichment/search/client_factory.py
from __future__ import annotations

import os
from typing import Any

from .searxng_client import SearxngClient

# If serper_client exists in your repo:
from .serper_client import SerperClient  # type: ignore


def get_search_client() -> Any:
    provider = (os.getenv("SEARCH_PROVIDER") or "serper").strip().lower()

    if provider == "searxng":
        return SearxngClient()
    if provider == "serper":
        return SerperClient()

    raise ValueError(f"Unknown SEARCH_PROVIDER={provider!r}")
