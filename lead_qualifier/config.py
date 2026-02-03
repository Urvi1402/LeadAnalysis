# from __future__ import annotations

# from dataclasses import dataclass
# from pathlib import Path
# import os

# from dotenv import load_dotenv


# def _as_bool(name: str, default: bool = False) -> bool:
#     v = os.getenv(name)
#     if v is None:
#         return default
#     return v.strip().lower() in {"1", "true", "yes", "y", "on"}


# def _find_project_root(start_dir: Path) -> Path:
#     """
#     Walk upwards from start_dir until we find a marker that indicates repo root.
#     This avoids brittle parents[n] assumptions.
#     """
#     for p in [start_dir] + list(start_dir.parents):
#         if (p / ".env").exists() or (p / ".git").exists() or (p / "pyproject.toml").exists():
#             return p
#     # Fallback: 2 levels up from this file (typical: repo/lead_qualifier/config.py)
#     return start_dir.parents[1]


# def _as_path(env_name: str, default_rel: str, project_root: Path) -> Path:
#     """
#     Reads a path from env; if relative, interpret it relative to project_root.
#     """
#     raw = os.getenv(env_name)
#     if raw and raw.strip():
#         p = Path(raw.strip())
#         if not p.is_absolute():
#             p = (project_root / p).resolve()
#         return p
#     return (project_root / default_rel).resolve()


# # --- locate repo root + load .env ---
# _THIS_FILE = Path(__file__).resolve()
# PROJECT_ROOT = _find_project_root(_THIS_FILE.parent)

# # Allow override via env var if you ever want it
# ENV_PATH = Path(os.getenv("LEAD_QUALIFIER_ENV_PATH", str(PROJECT_ROOT / ".env")))

# if ENV_PATH.exists():
#     # override=True prevents "sticky" shell vars from beating your .env during dev
#     load_dotenv(ENV_PATH, override=True)


# @dataclass(frozen=True)
# class Settings:
#     # Core app
#     gmail_query: str = os.getenv("GMAIL_QUERY", "in:inbox is:unread newer_than:7d")
#     max_emails_per_run: int = int(os.getenv("MAX_EMAILS_PER_RUN", "50"))

#     db_path: Path = _as_path("DB_PATH", "data/app.db", PROJECT_ROOT)
#     responses_dir: Path = _as_path("RESPONSES_DIR", "responses", PROJECT_ROOT)

#     # Gmail OAuth files (local)
#     credentials_path: Path = _as_path("GMAIL_CREDENTIALS_PATH", "credentials.json", PROJECT_ROOT)
#     token_path: Path = _as_path("GMAIL_TOKEN_PATH", "token.json", PROJECT_ROOT)

#     # Search provider
#     search_provider: str = os.getenv("SEARCH_PROVIDER", "serper").strip().lower()

#     # SearXNG
#     searxng_url: str = os.getenv("SEARXNG_URL", "http://localhost:8080").rstrip("/")
#     searxng_timeout_s: int = int(os.getenv("SEARXNG_TIMEOUT_S", "20"))

#     # Serper (optional fallback)
#     serper_api_key: str = os.getenv("SERPER_API_KEY", "")
#     serper_endpoint: str = os.getenv("SERPER_ENDPOINT", "https://google.serper.dev/search").rstrip("/")

#     # OpenSearch (optional, separate concern)
#     opensearch_url: str = os.getenv("OPENSEARCH_URL", "https://localhost:9200").rstrip("/")
#     opensearch_user: str = os.getenv("OPENSEARCH_USER", "admin")
#     opensearch_password: str = os.getenv("OPENSEARCH_PASSWORD", "")
#     opensearch_index: str = os.getenv("OPENSEARCH_INDEX", "company_pages")
#     opensearch_verify_tls: bool = _as_bool("OPENSEARCH_VERIFY_TLS", False)
#     opensearch_verify_ssl: bool = _as_bool("OPENSEARCH_VERIFY_SSL", False)

