from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import tldextract

from lead_qualifier.utils.normalize import normalize_company_name, clean_display_name


# Offline snapshot; no downloading PSL list at runtime.
_TLDX = tldextract.TLDExtract(suffix_list_urls=None)

COMMON_EMAIL_DOMAINS = {
    "gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com",
    "proton.me", "protonmail.com", "aol.com", "zoho.com"
}

# Domains we should NOT treat as companies even if they appear in links/sender domains.
# (ATS platforms, email sending platforms, recruitment tooling, etc.)
NON_COMPANY_DOMAINS = {
    "greenhouse.io", "lever.co", "workday.com", "myworkday.com",
    "successfactors.com", "smartrecruiters.com", "talent.com",
    "sendgrid.net", "mailchimp.com", "sparkpostmail.com",
    "campaign-archive.com", "hubspotemail.net", "hs-sites.com",
    "amazonaws.com", "cloudfront.net", "lnkd.in", "bit.ly", "t.co",
}

# Common non-company “organizations” that appear in email text/signatures.
STOP_ORGS = {
    "bits pilani", "bits", "placement unit", "career services", "internship cell",
    "human resources", "hr team", "hr", "talent acquisition", "recruitment", "recruiter",
    "team", "alerts", "newsletter", "digest", "no reply", "noreply",
    "upi", "otp", "invoice", "statement", "bank",
}

PATTERNS = [
    # High precision
    re.compile(r"\bCompany\s*:\s*(.+)", re.IGNORECASE),
    re.compile(r"\bOrganization\s*:\s*(.+)", re.IGNORECASE),
    re.compile(r"\bEmployer\s*:\s*(.+)", re.IGNORECASE),
    # Medium precision
    re.compile(r"\bInternship\s+(?:at|with)\s+([A-Z][A-Za-z0-9&.\- ]{2,})", re.IGNORECASE),
    re.compile(r"\bOpportunity\s+(?:at|with)\s+([A-Z][A-Za-z0-9&.\- ]{2,})", re.IGNORECASE),
]

URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)


@dataclass
class Candidate:
    name: str
    score: int
    source: str


def extract_company_candidates(subject: str, body_text: str, from_email: Optional[str]) -> List[Candidate]:
    cands: List[Candidate] = []

    # 1) Subject hints
    subj = subject or ""
    subj_hits = _extract_from_subject(subj)
    for h in subj_hits:
        cands.append(Candidate(h, 6, "subject"))

    # 2) Regex patterns in body
    for idx, pat in enumerate(PATTERNS):
        for m in pat.finditer(body_text or ""):
            val = (m.group(1) or "").strip()
            val = _trim_noise(val)
            if not val:
                continue

            # Robust scoring by pattern “tier”
            if idx == 0:      # Company:
                score = 9
            elif idx in (1, 2):  # Organization:/Employer:
                score = 8
            else:             # Internship at / Opportunity at
                score = 6

            cands.append(Candidate(val, score, f"body_pattern:{idx}"))

    # 3) Domains (from sender + urls)
    doms = set()

    if from_email and "@" in from_email:
        doms.add(from_email.split("@", 1)[1].lower().strip())

    for url in URL_RE.findall(body_text or ""):
        try:
            dom = urlparse(url).netloc.lower().split(":")[0]
            if dom.startswith("www."):
                dom = dom[4:]
            if dom:
                doms.add(dom)
        except Exception:
            pass

    for dom in doms:
        if not dom or dom in COMMON_EMAIL_DOMAINS:
            continue

        # Avoid common non-company domains (google docs etc.)
        if any(dom.endswith(x) for x in ["google.com", "docs.google.com", "forms.gle", "drive.google.com"]):
            continue

        # Avoid ATS / email tooling / recruitment platforms
        if any(dom.endswith(x) for x in NON_COMPANY_DOMAINS):
            continue

        guessed = _domain_to_company_guess(dom)
        if guessed:
            cands.append(Candidate(guessed, 4, f"domain:{dom}"))

    # 4) Filter + dedupe (keep max score per normalized key)
    best_by_norm: dict[str, Candidate] = {}

    for c in cands:
        disp = clean_display_name(c.name)
        norm = normalize_company_name(disp)

        if not norm:
            continue
        if norm in STOP_ORGS:
            continue

        prev = best_by_norm.get(norm)
        if prev is None or c.score > prev.score:
            best_by_norm[norm] = Candidate(disp, c.score, c.source)

    return sorted(best_by_norm.values(), key=lambda x: x.score, reverse=True)


def pick_best_company(subject: str, body_text: str, from_email: Optional[str]) -> Tuple[Optional[str], Optional[float], str]:
    """
    MVP: pick top heuristic candidate.
    Returns (company_name, confidence, source).
    """
    cands = extract_company_candidates(subject, body_text, from_email)
    if not cands:
        return None, None, "none"

    top = cands[0]
    # Heuristic confidence: map score to ~0.4..0.95
    conf = min(0.95, max(0.4, top.score / 10.0))
    return top.name, conf, top.source


def _extract_from_subject(subject: str) -> List[str]:
    out: List[str] = []
    s = (subject or "").strip()

    # Example: "Internship Opportunity at Razorpay"
    m = re.search(r"\b(?:at|with)\s+([A-Z][A-Za-z0-9&.\- ]{2,})\b", s)
    if m:
        out.append(m.group(1).strip())

    # Example: "Razorpay | Internship Role"
    if "|" in s:
        left = s.split("|", 1)[0].strip()
        if 3 <= len(left) <= 60:
            out.append(left)

    return [_trim_noise(x) for x in out if _trim_noise(x)]


def _trim_noise(s: str) -> str:
    if not s:
        return ""

    # Stop at common separators (keep first segment)
    s = re.split(r"[\n\r\t]| - | — | – | \| ", s)[0].strip()

    # Strip trailing punctuation
    s = s.strip(" .,:;!-")

    # Avoid overly long blobs
    if len(s) > 80:
        s = s[:80].strip()

    return s


def _domain_to_company_guess(domain: str) -> Optional[str]:
    """
    Guess company name from a domain using PSL parsing.

    Examples:
      axis.bank.in  -> Axis     (subdomain fallback if domain is generic)
      mail.adobe.com -> Adobe
      email.openai.com -> Openai
    """
    d = (domain or "").lower().strip()
    if not d:
        return None
    if d.startswith("www."):
        d = d[4:]

    ext = _TLDX(d)
    # ext.subdomain, ext.domain, ext.suffix

    # Generic domain labels that are not company identifiers
    generic_domains = {"bank", "co", "com", "org", "net", "edu", "gov", "nic", "mail", "email", "alerts"}

    base = (ext.domain or "").strip()

    # If base becomes something generic (like "bank"), use last subdomain label ("axis")
    if base in generic_domains and ext.subdomain:
        base = ext.subdomain.split(".")[-1]

    base = re.sub(r"[^a-z0-9\-]+", "", base)
    base = base.replace("-", " ").strip()

    if not base or len(base) < 3:
        return None

    return " ".join(w.capitalize() for w in base.split())
