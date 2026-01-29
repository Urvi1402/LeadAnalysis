from __future__ import annotations

import json
import os

from lead_qualifier.config import SETTINGS
from lead_qualifier.storage.db import get_conn, init_db, is_profile_fresh
from lead_qualifier.enrichment.wikipedia_enricher import enrich_from_wikipedia


# Import your picker from scripts.enrich_once for now (quick MVP)
# Later we’ll move picker into a shared module.
from scripts.enrich_once import pick_best_wikipedia  # type: ignore


def upsert_company_profile(conn, company_id: int, payload: dict) -> None:
    conn.execute(
        """
        INSERT INTO company_profiles (
            company_id, source, source_url, founded_year, employees,
            hq_location, industry, revenue, rating, confidence, raw_json, fetched_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(company_id, source) DO UPDATE SET
            source_url=excluded.source_url,
            founded_year=excluded.founded_year,
            employees=excluded.employees,
            hq_location=excluded.hq_location,
            industry=excluded.industry,
            revenue=excluded.revenue,
            rating=excluded.rating,
            confidence=excluded.confidence,
            raw_json=excluded.raw_json,
            fetched_at=datetime('now')
        """,
        (
            company_id,
            payload.get("source"),
            payload.get("source_url"),
            payload.get("founded_year"),
            payload.get("employees"),
            payload.get("hq_location"),
            payload.get("industry"),
            payload.get("revenue"),
            payload.get("rating"),
            payload.get("confidence"),
            json.dumps(payload, ensure_ascii=False),
        ),
    )
    conn.commit()


def main():
    conn = get_conn(SETTINGS.db_path)
    init_db(conn)

    ttl_days = int(os.environ.get("CACHE_TTL_DAYS", "7"))

    companies = conn.execute(
        "SELECT id, name FROM companies ORDER BY last_seen_at DESC"
    ).fetchall()

    print(f"Companies in DB = {len(companies)} | Cache TTL = {ttl_days} days")

    enriched = 0
    skipped_cache = 0
    skipped_no_source = 0

    for row in companies:
        company_id = row["id"]
        name = row["name"]

        if is_profile_fresh(conn, company_id, ttl_days=ttl_days):
            skipped_cache += 1
            continue

        wiki_url = pick_best_wikipedia(name)
        if not wiki_url:
            skipped_no_source += 1
            continue

        payload = enrich_from_wikipedia(wiki_url)
        upsert_company_profile(conn, company_id, payload)
        enriched += 1

        print(f"\n{name}")
        print("  url:", payload.get("source_url"))
        print("  founded_year:", payload.get("founded_year"))
        print("  employees:", payload.get("employees"))
        print("  hq_location:", payload.get("hq_location"))
        print("  industry:", payload.get("industry"))
        print("  revenue:", payload.get("revenue"))
        print("  confidence:", payload.get("confidence"))

    print("\nSummary")
    print("  enriched:", enriched)
    print("  skipped_cache:", skipped_cache)
    print("  skipped_no_source:", skipped_no_source)


if __name__ == "__main__":
    main()
