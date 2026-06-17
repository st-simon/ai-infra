# Cloud Run Automation

Date: 2026-06-16
Scope: stable cloud-first daily news briefing delivery

## Decision

Use Google Cloud Run Jobs plus Cloud Scheduler as the primary production path.
The Mac `launchd` path remains a local fallback only.

Target workflow:

```text
Cloud Scheduler -> Cloud Run Job -> News Briefing -> Gmail API draft
```

The Cloud Run path must remain draft-only. It creates a Gmail draft and never
sends email.

## Official Entry Points

- Cloud Run Jobs: https://cloud.google.com/run/docs/create-jobs
- Scheduled Cloud Run jobs: https://cloud.google.com/run/docs/execute/jobs-on-schedule
- Cloud Scheduler: https://cloud.google.com/scheduler/docs
- Gmail draft API: https://developers.google.com/workspace/gmail/api/guides/drafts

## Recommended Cloud Defaults

```text
Region: asia-east1
Time zone: Asia/Shanghai
Schedule: 13 7 * * *
Cloud Run Job: ai-infra-news-briefing
Cloud Scheduler Job: ai-infra-daily-news-briefing
Artifact Registry repository: ai-infra
```

The scheduled time is intentionally 07:13 rather than exactly 07:00.

## Runtime Configuration

The Cloud Run Job should set:

```text
MODEL_MODE=quality
AI_INFRA_GMAIL_API_DRAFT_ENABLED=auto
AI_INFRA_GMAIL_API_DRAFT_ATTEMPTS=3
AI_INFRA_GMAIL_API_DRAFT_RETRY_SECONDS=120
```

Provider-specific private values must be supplied by Google Cloud managed
runtime configuration, not committed to Git.

## Local Build Check

```bash
docker build -t ai-infra-news-briefing:local .
docker run --rm ai-infra-news-briefing:local python -m compileall agents shared scripts
```

If the Mac does not have Docker or `gcloud`, do the deployment from Google Cloud
Shell instead. Cloud Shell already has the Google Cloud CLI and can build with
Cloud Build.

## Verification

Manual smoke test:

```bash
gcloud run jobs execute ai-infra-news-briefing --region asia-east1 --wait
```

Pass criteria:

- Cloud Run Job execution exits successfully.
- Gmail Drafts shows a draft with today's `每日简报` subject.
- No email is sent.
