import sqlite3
from typing import Optional, Dict, Any

def upsert_email(conn: sqlite3.Connection, email: Dict[str, Any]) -> int:
    """
    Insert email if not exists. Return internal email row id.
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO emails
        (gmail_message_id, thread_id, internal_date, from_name, from_email, subject, snippet, body_text, received_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            email["gmail_message_id"],
            email.get("thread_id"),
            email.get("internal_date"),
            email.get("from_name"),
            email.get("from_email"),
            email.get("subject"),
            email.get("snippet"),
            email.get("body_text"),
            email.get("received_at"),
        ),
    )
    row = conn.execute(
        "SELECT id FROM emails WHERE gmail_message_id = ?",
        (email["gmail_message_id"],),
    ).fetchone()
    conn.commit()
    return int(row["id"])

def mark_email_processed(conn: sqlite3.Connection, email_id: int) -> None:
    conn.execute("UPDATE emails SET processed = 1 WHERE id = ?", (email_id,))
    conn.commit()

def upsert_company(conn, name: str, normalized_name: str) -> tuple[int, bool]:
    """
    Returns (company_id, created_new)
    """
    # Check if exists
    existing = conn.execute(
        "SELECT id FROM companies WHERE normalized_name = ?",
        (normalized_name,),
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE companies
            SET last_seen_at = datetime('now'),
                name = CASE WHEN length(?) > length(name) THEN ? ELSE name END
            WHERE normalized_name = ?
            """,
            (name, name, normalized_name),
        )
        conn.commit()
        return int(existing["id"]), False

    conn.execute(
        "INSERT INTO companies (name, normalized_name) VALUES (?, ?)",
        (name, normalized_name),
    )
    row = conn.execute(
        "SELECT id FROM companies WHERE normalized_name = ?",
        (normalized_name,),
    ).fetchone()
    conn.commit()
    return int(row["id"]), True


def link_email_company(
    conn: sqlite3.Connection,
    email_id: int,
    company_id: int,
    confidence: Optional[float],
    source: str,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO email_companies (email_id, company_id, confidence, source)
        VALUES (?, ?, ?, ?)
        """,
        (email_id, company_id, confidence, source),
    )
    conn.commit()
