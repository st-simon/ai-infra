# News Briefing Delivery

Date: 2026-06-13
Scope: delivery path for `agents/news_briefing/agent.py`

## Decision

Keep Markdown files in `logs/` as the source of record.

Delivery progresses in five steps:

1. Keep the existing Markdown briefing output.
2. Generate local email-ready drafts from the Markdown briefing.
3. Generate a Gmail draft request file for Codex/Gmail MCP to consume.
4. Codex automation consumes the request and creates a Gmail draft.
5. Enable automatic sending only after draft mode is verified and recipient policy is explicit.

## Current Status

Current implementation supports Gmail draft handoff. The local Python process
writes a draft request under `logs/`, and Codex uses the Gmail MCP connector to
create the Gmail draft.

The daily execution path is intentionally split:

- `launchd` runs the local news briefing agent at 07:00.
- Codex automation `ai-infra-daily-gmail-draft-handoff` runs at 07:45 and uses
  Gmail MCP to create the actual Gmail draft.

Phase 1 should be judged by whether the Markdown briefing is reliable and
readable. HTML, EML, and Gmail request JSON are delivery packaging, not separate
editorial formats to maintain by hand.

Each real run writes:

```text
logs/*_briefing.md
logs/source_health/*_source_health.jsonl
logs/email_drafts/*_briefing_email.html
logs/email_drafts/*_briefing_email.eml
logs/gmail_draft_requests/*_gmail_draft_request.json
```

`--dry-run` does not write any of these files.

## Configuration

Delivery configuration lives in:

```text
config/delivery.yaml
```

Defaults:

- `email.enabled: true`
- `email.mode: gmail_draft`
- `email.to_env: AI_INFRA_BRIEFING_TO`
- `email.gmail_draft_enabled: true`
- `email.auto_send_enabled: false`

Keep `email.auto_send_enabled: false` unless the user separately approves
automatic sending.

Set the recipient locally, not in committed config:

```bash
AI_INFRA_BRIEFING_TO=your-address@example.com
```

The key is case-sensitive and must be spelled exactly as
`AI_INFRA_BRIEFING_TO`.

`scripts/run_news_briefing.sh` loads `.env` before running the agent, so launchd
can use this value without committing the address.

## Gmail Boundary

Gmail is a reasonable delivery channel for this public-news briefing, but it
starts as draft-only.

The Gmail MCP connector has been verified for:

- reading labels
- reading drafts
- creating a test draft

The project still treats Gmail as a handoff boundary: the request JSON is the
local artifact; the connector creates the actual Gmail draft.

As of 2026-06-15, the Codex automation responsible for this handoff is:

```text
ai-infra-daily-gmail-draft-handoff
```

This is a staged solution. If Codex App is closed or unavailable, the local
launchd job may still generate the request JSON, but Gmail draft creation is not
guaranteed. The local Gmail API draft-only smoke test passed on 2026-06-16.
The local request consumer has also been verified and wired into
`scripts/run_news_briefing.sh`, so future launchd runs can create Gmail drafts
without Codex App while preserving draft-only behavior.

Do not auto-send until these are explicit:

- recipient
- sender account
- OAuth permission boundary
- duplicate-send behavior
- failure and retry behavior

Keep Gmail account-specific authorization outside this repository.