#     # LLM extraction (optional)
#     use_llm_extraction: bool = _as_bool("USE_LLM_EXTRACTION", False)
#     llm_base_url: str = os.getenv("LLM_BASE_URL", "").rstrip("/")
#     llm_model: str = os.getenv("LLM_MODEL", "")
#     llm_api_key: str = os.getenv("LLM_API_KEY", "")


# SETTINGS = Settings()


from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv


def _as_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or not v.strip():
        return default
    try:
        return int(v.strip())
    except Exception:
        return default


def _as_float(name: str, default: float) -> float:
    v = os.getenv(name)
    if v is None or not v.strip():
        return default
    try:
        return float(v.strip())
    except Exception:
        return default


# Always load .env from repo root (so running scripts from any folder works)
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../LeadQualifier
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(ENV_PATH, override=False)


@dataclass(frozen=True)
class Settings:
    # Core app
    gmail_query: str = os.getenv("GMAIL_QUERY", "in:inbox is:unread newer_than:7d")
    db_path: Path = Path(os.getenv("DB_PATH", "data/app.db"))
    responses_dir: Path = Path(os.getenv("RESPONSES_DIR", "responses"))
    max_emails_per_run: int = _as_int("MAX_EMAILS_PER_RUN", 50)

    # Gmail OAuth files (local)
    credentials_path: Path = Path(os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json"))
    token_path: Path = Path(os.getenv("GMAIL_TOKEN_PATH", "token.json"))

    # Search provider
    search_provider: str = os.getenv("SEARCH_PROVIDER", "serper").strip().lower()

    # SearXNG
    searxng_url: str = os.getenv("SEARXNG_URL", "http://localhost:8080").rstrip("/")
    searxng_timeout_s: int = _as_int("SEARXNG_TIMEOUT_S", 20)

    # Serper (optional fallback)
    serper_api_key: str = os.getenv("SERPER_API_KEY", "")
    serper_endpoint: str = os.getenv("SERPER_ENDPOINT", "https://google.serper.dev/search").rstrip("/")

    # OpenSearch (optional, separate concern)
    opensearch_url: str = os.getenv("OPENSEARCH_URL", "https://localhost:9200").rstrip("/")
    opensearch_user: str = os.getenv("OPENSEARCH_USER", "admin")
    opensearch_password: str = os.getenv("OPENSEARCH_PASSWORD", "")
    opensearch_index: str = os.getenv("OPENSEARCH_INDEX", "company_pages")
    opensearch_verify_tls: bool = _as_bool("OPENSEARCH_VERIFY_TLS", False)
    opensearch_verify_ssl: bool = _as_bool("OPENSEARCH_VERIFY_SSL", False)

    # LLM extraction (optional)
    use_llm_extraction: bool = _as_bool("USE_LLM_EXTRACTION", False)
    llm_base_url: str = os.getenv("LLM_BASE_URL", "").rstrip("/")
    llm_model: str = os.getenv("LLM_MODEL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")

    # LLM scoring (NEW)
    use_llm_scoring: bool = _as_bool("USE_LLM_SCORING", False)

    llm_scoring_base_url: str = os.getenv("LLM_SCORING_BASE_URL", "").rstrip("/") or llm_base_url
    llm_scoring_model: str = os.getenv("LLM_SCORING_MODEL", "").strip() or llm_model
    llm_scoring_api_key: str = os.getenv("LLM_SCORING_API_KEY", "").strip() or llm_api_key

    llm_scoring_temperature: float = _as_float("LLM_SCORING_TEMPERATURE", 0.0)
    llm_scoring_max_tokens: int = _as_int("LLM_SCORING_MAX_TOKENS", 900)

    # Preferences to guide the LLM's domain relevance scoring (optional)
    domain_preferences_raw: str = os.getenv("DOMAIN_PREFERENCES", "").strip()

    @property
    def domain_preferences(self) -> list[str]:
        if not self.domain_preferences_raw:
            return []
        return [x.strip() for x in self.domain_preferences_raw.split(",") if x.strip()]


SETTINGS = Settings()
