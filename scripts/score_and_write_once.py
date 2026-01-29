from __future__ import annotations

import json
from pathlib import Path

from lead_qualifier.config import SETTINGS
from lead_qualifier.storage.db import get_conn, init_db
from lead_qualifier.scoring.rules import compute_weighted_score


def safe_filename(name: str) -> str:
    # very small sanitizer for file naming
    keep = []
    for ch in name:
        if ch.isalnum() or ch in (" ", "-", "_"):
            keep.append(ch)
    out = "".join(keep).strip().replace(" ", "_")
    return out or "company"


def main():
    SETTINGS.responses_dir.mkdir(parents=True, exist_ok=True)

    conn = get_conn(SETTINGS.db_path)
    init_db(conn)

    rows = conn.execute(
        """
        SELECT c.id AS company_id, c.name AS company_name, p.raw_json
        FROM companies c
        LEFT JOIN company_profiles p
          ON p.company_id = c.id AND p.source = 'wikipedia'
        ORDER BY c.last_seen_at DESC
        """
    ).fetchall()

    scored = 0
    skipped_no_profile = 0

    for r in rows:
        name = r["company_name"]
        raw = r["raw_json"]

        if not raw:
            skipped_no_profile += 1
            continue

        profile = json.loads(raw)
        result = compute_weighted_score(profile)

        # write response file
        out_path = SETTINGS.responses_dir / f"{safe_filename(name)}.txt"
        with out_path.open("w", encoding="utf-8") as f:
            f.write(f"Company: {name}\n")
            f.write(f"Source: {profile.get('source')} | URL: {profile.get('source_url')}\n\n")

            f.write("Extracted Metrics\n")
            f.write(f"- Founded year: {profile.get('founded_year')}\n")
            f.write(f"- Employees: {profile.get('employees')}\n")
            f.write(f"- HQ: {profile.get('hq_location')}\n")
            f.write(f"- Industry: {profile.get('industry')}\n")
            f.write(f"- Revenue: {profile.get('revenue')}\n")
            f.write(f"- Profile confidence: {profile.get('confidence')}\n\n")

            f.write("Scoring Breakdown (1–5)\n")
            subs = result.get("subscores_1_to_5", {})
            f.write(f"- Age/Longevity (10%): {subs.get('age')}\n")
            f.write(f"- Employees Strength (10%): {subs.get('employees')}\n")
            f.write(f"- Financial Stability (10%): {subs.get('financial')}\n")
            f.write(f"- Founders Profile (5%): {subs.get('founders')}\n")
            f.write(f"- Domain Relevance (25%): {subs.get('domain')}\n")
            f.write(f"- Project Quality & Fit (20%): {subs.get('project')}\n")
            f.write(f"- Geographic Advantage (20%): {subs.get('geo')}\n\n")

            if result.get("label") == "Disqualified" and "reason" in result:
                f.write(f"Decision: Disqualified\nReason: {result['reason']}\n")
            else:
                f.write(f"Weighted score (0–100): {result.get('total_score_0_100')}\n")
                f.write(f"Label: {result.get('label')}\n")
                if result.get("low_confidence"):
                    f.write("Note: LOW CONFIDENCE (missing/weak source signals)\n")

        scored += 1

    print(f"Scored & wrote files: {scored}")
    print(f"Skipped (no wikipedia profile): {skipped_no_profile}")
    print(f"Output dir: {SETTINGS.responses_dir}")


if __name__ == "__main__":
    main()
