from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup


UA = "LeadQualifierBot/1.0 (educational project)"

YEAR_RE = re.compile(r"(18|19|20)\d{2}")
INT_RE = re.compile(r"(\d[\d,]*)")


def _title_from_wiki_url(url: str) -> str:
    # https://en.wikipedia.org/wiki/Apple_Inc. -> Apple_Inc.
    part = url.split("/wiki/", 1)[1]
    return unquote(part).strip()


def _clean_text(s: str) -> str:
    s = re.sub(r"\[\d+\]", "", s)          # remove citations like [1]
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _first_year(text: str) -> Optional[int]:
    m = YEAR_RE.search(text or "")
    if not m:
        return None
    try:
        return int(m.group(0))
    except Exception:
        return None


def _first_int(text: str) -> Optional[int]:
    m = INT_RE.search(text or "")
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except Exception:
        return None


def _parse_infobox(html: str) -> Dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    infobox = soup.find("table", class_=lambda c: c and "infobox" in c)
    if not infobox:
        return {}

    data: Dict[str, str] = {}
    for tr in infobox.find_all("tr", recursive=True):
        th = tr.find("th")
        td = tr.find("td")
        if not th or not td:
            continue
        key = _clean_text(th.get_text(" ", strip=True)).lower()
        val = _clean_text(td.get_text(" ", strip=True))
        if key and val:
            data[key] = val

    return data


def fetch_wikipedia_parsed_html(wiki_url: str) -> Dict[str, Any]:
    """
    Uses MediaWiki 'action=parse' to get rendered HTML for the page (with redirects).
    Returns: { "title": canonical_title, "html": page_html, "final_url": canonical_url }
    """
    title = _title_from_wiki_url(wiki_url)

    api = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "format": "json",
        "redirects": "1",
    }

    r = requests.get(api, params=params, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    j = r.json()

    if "error" in j:
        raise RuntimeError(f"Wikipedia API error: {j['error']}")

    parse = j.get("parse") or {}
    canon_title = parse.get("title") or title
    html = (parse.get("text") or {}).get("*") or ""

    final_url = f"https://en.wikipedia.org/wiki/{canon_title.replace(' ', '_')}"
    return {"title": canon_title, "html": html, "final_url": final_url}


def fetch_wikipedia_summary(title: str) -> Optional[str]:
    """
    REST summary API is handy for a short description for domain mapping.
    """
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '%20')}"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    if r.status_code != 200:
        return None
    j = r.json()
    return (j.get("extract") or "").strip() or None


def enrich_from_wikipedia(wiki_url: str) -> Dict[str, Any]:
    """
    Extracts: founded_year, employees, hq_location, industry, revenue, description.
    rating is not expected from Wikipedia.
    Returns a payload with a computed confidence.
    """
    parsed = fetch_wikipedia_parsed_html(wiki_url)
    title = parsed["title"]
    html = parsed["html"]
    final_url = parsed["final_url"]

    infobox = _parse_infobox(html)

    # Common infobox keys (vary by page)
    founded_raw = infobox.get("founded") or infobox.get("founded on") or ""
    hq_raw = infobox.get("headquarters") or ""
    industry_raw = infobox.get("industry") or infobox.get("type") or ""
    employees_raw = (
        infobox.get("number of employees")
        or infobox.get("employees")
        or infobox.get("num. employees")
        or ""
    )
    revenue_raw = infobox.get("revenue") or ""

    founded_year = _first_year(founded_raw)
    employees = _first_int(employees_raw)

    # Light cleanup for HQ
    hq_location = _clean_text(hq_raw) if hq_raw else None
    industry = _clean_text(industry_raw) if industry_raw else None
    revenue = _clean_text(revenue_raw) if revenue_raw else None

    description = fetch_wikipedia_summary(title)

    # Confidence heuristic: how many “core fields” we found
    found = 0
    for x in [founded_year, hq_location, industry, employees, revenue]:
        if x not in (None, "", 0):
            found += 1
    confidence = round(min(0.95, 0.35 + 0.12 * found), 2)

    return {
        "source": "wikipedia",
        "source_url": final_url,
        "title": title,
        "founded_year": founded_year,
        "employees": employees,
        "hq_location": hq_location,
        "industry": industry,
        "revenue": revenue,
        "rating": None,
        "description": description,
        "confidence": confidence,
    }
