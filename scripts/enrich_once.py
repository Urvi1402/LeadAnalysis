from __future__ import annotations

from urllib.parse import quote, unquote
import requests

from lead_qualifier.config import SETTINGS
from lead_qualifier.storage.db import get_conn, init_db
from lead_qualifier.enrichment.search.router import web_search

# --- Wikipedia selection helpers (validated) ---

BAD_WIKI_PREFIXES = (
    "https://en.wikipedia.org/wiki/Wikipedia:",
    "https://en.wikipedia.org/wiki/Help:",
    "https://en.wikipedia.org/wiki/Special:",
    "https://en.wikipedia.org/wiki/Category:",
    "https://en.wikipedia.org/wiki/Talk:",
    "https://en.wikipedia.org/wiki/Template:",
    "https://en.wikipedia.org/wiki/Portal:",
    "https://en.wikipedia.org/wiki/File:",
)

NEGATIVE_TERMS = (
    " v. ", " vs ", "lawsuit", "court", "appeal", "judge", "legal",
    "case", "litigation", "complaint", "plaintiff", "defendant",
)

COMPANY_HINTS = (
    "company", "corporation", "inc", "ltd", "limited", "firm",
    "headquartered", "founded", "employees", "revenue", "subsidiary",
    "technology", "software", "platform",
)

UA = "LeadQualifierBot/1.0 (educational project)"

def wiki_title_from_url(url: str) -> str:
    part = url.split("/wiki/", 1)[1]
    return unquote(part).replace("_", " ")

def fetch_wiki_summary(title: str) -> dict | None:
    api = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
    r = requests.get(api, headers={"User-Agent": UA}, timeout=20)
    if r.status_code != 200:
        return None
    return r.json()

def is_good_company_page(company_name: str, url: str) -> tuple[bool, int, str]:
    if not url.startswith("https://en.wikipedia.org/wiki/"):
        return False, -999, "not_wiki_article"
    if url.startswith(BAD_WIKI_PREFIXES):
        return False, -999, "wiki_meta_page"

    title = wiki_title_from_url(url)
    summary = fetch_wiki_summary(title)
    if not summary:
        return False, -50, "no_summary"

    if summary.get("type") == "disambiguation":
        return False, -50, "disambiguation"

    extract = (summary.get("extract") or "").lower()
    t = (summary.get("title") or "").lower()
    cname = (company_name or "").lower()

    # hard reject lawsuit/case pages
    if any(term in t for term in NEGATIVE_TERMS) or any(term in extract for term in NEGATIVE_TERMS):
        return False, -100, "legal_case_page"

    score = 0
    if cname and cname in t:
        score += 8
    if "(company)" in t:
        score += 8
    if cname and cname.replace(" ", "_") in url.lower():
        score += 4

    for h in COMPANY_HINTS:
        if h in extract:
            score += 2

    # require some company-like signal
    if score < 8:
        return False, score, "low_company_signal"

    return True, score, "ok"

def pick_best_wikipedia(company_name: str) -> str | None:
    # 1) direct canonical guesses first
    direct_urls = [
        f"https://en.wikipedia.org/wiki/{company_name.replace(' ', '_')}",
        f"https://en.wikipedia.org/wiki/{company_name.replace(' ', '_')}_Inc.",
        f"https://en.wikipedia.org/wiki/{company_name.replace(' ', '_')}_Technologies",
        f"https://en.wikipedia.org/wiki/{company_name.replace(' ', '_')}_Ltd",
        f"https://en.wikipedia.org/wiki/{company_name.replace(' ', '_')}_(company)",
    ]

    best_url = None
    best_score = -10**9

    for u in direct_urls:
        ok, sc, _ = is_good_company_page(company_name, u)
        if ok and sc > best_score:
            best_url, best_score = u, sc

    if best_url:
        return best_url

    # 2) search and validate
    queries = [
        f'"{company_name}" company site:en.wikipedia.org',
        f'"{company_name}" founded headquartered site:en.wikipedia.org',
        f'"{company_name}" site:en.wikipedia.org',
    ]

    candidates = []
    for q in queries:
        candidates.extend(web_search(q, num=8))

    for c in candidates:
        u = c.link
        ok, sc, _ = is_good_company_page(company_name, u)
        if ok and sc > best_score:
            best_url, best_score = u, sc

    return best_url

# --- Main script ---

def main():
    conn = get_conn(SETTINGS.db_path)
    init_db(conn)

    companies = conn.execute("SELECT id, name FROM companies ORDER BY last_seen_at DESC").fetchall()
    print(f"Companies in DB = {len(companies)}")

    for row in companies:
        name = row["name"]
        wiki_url = pick_best_wikipedia(name)

        print(f"\n{name}")
        if wiki_url:
            print("  best_wiki:", wiki_url)
        else:
            print("  best_wiki: NOT FOUND (will fallback to other sources later)")

if __name__ == "__main__":
    main()
