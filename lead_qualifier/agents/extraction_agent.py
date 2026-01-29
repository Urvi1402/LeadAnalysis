from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from lead_qualifier.llm.client import LLMClient, get_llm_config
from lead_qualifier.utils.normalize import normalize_company_name, clean_display_name


JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


SYSTEM_PROMPT = """You are an information extraction engine.
Extract structured fields from an email about internship/company leads.

Rules:
- Output MUST be valid JSON only. No markdown. No extra commentary.
- If a field is unknown, set it to null.
- Company name must be the actual organization, not a newsletter brand, bank alert, payment system, or generic term.
- If the email is not a recruiting/lead email, set is_lead=false and company_name=null.
"""

USER_TEMPLATE = """Extract the lead info from this email.

Return JSON with exactly these keys:
{{
  "is_lead": boolean,
  "company_name": string|null,
  "company_domain": string|null,
  "role_title": string|null,
  "location": string|null,
  "source_links": [string],
  "confidence": number
}}

Email:
FROM: {from_email}
SUBJECT: {subject}

BODY:
{body}
"""


@dataclass
class ExtractionResult:
    is_lead: bool
    company_name: Optional[str]
    normalized_name: Optional[str]
    company_domain: Optional[str]
    role_title: Optional[str]
    location: Optional[str]
    source_links: list[str]
    confidence: float
    raw_json: Dict[str, Any]


def _safe_json_parse(text: str) -> Optional[Dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return None

    # Sometimes models wrap extra text; pull the first JSON object
    m = JSON_BLOCK_RE.search(text)
    if not m:
        return None

    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def extract_with_llm(subject: str, body_text: str, from_email: Optional[str]) -> ExtractionResult:
    cfg = get_llm_config()
    llm = LLMClient(cfg)

    user = USER_TEMPLATE.format(
        from_email=from_email or "",
        subject=(subject or "")[:300],
        body=(body_text or "")[:6000],
    )

    out = llm.chat_json(system=SYSTEM_PROMPT, user=user, temperature=0.0, max_tokens=700)
    data = _safe_json_parse(out) or {}

    is_lead = bool(data.get("is_lead", False))

    company = data.get("company_name")
    company = clean_display_name(company) if isinstance(company, str) else None
    norm = normalize_company_name(company) if company else None

    # confidence clamp
    conf = data.get("confidence", 0.0)
    try:
        conf = float(conf)
    except Exception:
        conf = 0.0
    conf = max(0.0, min(1.0, conf))

    links = data.get("source_links") or []
    if not isinstance(links, list):
        links = []
    links = [str(x) for x in links if x]

    return ExtractionResult(
        is_lead=is_lead,
        company_name=company,
        normalized_name=norm,
        company_domain=data.get("company_domain"),
        role_title=data.get("role_title"),
        location=data.get("location"),
        source_links=links,
        confidence=conf,
        raw_json=data if isinstance(data, dict) else {},
    )
