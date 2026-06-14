# News Briefing Scheduling

Date: 2026-06-13
Scope: daily local run for `agents/news_briefing/agent.py`

## Decision

Use `launchd` as the default daily automation path on macOS.

Keep `scheduler.py` only as a foreground fallback for development or manual
long-running sessions. The Phase 1 production path is `launchd`; do not run both
automation paths at the same time.

## Daily Schedule

The launchd template runs once per day at 07:00 local Mac time.

Gmail draft creation is a second step handled by Codex automation at 07:45 local
Mac time:

```text
ai-infra-daily-gmail-draft-handoff
```

This automation consumes `logs/gmail_draft_requests/*_gmail_draft_request.json`
and creates the Gmail draft through Gmail MCP. It does not send email.

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

If a Gmail request exists but no Gmail draft appears, check the Codex automation
`ai-infra-daily-gmail-draft-handoff`.

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
.venv/bin/python scheduler.py --no-run-now
```
