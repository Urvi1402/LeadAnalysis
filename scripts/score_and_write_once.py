from __future__ import annotations

import json
from pathlib import Path

from lead_qualifier.config import SETTINGS
from lead_qualifier.storage.db import get_conn, init_db
from lead_qualifier.scoring.rules import compute_weighted_score

# NEW
from lead_qualifier.scoring.llm_scorer import score_with_llm


def safe_filename(name: str) -> str:
    keep = []
    for ch in name:
        if ch.isalnum() or ch in (" ", "-", "_"):
            keep.append(ch)
    out = "".join(keep).strip().replace(" ", "_")
    return out or "company"


def _map_1to5_to_100(x: int) -> int:
    return {1: 20, 2: 40, 3: 60, 4: 80, 5: 100}.get(int(x), 40)


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

        # ---- SCORING BRANCH ----
        if SETTINGS.use_llm_scoring:
            llm_result = score_with_llm(name, profile)

            subs = llm_result.get("subscores_1_to_5", {}) or {}
            total = llm_result.get("total_score_0_100")
            label = llm_result.get("label")
            conf = llm_result.get("confidence")

            # if total missing, compute from subs as fallback
            if total is None:
                weights = {
                    "age": 10,
                    "employees": 10,
                    "financial": 10,
                    "founders": 5,
                    "domain": 25,
                    "project": 20,
                    "geo": 20,
                }
                s = 0.0
                wsum = 0.0
                for k, w in weights.items():
                    v = subs.get(k, 2)
                    s += w * _map_1to5_to_100(int(v))
                    wsum += w
                total = int(round(s / max(wsum, 1.0)))

            result = {
                "method": "llm",
                "total_score_0_100": int(total),
                "label": label or "Medium",
                "confidence": conf if conf is not None else 0.6,
                "subscores_1_to_5": subs,
                "missing_fields": llm_result.get("missing_fields", []),
                "red_flags": llm_result.get("red_flags", []),
                "rationale_bullets": llm_result.get("rationale_bullets", []),
                "recommended_next_steps": llm_result.get("recommended_next_steps", []),
            }

        else:
            # old deterministic path
            rr = compute_weighted_score(profile)
            result = {"method": "rules", **rr}

        # ---- WRITE OUTPUT FILE ----
        out_path = SETTINGS.responses_dir / f"{safe_filename(name)}.txt"
        with out_path.open("w", encoding="utf-8") as f:
            f.write(f"Company: {name}\n")
            f.write(f"Source: {profile.get('source')} | URL: {profile.get('source_url')}\n")
            f.write(f"Scoring method: {result.get('method')}\n\n")

            f.write("Extracted Metrics\n")
            f.write(f"- Founded year: {profile.get('founded_year')}\n")
            f.write(f"- Employees: {profile.get('employees')}\n")
            f.write(f"- HQ: {profile.get('hq_location')}\n")
            f.write(f"- Industry: {profile.get('industry')}\n")
            f.write(f"- Revenue: {profile.get('revenue')}\n")
            f.write(f"- Profile confidence: {profile.get('confidence')}\n\n")

            f.write("Scoring Breakdown (1–5)\n")
            subs = result.get("subscores_1_to_5", {}) or {}
            f.write(f"- Age/Longevity (10%): {subs.get('age')}\n")
            f.write(f"- Employees Strength (10%): {subs.get('employees')}\n")
            f.write(f"- Financial Stability (10%): {subs.get('financial')}\n")
            f.write(f"- Founders Profile (5%): {subs.get('founders')}\n")
            f.write(f"- Domain Relevance (25%): {subs.get('domain')}\n")
            f.write(f"- Project Quality & Fit (20%): {subs.get('project')}\n")
            f.write(f"- Geographic Advantage (20%): {subs.get('geo')}\n\n")

            f.write(f"Weighted score (0–100): {result.get('total_score_0_100')}\n")
            f.write(f"Label: {result.get('label')}\n")
            if "confidence" in result:
                f.write(f"LLM confidence: {result.get('confidence')}\n")

            # extra LLM narrative sections (only if present)
            if result.get("missing_fields"):
                f.write("\nMissing / weak data\n")
                for x in result["missing_fields"]:
                    f.write(f"- {x}\n")

            if result.get("red_flags"):
                f.write("\nRed flags\n")
                for x in result["red_flags"]:
                    f.write(f"- {x}\n")

            if result.get("rationale_bullets"):
                f.write("\nRationale\n")
                for x in result["rationale_bullets"]:
                    f.write(f"- {x}\n")

            if result.get("recommended_next_steps"):
                f.write("\nRecommended next steps\n")
                for x in result["recommended_next_steps"]:
                    f.write(f"- {x}\n")

        scored += 1

    print(f"Scored & wrote files: {scored}")
    print(f"Skipped (no wikipedia profile): {skipped_no_profile}")
    print(f"Output dir: {SETTINGS.responses_dir}")


if __name__ == "__main__":
    main()
