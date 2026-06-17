#!/usr/bin/env python3
"""Create a Gmail draft from a news briefing request JSON.

This local automation path is draft-only. It never sends email.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

import gmail_api_draft_smoke as smoke

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUEST_DIR = PROJECT_ROOT / "logs" / "gmail_draft_requests"
DEFAULT_STATE_FILE = PROJECT_ROOT / "logs" / "gmail_api_drafts.json"


class DraftRequestError(ValueError):
    pass


def normalize_subject(subject: str) -> str:
    return re.sub(r"\s+", " ", subject).strip()


def latest_request(request_dir: Path) -> Path:
    candidates = sorted(request_dir.glob("*_gmail_draft_request.json"))
    if not candidates:
        raise FileNotFoundError(f"No Gmail draft request found in {request_dir}.")
    return candidates[-1]


def request_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_request(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise DraftRequestError("Draft request JSON must be an object.")
    if data.get("auto_send_enabled") is not False:
        raise DraftRequestError("Refusing request unless auto_send_enabled is false.")

    recipient = str(data.get("to", "")).strip()
    subject = normalize_subject(str(data.get("subject", "")))
    body = str(data.get("body", "")).strip()
    if not recipient:
        raise DraftRequestError("Missing recipient field: to.")
    if not subject:
        raise DraftRequestError("Missing subject.")
    if not body:
        raise DraftRequestError("Missing body.")
    return {"to": recipient, "subject": subject, "body": body}


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "drafts": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"version": 1, "drafts": []}
    data.setdefault("drafts", [])
    return data


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_record(state: dict[str, Any], digest: str) -> dict[str, Any] | None:
    for record in state.get("drafts", []):
        if record.get("request_sha256") == digest:
            return record
    return None


def default_private_files():
    client_file = smoke._expand(os.getenv("GMAIL_OAUTH_CLIENT_FILE"), smoke.DEFAULT_CLIENT_FILE)
    private_file = smoke._expand(os.getenv("GMAIL_OAUTH_TOKEN_FILE"), smoke.DEFAULT_TOKEN_FILE)
    if not client_file.exists() or not private_file.exists():
        raise DraftRequestError(
            "Missing local Gmail API authorization files. "
            "Run scripts/gmail_api_draft_smoke.py interactively first."
        )
    return client_file, private_file


def run(args: argparse.Namespace) -> dict[str, Any]:
    request_path = latest_request(args.request_dir) if args.latest else args.request
    if request_path is None:
        raise DraftRequestError("Pass a request JSON path or use --latest.")
    request_path = request_path.expanduser().resolve()
    request = load_request(request_path)
    digest = request_digest(request_path)
    state = load_state(args.state_file)

    existing = find_record(state, digest)
    if existing:
        return {
            "mode": "gmail_api_draft_request",
            "status": "skipped",
            "reason": "already_recorded",
            "request_path": str(request_path),
            "draft_id": existing.get("draft_id"),
            "subject": request["subject"],
            "sent": False,
        }

    if args.dry_run:
        return {
            "mode": "gmail_api_draft_request",
            "status": "validated",
            "request_path": str(request_path),
            "to": request["to"],
            "subject": request["subject"],
            "request_sha256": digest,
            "sent": False,
        }

    client_file, private_file = default_private_files()
    draft = smoke.create_draft(
        request["to"],
        request["subject"],
        request["body"],
        client_file,
        private_file,
    )
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "request_path": str(request_path),
        "request_sha256": digest,
        "subject": request["subject"],
        "to": request["to"],
        "draft_id": draft.get("id"),
        "message_id": draft.get("message", {}).get("id"),
        "status": "created",
        "sent": False,
    }
    state.setdefault("drafts", []).append(record)
    write_state(args.state_file, state)
    return {
        "mode": "gmail_api_draft_request",
        "status": "created",
        "request_path": str(request_path),
        "draft_id": draft.get("id"),
        "message_id": draft.get("message", {}).get("id"),
        "subject": request["subject"],
        "sent": False,
    }


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser(description="Create a Gmail API draft from a request JSON.")
    parser.add_argument("request", nargs="?", type=Path)
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--request-dir", type=Path, default=DEFAULT_REQUEST_DIR)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    args = parser.parse_args()
    args.request_dir = args.request_dir.expanduser()
    args.state_file = args.state_file.expanduser()

    try:
        result = run(args)
    except Exception as exc:
        print(f"Gmail API draft request failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
