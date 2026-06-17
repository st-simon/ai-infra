# News Briefing Scheduling

Date: 2026-06-13
Scope: daily scheduling for `agents/news_briefing/agent.py`

## Decision

Use Cloud Run Job + Cloud Scheduler as the production automation path so the
daily briefing does not depend on the Mac being awake or online. See
`docs/CLOUD_RUN_AUTOMATION.md`.

Keep `launchd` and `scheduler.py` only as local fallback/debugging paths. Do not
run multiple production schedulers at the same time.

## Daily Schedule

The Cloud Scheduler target should run once per day at 07:13 Asia/Shanghai.

The launchd template runs once per day at 07:00 local Mac time when the local
fallback is installed.

Gmail draft creation is handled locally after the news briefing script succeeds.
`scripts/run_news_briefing.sh` consumes the newest
`logs/gmail_draft_requests/*_gmail_draft_request.json` file through
`scripts/gmail_api_create_draft_from_request.py` and creates a Gmail draft
through the local Gmail API. It does not send email.

The previous Codex automation handoff is retained as a staged fallback/reference:

```text
ai-infra-daily-gmail-draft-handoff
```

It consumed `logs/gmail_draft_requests/*_gmail_draft_request.json` through Gmail
MCP, but it depends on Codex App availability and should not be the primary
daily path.

Project path:

```bash
/Users/junxia/codex-projects/projects/ai-infra
```

Launchd label:

```bash
com.junxia.ai-infra.news-briefing
```

## Verify Before Installing

```bash
cd /Users/junxia/codex-projects/projects/ai-infra
.venv/bin/python agents/news_briefing/agent.py --dry-run
scripts/run_news_briefing.sh
```

`--dry-run` does not write briefing files or source-health files. `scripts/run_news_briefing.sh` performs a real run and writes outputs under `logs/`.

## Install

```bash
cd /Users/junxia/codex-projects/projects/ai-infra
scripts/install_daily_briefing_launchd.sh
```

The installer copies:

```bash
deploy/launchd/com.junxia.ai-infra.news-briefing.plist
```

to:

```bash
~/Library/LaunchAgents/com.junxia.ai-infra.news-briefing.plist
```

and loads it with `launchctl`.

## Check Status

```bash
launchctl list | grep com.junxia.ai-infra.news-briefing
```

Run logs:

```bash
logs/launchd-news-briefing.out.log
logs/launchd-news-briefing.err.log
```

Briefing outputs:

```bash
logs/*_briefing.md
logs/source_health/*_source_health.jsonl
logs/email_drafts/*_briefing_email.html
logs/email_drafts/*_briefing_email.eml
logs/gmail_draft_requests/*_gmail_draft_request.json
```

If Markdown and local email drafts are created but no Gmail request appears,
check that `.env` contains a non-empty `AI_INFRA_BRIEFING_TO` entry. The key name
is case-sensitive.

If a Gmail request exists but no Gmail draft appears, run:

```bash
.venv/bin/python scripts/gmail_api_create_draft_from_request.py --latest --dry-run
```

Then check the launchd logs and the local Gmail API setup in
`docs/GMAIL_API_AUTOMATION.md`.

## Manual Trigger

```bash
launchctl start com.junxia.ai-infra.news-briefing
```

## Uninstall

```bash
cd /Users/junxia/codex-projects/projects/ai-infra
scripts/uninstall_daily_briefing_launchd.sh
```

## Foreground Fallback

Use this only when you want a visible long-running Python process:

```bash
cd /Users/junxia/codex-projects/projects/ai-infra
.venv/bin/python scheduler.py
```

Use `.venv/bin/python scheduler.py --run-now` only when you want one immediate
briefing run before the foreground scheduler starts.
