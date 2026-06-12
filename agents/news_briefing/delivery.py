"""Email draft generation for the news briefing agent.

This module intentionally stops at local draft files. Gmail integration should
create drafts first, then only later enable automatic sending after permissions
and recipient policy are explicit.
"""

from __future__ import annotations

import html
import os
import re
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DELIVERY_CONFIG_PATH = PROJECT_ROOT / "config" / "delivery.yaml"


def load_delivery_config(path: Path = DELIVERY_CONFIG_PATH) -> dict:
    if not path.exists():
        return {"email": {"enabled": False}}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"email": {"enabled": False}}


def briefing_subject(markdown: str, prefix: str = "每日简报") -> str:
    first_line = next((line.strip("# ").strip() for line in markdown.splitlines() if line), "")
    if first_line:
        return first_line
    date_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    return f"{prefix} {date_str}"


def markdown_to_email_html(markdown: str) -> str:
    body = []
    in_list = False
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            if in_list:
                body.append("</ol>")
                in_list = False
            continue
        if line.startswith("# "):
            if in_list:
                body.append("</ol>")
                in_list = False
            body.append(f"<h1>{html.escape(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            if in_list:
                body.append("</ol>")
                in_list = False
            body.append(f"<h2>{html.escape(line[3:].strip())}</h2>")
        elif re.match(r"^\d+\. ", line):
            if not in_list:
                body.append("<ol>")
                in_list = True
            item = re.sub(r"^\d+\. ", "", line)
            item = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", html.escape(item))
            body.append(f"<li>{item}</li>")
        else:
            if line.startswith("原文："):
                text = html.escape(line.removeprefix("原文："))
                body.append(f"<p class=\"source\">原文：{text}</p>")
            else:
                body.append(f"<p>{html.escape(line)}</p>")
    if in_list:
        body.append("</ol>")

    return "\n".join([
        "<!doctype html>",
        "<html>",
        "<head>",
        "<meta charset=\"utf-8\">",
        "<style>",
        "body{font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif;line-height:1.55;color:#111;}",
        "h1{font-size:24px;} h2{font-size:18px;margin-top:24px;} li{margin:10px 0;} .source{color:#555;font-size:13px;}",
        "</style>",
        "</head>",
        "<body>",
        *body,
        "</body>",
        "</html>",
    ])


def write_local_email_draft(markdown: str, config: dict, generated_at: datetime | None = None) -> dict:
    email_conf = config.get("email", {})
    generated_at = generated_at or datetime.now(timezone(timedelta(hours=8)))
    draft_dir = PROJECT_ROOT / email_conf.get("local_draft_dir", "logs/email_drafts")
    draft_dir.mkdir(parents=True, exist_ok=True)

    stem = generated_at.strftime("%Y%m%d_%H%M") + "_briefing_email"
    subject = briefing_subject(markdown, email_conf.get("subject_prefix", "每日简报"))
    html_body = markdown_to_email_html(markdown)

    html_path = draft_dir / f"{stem}.html"
    html_path.write_text(html_body, encoding="utf-8")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_conf.get("from", "")
    msg["To"] = email_conf.get("to", "")
    msg["Date"] = formatdate(localtime=True)
    msg.set_content(markdown)
    msg.add_alternative(html_body, subtype="html")

    eml_path = draft_dir / f"{stem}.eml"
    eml_path.write_bytes(bytes(msg))

    return {
        "mode": "local_draft",
        "subject": subject,
        "html_path": str(html_path),
        "eml_path": str(eml_path),
    }


def create_gmail_draft(markdown: str, config: dict) -> dict:
    raise NotImplementedError("Gmail draft creation requires a Gmail MCP connector that is not available in this Codex session.")


def deliver_briefing(markdown: str, config: dict | None = None) -> dict:
    config = config or load_delivery_config()
    email_conf = config.get("email", {})
    if not email_conf.get("enabled", False):
        return {"mode": "disabled"}

    if email_conf.get("auto_send_enabled", False):
        raise NotImplementedError("Automatic email sending is intentionally disabled until draft mode is verified.")

    if email_conf.get("gmail_draft_enabled", False):
        return create_gmail_draft(markdown, config)

    return write_local_email_draft(markdown, config)
