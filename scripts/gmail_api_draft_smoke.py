#!/usr/bin/env python3
"""Create a Gmail draft through the local Gmail API OAuth flow.

This is a smoke-test script. It creates drafts only and never sends email.
OAuth client and token files live outside the repository by default.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "ai-infra"
DEFAULT_CLIENT_FILE = DEFAULT_CONFIG_DIR / "gmail_oauth_client.json"
DEFAULT_TOKEN_FILE = DEFAULT_CONFIG_DIR / "gmail_token.json"
DEFAULT_SUBJECT = "ai-infra Gmail API draft smoke test"


def _dependency_status() -> dict[str, bool]:
    modules = [
        "googleapiclient.discovery",
        "google.auth.transport.requests",
        "google.oauth2.credentials",
        "google_auth_oauthlib.flow",
    ]
    status = {}
    for module in modules:
        try:
            __import__(module)
            status[module] = True
        except Exception:
            status[module] = False
    return status


def _load_google_modules():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    return Request, Credentials, InstalledAppFlow, build


def _expand(path_value: str | None, default: Path) -> Path:
    if not path_value:
        return default
    return Path(path_value).expanduser()


def get_credentials(client_file: Path, token_file: Path):
    Request, Credentials, InstalledAppFlow, _build = _load_google_modules()

    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid:
        if not client_file.exists():
            raise FileNotFoundError(
                f"Missing Gmail OAuth client file: {client_file}. "
                "Create a Google Cloud OAuth desktop client and save it there."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
        creds = flow.run_local_server(port=0)

    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    token_file.chmod(0o600)
    return creds


def build_message(to: str, subject: str, body: str) -> dict:
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    encoded = base64.urlsafe_b64encode(bytes(message)).decode("ascii")
    return {"message": {"raw": encoded}}


def create_draft(to: str, subject: str, body: str, client_file: Path, token_file: Path) -> dict:
    _request, _credentials, _flow, build = _load_google_modules()
    creds = get_credentials(client_file, token_file)
    service = build("gmail", "v1", credentials=creds)
    return service.users().drafts().create(
        userId="me",
        body=build_message(to, subject, body),
    ).execute()


def check_environment(client_file: Path, token_file: Path, recipient: str) -> dict:
    dependency_status = _dependency_status()
    return {
        "dependencies_ok": all(dependency_status.values()),
        "dependencies": dependency_status,
        "client_file": str(client_file),
        "client_file_exists": client_file.exists(),
        "token_file": str(token_file),
        "token_file_exists": token_file.exists(),
        "recipient_configured": bool(recipient),
        "scopes": SCOPES,
    }


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Create a Gmail API draft smoke test.")
    parser.add_argument("--check", action="store_true", help="Check local setup without OAuth.")
    parser.add_argument("--to", default=os.getenv("AI_INFRA_BRIEFING_TO", ""))
    parser.add_argument("--subject", default=DEFAULT_SUBJECT)
    parser.add_argument(
        "--body",
        default=(
            "This is a local Gmail API draft-only smoke test from ai-infra.\n\n"
            "If this appears in Gmail Drafts, local Gmail API draft creation works."
        ),
    )
    parser.add_argument(
        "--client-file",
        default=os.getenv("GMAIL_OAUTH_CLIENT_FILE", str(DEFAULT_CLIENT_FILE)),
    )
    parser.add_argument(
        "--token-file",
        default=os.getenv("GMAIL_OAUTH_TOKEN_FILE", str(DEFAULT_TOKEN_FILE)),
    )
    args = parser.parse_args()

    client_file = _expand(args.client_file, DEFAULT_CLIENT_FILE)
    token_file = _expand(args.token_file, DEFAULT_TOKEN_FILE)
    recipient = args.to.strip()

    if args.check:
        print(json.dumps(
            check_environment(client_file, token_file, recipient),
            ensure_ascii=False,
            indent=2,
        ))
        return 0

    if not recipient:
        print("Missing recipient. Set AI_INFRA_BRIEFING_TO or pass --to.", file=sys.stderr)
        return 2

    try:
        draft = create_draft(recipient, args.subject, args.body, client_file, token_file)
    except Exception as exc:
        print(f"Gmail API draft smoke test failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({
        "mode": "gmail_api_draft_smoke",
        "draft_id": draft.get("id"),
        "message_id": draft.get("message", {}).get("id"),
        "to": recipient,
        "subject": args.subject,
        "sent": False,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
