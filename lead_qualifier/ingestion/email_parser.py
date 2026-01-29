from __future__ import annotations

import base64
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Dict, Any, Optional, Tuple, List

from bs4 import BeautifulSoup

def _headers_map(payload: dict) -> Dict[str, str]:
    headers = payload.get("headers", []) or []
    out = {}
    for h in headers:
        name = (h.get("name") or "").lower().strip()
        value = (h.get("value") or "").strip()
        if name:
            out[name] = value
    return out

def _decode_b64(data: str) -> str:
    if not data:
        return ""
    missing_padding = (-len(data)) % 4
    data += "=" * missing_padding
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")

def _walk_parts(payload: dict) -> List[dict]:
    """
    Recursively flatten MIME parts.
    """
    parts = []
    stack = [payload]
    while stack:
        p = stack.pop()
        sub = p.get("parts")
        if sub:
            stack.extend(sub)
        else:
            parts.append(p)
    return parts

def _extract_best_body(payload: dict) -> Tuple[str, Optional[str]]:
    """
    Returns (body_text, body_html_opt).
    Prefer text/plain; fallback to html->text.
    """
    parts = _walk_parts(payload)
    text_chunks = []
    html_chunks = []

    for p in parts:
        mime = (p.get("mimeType") or "").lower()
        body = (p.get("body") or {})
        data = body.get("data")
        if not data:
            continue

        decoded = _decode_b64(data)
        if "text/plain" in mime:
            text_chunks.append(decoded)
        elif "text/html" in mime:
            html_chunks.append(decoded)

    if text_chunks:
        return "\n".join(text_chunks).strip(), None

    if html_chunks:
        html = "\n".join(html_chunks)
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text("\n")
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        return text.strip(), html

    # Sometimes body lives directly in payload.body.data
    body = payload.get("body", {}) or {}
    data = body.get("data")
    if data:
        decoded = _decode_b64(data).strip()
        return decoded, None

    return "", None

def parse_gmail_message(msg: dict) -> Dict[str, Any]:
    payload = msg.get("payload", {}) or {}
    headers = _headers_map(payload)

    from_raw = headers.get("from", "")
    from_name, from_email = _safe_parse_from(from_raw)

    subject = headers.get("subject", "") or ""
    snippet = msg.get("snippet", "") or ""
    internal_date = int(msg.get("internalDate", 0)) if msg.get("internalDate") else None
    received_at = None
    if internal_date:
        received_at = datetime.fromtimestamp(internal_date / 1000, tz=timezone.utc).isoformat()

    body_text, _body_html = _extract_best_body(payload)

    return {
        "gmail_message_id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "internal_date": internal_date,
        "from_name": from_name,
        "from_email": from_email,
        "subject": subject,
        "snippet": snippet,
        "body_text": body_text,
        "received_at": received_at,
    }

def _safe_parse_from(from_header: str) -> Tuple[Optional[str], Optional[str]]:
    name, email = parseaddr(from_header or "")
    name = name.strip() or None
    email = email.strip().lower() or None
    return name, email
