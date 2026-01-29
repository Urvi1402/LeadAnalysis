from __future__ import annotations

import os
from typing import Optional, Tuple

from lead_qualifier.config import SETTINGS
from lead_qualifier.storage.db import get_conn, init_db
from lead_qualifier.storage.crud import (
    upsert_email,
    upsert_company,
    link_email_company,
    mark_email_processed,
)
from lead_qualifier.ingestion.gmail_client import get_gmail_service
from lead_qualifier.ingestion.email_poller import fetch_message_ids, fetch_full_message
from lead_qualifier.ingestion.email_parser import parse_gmail_message
from lead_qualifier.extraction.company_extractor import pick_best_company
from lead_qualifier.extraction.email_filter import is_lead_email
from lead_qualifier.utils.normalize import normalize_company_name


def _llm_enabled() -> bool:
    return os.environ.get("USE_LLM_EXTRACTION", "0").strip() == "1"


def _try_llm_extract(
    subject: str, body: str, from_email: Optional[str]
) -> Tuple[Optional[str], Optional[float], Optional[str]]:
    """
    Returns (company_name, confidence, source) using the LLM extraction agent.
    If agent isn't installed / not configured, returns (None, None, None).
    """
    if not _llm_enabled():
        return None, None, None

    try:
        # You should have created this from earlier steps:
        # lead_qualifier/agents/extraction_agent.py
        from lead_qualifier.agents.extraction_agent import extract_with_llm  # type: ignore
    except Exception:
        # Agent not present or import fails
        return None, None, None

    try:
        res = extract_with_llm(subject, body, from_email)
    except Exception:
        # LLM call failed; don't break the pipeline
        return None, None, None

    if not res.is_lead:
        return None, None, None

    if not res.company_name:
        return None, None, None

    # Normalize to ensure it's usable
    norm = res.normalized_name or normalize_company_name(res.company_name)
    if not norm:
        return None, None, None

    return res.company_name, float(res.confidence or 0.0), "llm"


def main() -> None:
    SETTINGS.responses_dir.mkdir(parents=True, exist_ok=True)

    conn = get_conn(SETTINGS.db_path)
    init_db(conn)

    if not SETTINGS.credentials_path.exists():
        raise FileNotFoundError(
            f"Missing {SETTINGS.credentials_path}. Put your OAuth credentials JSON there."
        )

    service = get_gmail_service(SETTINGS.credentials_path, SETTINGS.token_path)

    msg_ids = fetch_message_ids(
        service, SETTINGS.gmail_query, max_results=SETTINGS.max_emails_per_run
    )
    print(f"Fetched {len(msg_ids)} Gmail message IDs (query='{SETTINGS.gmail_query}').")

    processed = 0
    skipped_nonlead = 0

    emails_with_company = 0
    new_unique_companies = 0
    links_created = 0

    for mid in msg_ids:
        msg = fetch_full_message(service, mid)
        parsed = parse_gmail_message(msg)
        email_id = upsert_email(conn, parsed)

        # If already processed locally, skip it
        row = conn.execute(
            "SELECT processed FROM emails WHERE id = ?", (email_id,)
        ).fetchone()
        if row and int(row["processed"]) == 1:
            continue

        subject = parsed.get("subject") or ""
        body = parsed.get("body_text") or ""
        from_email = parsed.get("from_email")

        # 1) Lead filter first (cheap)
        decision = is_lead_email(subject, body, from_email)
        if not decision.should_process:
            skipped_nonlead += 1
            mark_email_processed(conn, email_id)
            processed += 1
            continue

        # 2) Heuristic extraction first (cheap + fast)
        company_name, conf, src = pick_best_company(subject, body, from_email)

        # 3) Decide whether to call LLM extraction agent as fallback
        #    - No company found OR
        #    - confidence is low OR
        #    - normalization fails (likely garbage)
        needs_llm = False
        if not company_name:
            needs_llm = True
        elif conf is None or (isinstance(conf, float) and conf < 0.60):
            needs_llm = True
        else:
            norm_check = normalize_company_name(company_name)
            if not norm_check:
                needs_llm = True

        if needs_llm:
            llm_name, llm_conf, llm_src = _try_llm_extract(subject, body, from_email)
            if llm_name:
                company_name, conf, src = llm_name, llm_conf, llm_src

        # 4) Store company + link
        if company_name:
            norm = normalize_company_name(company_name)
            if norm:
                emails_with_company += 1
                company_id, created_new = upsert_company(conn, company_name, norm)
                if created_new:
                    new_unique_companies += 1

                link_email_company(conn, email_id, company_id, conf, src or "heuristic")
                links_created += 1

        mark_email_processed(conn, email_id)
        processed += 1

    total_unique = conn.execute("SELECT COUNT(*) AS n FROM companies").fetchone()["n"]

    print(
        f"Processed {processed} emails. "
        f"Skipped non-leads = {skipped_nonlead}. "
        f"Emails with company found = {emails_with_company}. "
        f"New unique companies added = {new_unique_companies}. "
        f"Links created = {links_created}. "
        f"Total unique companies in DB = {total_unique}."
    )
    print(f"DB: {SETTINGS.db_path}")
    print("Next: web enrichment + 7-day cache + scoring.")


if __name__ == "__main__":
    main()
