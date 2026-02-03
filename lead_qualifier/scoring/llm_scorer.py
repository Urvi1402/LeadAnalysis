from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from lead_qualifier.config import SETTINGS
from lead_qualifier.llm.openai_compat import ChatMessage, chat_completions, LLMError


def _prompt(company_name: str, profile: Dict[str, Any]) -> Tuple[str, str]:
    prefs = SETTINGS.domain_preferences
    prefs_str = ", ".join(prefs) if prefs else "(not provided)"

    system = (
        "You are a strict lead scoring agent for company evaluation.\n"
        "Return ONLY valid JSON. No markdown. No extra text.\n"
        "Use the rubric + weights exactly.\n"
        "Be conservative when data is missing.\n"
    )

    user = {
        "task": "Score this company and generate a structured evaluation for a student placement lead scoring system.",
        "company_name": company_name,
        "domain_preferences": prefs_str,
        "weights_percent": {
            "age": 10,
            "employees": 10,
            "financial": 10,
            "founders": 5,
            "domain": 25,
            "project": 20,
            "geo": 20,
        },
        "required_output_json_schema": {
            "subscores_1_to_5": {
                "age": "int 1-5",
                "employees": "int 1-5",
                "financial": "int 1-5",
                "founders": "int 1-5",
                "domain": "int 1-5",
                "project": "int 1-5",
                "geo": "int 1-5",
            },
            "total_score_0_100": "int 0-100",
            "label": "one of: Strong, Medium, Weak, Disqualified",
            "confidence": "float 0-1",
            "missing_fields": "list[str]",
            "red_flags": "list[str]",
            "rationale_bullets": "list[str] (max 8 bullets)",
            "recommended_next_steps": "list[str] (max 6 bullets)",
        },
        "rules": [
            "If data is insufficient for a dimension, score 2 (not 1) and add it to missing_fields.",
            "Disqualified only if there is a clear hard red flag (e.g., scam indicators, illegal activity, explicit mismatch).",
            "Compute total_score_0_100 using the provided weights (weighted average of 1-5 mapped to 0-100).",
            "Mapping from subscore to 0-100: 1->20, 2->40, 3->60, 4->80, 5->100.",
            "Confidence should reflect completeness + reliability of the profile (0.3 low, 0.7 decent, 0.9 very strong).",
        ],
        "company_profile_input": profile,
    }

    return system, json.dumps(user, ensure_ascii=False)


def score_with_llm(company_name: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    if not SETTINGS.use_llm_scoring:
        raise RuntimeError("LLM scoring is disabled (USE_LLM_SCORING=0).")

    system, user = _prompt(company_name, profile)

    content = chat_completions(
        base_url=SETTINGS.llm_scoring_base_url,
        api_key=SETTINGS.llm_scoring_api_key,
        model=SETTINGS.llm_scoring_model,
        messages=[
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=user),
        ],
        temperature=SETTINGS.llm_scoring_temperature,
        max_tokens=SETTINGS.llm_scoring_max_tokens,
        timeout_s=90,
        max_retries=2,
    )

    # Parse JSON strictly; if the model returns junk, fail clearly
    try:
        data = json.loads(content)
    except Exception as e:
        raise LLMError(f"LLM did not return valid JSON. Error: {e}. Raw: {content[:400]}")

    return data
