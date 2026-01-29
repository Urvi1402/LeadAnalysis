from __future__ import annotations

from pathlib import Path
from typing import Optional

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_gmail_service(credentials_path: Path, token_path: Path):
    """
    Creates Gmail API service using OAuth tokens.
    First run: prints a URL, you authenticate, token.json gets saved.
    """
    creds: Optional[Credentials] = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            # safer in WSL/headless: don't auto-open browser
            creds = flow.run_local_server(port=0, open_browser=False)

        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)
