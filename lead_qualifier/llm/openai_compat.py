from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


@dataclass
class ChatMessage:
    role: str
    content: str


class LLMError(RuntimeError):
    pass


def chat_completions(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: List[ChatMessage],
    temperature: float = 0.0,
    max_tokens: int = 800,
    timeout_s: int = 60,
    max_retries: int = 2,
) -> str:
    if not base_url:
        raise LLMError("Missing base_url for LLM.")
    if not model:
        raise LLMError("Missing model for LLM.")

    url = base_url.rstrip("/") + "/chat/completions"
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_err: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
            if r.status_code == 429:
                time.sleep(1.5 * attempt)
                continue
            if r.status_code >= 400:
                raise LLMError(f"LLM HTTP {r.status_code}: {r.text[:400]}")

            data = r.json()
            return data["choices"][0]["message"]["content"]

        except Exception as e:
            last_err = e
            time.sleep(0.8 * attempt)

    raise LLMError(f"LLM call failed after retries. Last error: {last_err}")
