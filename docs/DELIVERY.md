# News Briefing Delivery

Date: 2026-06-12
Scope: delivery path for `agents/news_briefing/agent.py`

## Decision

Keep Markdown files in `logs/` as the source of record.

Delivery progresses in four steps:

1. Keep the existing Markdown briefing output.
2. Generate local email-ready drafts from the Markdown briefing.
3. When a Gmail connector is available in this runtime, create Gmail drafts first.
4. Enable automatic sending only after draft mode is verified and recipient policy is explicit.

## Current Status

Current implementation stops at local draft generation.

Each real run writes:

```text
logs/*_briefing.md
logs/source_health/*_source_health.jsonl
logs/email_drafts/*_briefing_email.html
logs/email_drafts/*_briefing_email.eml
```

`--dry-run` does not write any of these files.

## Configuration

Delivery configuration lives in:

```text
config/delivery.yaml
```

Defaults:

- `email.enabled: true`
- `email.mode: local_draft`
- `email.gmail_draft_enabled: false`
- `email.auto_send_enabled: false`

Leave Gmail draft and auto-send disabled until the Gmail MCP connector is available in the runtime that executes this project.

## Gmail Boundary

Gmail is a reasonable eventual delivery channel for this public-news briefing, but it should start as draft-only.

Do not auto-send until these are explicit:

- recipient
- sender account
- OAuth permission boundary
- duplicate-send behavior
- failure and retry behavior

At the time this document was written, this Codex session did not expose a Gmail MCP connector. Project docs note that Gmail/Calendar were connected in Claude.ai, which is a separate runtime.
