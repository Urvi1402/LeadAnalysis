from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import re

# Strong signals that an email is about hiring / internship / role
PRIMARY_KEYWORDS = {
    "internship", "intern", "hiring", "we are hiring",
    "job opening", "opening", "vacancy", "role", "position",
    "interview", "shortlisted", "shortlist", "selection",
    "recruitment", "recruiter", "talent acquisition",
    "practice school", "ps", "campus hiring", "placement"
}

# Weak signals: appear in marketing too; allow only if job-evidence exists
SECONDARY_KEYWORDS = {"apply", "application", "opportunity", "career", "careers"}

# Extra job-evidence terms (must appear if we only have secondary keywords)
JOB_EVIDENCE = {
    "resume", "cv", "curriculum vitae",
    "job description", "jd", "responsibilities", "requirements",
    "stipend", "ctc", "compensation", "salary",
    "joining", "start date", "duration", "eligibility",
    "assessment", "coding test", "oa", "interview"
}

# Noise subject patterns
EXCLUDE_SUBJECT_PATTERNS = [
    r"\bdebited\b", r"\bcredited\b", r"\botp\b", r"\bstatement\b",
    r"\binvoice\b", r"\border\b", r"\bdelivered\b", r"\bshipment\b",
    r"\bnewsletter\b", r"\bdigest\b", r"\bconfirmation\b",
    r"\breset password\b", r"\bverification code\b", r"\btransaction\b",
    r"\boffer\b", r"\bdiscount\b", r"\bsale\b"
]

# Skip these sources for now (we'll parse them separately later as "aggregators")
AGGREGATOR_DOMAINS = {
    "naukri.com", "linkedin.com", "indeed.com", "internshala.com", "glassdoor.com",
    "shine.com", "foundit.in", "monster.com", "lnkd.in"
}

# If these appear, it’s almost certainly a newsletter/marketing mail
NEWSLETTER_SIGNALS = {
    "unsubscribe", "manage preferences", "view in browser",
    "promotional", "you received this email because"
}

@dataclass(frozen=True)
class EmailDecision:
    should_process: bool
    reason: str

def _domain(from_email: Optional[str]) -> Optional[str]:
    if not from_email or "@" not in from_email:
        return None
    return from_email.split("@", 1)[1].lower().strip()

def is_lead_email(subject: str, body_text: str, from_email: Optional[str]) -> EmailDecision:
    subj = (subject or "").lower()
    body = (body_text or "").lower()
    dom = _domain(from_email)

    # 1) Exclude obvious noise via subject patterns
    for pat in EXCLUDE_SUBJECT_PATTERNS:
        if re.search(pat, subj):
            return EmailDecision(False, f"excluded_subject:{pat}")

    # 2) Exclude aggregators (we'll handle later)
    if dom and any(dom.endswith(d) for d in AGGREGATOR_DOMAINS):
        return EmailDecision(False, "aggregator_domain")

    # 3) Newsletter signals -> reject unless we see PRIMARY keywords
    if any(sig in body for sig in NEWSLETTER_SIGNALS):
        # if primary exists, we still allow
        if not any(pk in (subj + "\n" + body) for pk in PRIMARY_KEYWORDS):
            return EmailDecision(False, "newsletter_signal")

    hay = subj + "\n" + body

    # 4) If ANY primary keyword is present => process
    for pk in PRIMARY_KEYWORDS:
        if pk in hay:
            return EmailDecision(True, f"primary:{pk}")

    # 5) If only secondary keywords exist, require job evidence too
    secondary_hit = any(sk in hay for sk in SECONDARY_KEYWORDS)
    evidence_hit = any(ev in hay for ev in JOB_EVIDENCE)

    if secondary_hit and evidence_hit:
        return EmailDecision(True, "secondary+evidence")

    return EmailDecision(False, "no_lead_signals")
