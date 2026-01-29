from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    gmail_query: str = os.getenv("GMAIL_QUERY", "in:inbox is:unread newer_than:7d")
    db_path: Path = Path(os.getenv("DB_PATH", "data/app.db"))
    responses_dir: Path = Path(os.getenv("RESPONSES_DIR", "responses"))
    max_emails_per_run: int = int(os.getenv("MAX_EMAILS_PER_RUN", "50"))

    # Gmail OAuth files (local)
    credentials_path: Path = Path(os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json"))
    token_path: Path = Path(os.getenv("GMAIL_TOKEN_PATH", "token.json"))

SETTINGS = Settings()
