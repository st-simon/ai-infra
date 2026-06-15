# Gmail API Local Automation

Date: 2026-06-15
Verified: 2026-06-16
Scope: local draft-only Gmail API path for news briefing delivery

## Decision

Use a local Gmail API OAuth flow for unattended draft creation. Codex MCP remains
useful for interactive work, but daily news delivery should not depend on Codex
App being open.

The local Gmail API path must stay draft-only: it may create Gmail drafts, but
it must not send email.

## Smoke Test

Do not connect this to `launchd` until the smoke test creates a visible Gmail
draft.

```bash
cd /Users/junxia/codex-projects/projects/ai-infra
.venv/bin/python scripts/gmail_api_draft_smoke.py --check
.venv/bin/python scripts/gmail_api_draft_smoke.py
```

Pass criteria:

- Gmail Drafts shows `ai-infra Gmail API draft smoke test`.
- No email is sent.

Result: passed on 2026-06-16. The OAuth token exists outside the repository,
the dependency check passes, and Gmail Drafts shows the smoke-test draft.

## Request Consumer

`scripts/gmail_api_create_draft_from_request.py` consumes an existing
`logs/gmail_draft_requests/*_gmail_draft_request.json` file and creates a
Gmail draft through the local Gmail API path.

```bash
.venv/bin/python scripts/gmail_api_create_draft_from_request.py --latest --dry-run
.venv/bin/python scripts/gmail_api_create_draft_from_request.py --latest
```

Result: verified on 2026-06-16 with a temporary request JSON. Gmail Drafts
showed `ai-infra Gmail API request consumer smoke test`; no email was sent.

`scripts/run_news_briefing.sh` now runs the consumer after the news briefing
agent succeeds. Set `AI_INFRA_GMAIL_API_DRAFT_ENABLED=false` to disable this
step.
