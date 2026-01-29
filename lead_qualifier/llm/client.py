from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import OpenAI


@dataclass
class LLMConfig:
    base_url: str
    model: str
    api_key: str


def get_llm_config() -> LLMConfig:
    base_url = os.environ.get("LLM_BASE_URL", "").strip()
    model = os.environ.get("LLM_MODEL", "").strip()
    api_key = os.environ.get("LLM_API_KEY", "local").strip()  # vLLM often ignores it

    if not base_url or not model:
        raise ValueError("Missing LLM_BASE_URL or LLM_MODEL in environment/.env")

    return LLMConfig(base_url=base_url, model=model, api_key=api_key)


class LLMClient:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg
        self.client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)

    def chat_json(
        self,
        system: str,
        user: str,
        temperature: float = 0.0,
        max_tokens: int = 700,
    ) -> str:
        """
        Returns raw text. We instruct the model to output JSON only.
        Parsing + validation happens in the agent.
        """
        resp = self.client.chat.completions.create(
            model=self.cfg.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()
