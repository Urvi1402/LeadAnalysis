from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple


BITS_RELEVANT_KEYWORDS = {
    # Engineering / CS / Electronics
    "software", "technology", "internet", "cloud", "ai", "machine learning", "electronics",
    "semiconductor", "telecommunications", "robotics", "data", "analytics", "cybersecurity",
    # Finance / Management
    "financial", "bank", "fintech", "payments", "investment", "consulting",
    # Bio / Health (since you’re dual degree + common internships)
    "health", "biotech", "pharma", "medical",
}

# Very rough metro mapping (we’ll improve later with proper geo APIs)
METRO_HINTS = {
    "san francisco", "seattle", "new york", "london", "singapore", "bengaluru",
    "bangalore", "mumbai", "delhi", "hyderabad", "chennai", "pune",
    "cupertino", "los angeles", "toronto", "sydney", "melbourne",
}

def _now_year() -> int:
    return datetime.now().year

def _safe_lower(x: Optional[str]) -> str:
    return (x or "").lower()

def _parse_revenue_to_bucket(revenue_text: Optional[str]) -> Optional[float]:
    """
    Very simple parsing: returns revenue in billions USD if it sees a number + 'billion'.
    Otherwise None.
    Examples:
      'US$637.9 billion (2024)' -> 637.9
      'US$ 903 million (2020)' -> 0.903
    """
    if not revenue_text:
        return None
    t = revenue_text.lower().replace(",", "")
    m = re.search(r"(\d+(\.\d+)?)\s*(billion|million)", t)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(3)
    if unit == "million":
        return val / 1000.0
    return val  # billions

def score_age_1_to_5(founded_year: Optional[int]) -> int:
    if not founded_year:
        return 0  # missing -> 0 contribution
    age = _now_year() - founded_year
    if age < 1:
        return -1  # special flag for disqualify
    if age >= 30:
        return 5
    if age >= 15:
        return 4
    if age >= 7:
        return 3
    if age >= 2:
        return 2
    return 1  # age 1–<2

def score_employees_1_to_5(employees: Optional[int]) -> int:
    if not employees:
        return 0
    if employees >= 100000:
        return 5
    if employees >= 10000:
        return 4
    if employees >= 1000:
        return 3
    if employees >= 100:
        return 2
    return 1

def score_financial_stability_1_to_5(revenue_text: Optional[str]) -> int:
    """
    Proxy via revenue bucket. Missing -> 0
    """
    rev_b = _parse_revenue_to_bucket(revenue_text)
    if rev_b is None:
        return 0
    if rev_b >= 50:
        return 5
    if rev_b >= 5:
        return 4
    if rev_b >= 1:
        return 3
    if rev_b >= 0.1:
        return 2
    return 1

def score_founders_profile_1_to_5(_payload: Dict[str, Any]) -> int:
    """
    Placeholder for now.
    We don’t have founder bios yet from Wikipedia infobox reliably.
    Keep as 0 until we add founder extraction / LinkedIn/Wikidata.
    """
    return 0

def score_domain_relevance_1_to_5(industry: Optional[str], description: Optional[str]) -> int:
    text = f"{industry or ''} {description or ''}".lower()
    if not text.strip():
        return 0

    hits = sum(1 for kw in BITS_RELEVANT_KEYWORDS if kw in text)
    # map hits -> 1..5
    if hits >= 6:
        return 5
    if hits >= 4:
        return 4
    if hits >= 2:
        return 3
    if hits >= 1:
        return 2
    return 1

def score_project_quality_1_to_5(industry: Optional[str], description: Optional[str]) -> int:
    """
    Proxy for now: tech/platform/product companies tend to have richer internship projects.
    We'll later replace with job-post scraping/role analysis.
    """
    text = f"{industry or ''} {description or ''}".lower()
    if not text.strip():
        return 0

    high_impact = ["ai", "cloud", "platform", "infrastructure", "research", "data", "analytics"]
    routine = ["retail", "news", "publishing", "media"]

    score = 3
    if any(k in text for k in high_impact):
        score += 1
    if any(k in text for k in routine):
        score -= 1

    return max(1, min(5, score))

def score_geo_1_to_5(hq_location: Optional[str]) -> int:
    if not hq_location:
        return 0
    t = _safe_lower(hq_location)
    if any(m in t for m in METRO_HINTS):
        return 5
    # Has a location but not in our metro list -> neutral-ish
    return 3

def compute_weighted_score(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns:
      - disqualified (bool)
      - total_score_0_100
      - label
      - breakdown scores + weighted contributions
    """
    founded_year = profile.get("founded_year")
    employees = profile.get("employees")
    revenue = profile.get("revenue")
    industry = profile.get("industry")
    hq = profile.get("hq_location")
    desc = profile.get("description")
    conf = profile.get("confidence") or 0.0

    # Sub-scores (1..5, 0 if missing)
    age_score = score_age_1_to_5(founded_year)
    if age_score == -1:
        return {
            "disqualified": True,
            "total_score_0_100": 0,
            "label": "Disqualified",
            "reason": "Company age < 1 year (auto reject)",
        }

    emp_score = score_employees_1_to_5(employees)
    fin_score = score_financial_stability_1_to_5(revenue)
    founder_score = score_founders_profile_1_to_5(profile)

    domain_score = score_domain_relevance_1_to_5(industry, desc)
    project_score = score_project_quality_1_to_5(industry, desc)
    geo_score = score_geo_1_to_5(hq)

    # Weights (as fractions)
    W = {
        "age": 0.10,
        "employees": 0.10,
        "financial": 0.10,
        "founders": 0.05,
        "domain": 0.25,
        "project": 0.20,
        "geo": 0.20,
    }

    # Weighted average on 1..5 scale (missing=0 contributes 0)
    weighted_1_to_5 = (
        age_score * W["age"]
        + emp_score * W["employees"]
        + fin_score * W["financial"]
        + founder_score * W["founders"]
        + domain_score * W["domain"]
        + project_score * W["project"]
        + geo_score * W["geo"]
    )

    total_0_100 = round((weighted_1_to_5 / 5.0) * 100, 2)

    # Label thresholds
    if total_0_100 >= 80:
        label = "Strong"
    elif total_0_100 >= 60:
        label = "Moderate"
    elif total_0_100 >= 40:
        label = "Weak"
    else:
        label = "Disqualified"

    # Confidence flag
    low_conf = conf < 0.6

    return {
        "disqualified": label == "Disqualified",
        "total_score_0_100": total_0_100,
        "label": label,
        "low_confidence": low_conf,
        "profile_confidence": conf,
        "subscores_1_to_5": {
            "age": age_score,
            "employees": emp_score,
            "financial": fin_score,
            "founders": founder_score,
            "domain": domain_score,
            "project": project_score,
            "geo": geo_score,
        },
        "weights": W,
        "weighted_1_to_5": round(weighted_1_to_5, 3),
    }
