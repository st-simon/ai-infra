# Tool Agent

Date: 2026-06-13
Scope: Phase 2 local planner, reviewed Gmail draft handoff, and Calendar MCP handoff

## Decision

Start Phase 2 with a local planning agent, not direct account actions.

The Tool Agent turns a natural-language request into a structured request file
under `logs/tool_agent_requests/`. Real Gmail and Calendar actions stay behind
Codex MCP connectors and require explicit user confirmation.

## Current Capabilities

- Classify a request as:
  - `email_draft`
  - `calendar_event`
  - `task_note`
  - `clarification_needed`
- Build a structured action payload.
- Extract basic Gmail `to`, `subject`, and `body` fields from labeled natural
  language requests.
- Extract basic Calendar `title`, `time_window`, `attendees`, and `description`
  fields from labeled natural language requests, plus optional
  `reminder_minutes`.
- Extract basic local task `title`, `due`, and `context` fields from labeled
  natural language requests.
- Run in `--dry-run` mode without writing files.
- Persist request JSON for later MCP handoff when not in dry-run mode.
- Persist local `task_note` records under `logs/tool_tasks/` when not in
  dry-run mode.
- Validate reviewed `email_draft` JSON and prepare Gmail MCP
  `create_draft` arguments.
- Validate reviewed `calendar_event` JSON and prepare Google Calendar MCP
  `create_event` arguments when exact start/end datetimes are provided.

## Boundary

The local Python process does not read Gmail, send email, create calendar
events, or modify remote account state.

MCP-backed execution should happen in Codex after the user reviews the planned
action. For example:

1. Local Tool Agent writes a request JSON.
2. Codex reads the request.
3. Codex validates the reviewed request with `--gmail-draft-handoff`.
4. Codex uses Gmail MCP tools to create a Gmail draft.
5. User reviews.
6. Sending or calendar creation requires a separate explicit approval.

## Gmail Draft Handoff

The handoff command validates a Tool Agent request and prints the exact Gmail
MCP `create_draft` arguments. It does not send email and does not call Gmail
from the local Python process.

```bash
.venv/bin/python agents/tool_agent/agent.py \
  --gmail-draft-handoff logs/tool_agent_requests/<request>.json \
  --reviewed \
  --to person@example.com \
  --subject "Reviewed subject"
```

Expected result:

- `mode` is `gmail_draft_handoff`
- `status` is `ready_for_mcp`
- `mcp_tool` is `mcp__codex_apps__gmail._create_draft`
- `safety.sends_email` is `false`

Codex then passes `arguments` to Gmail MCP `_create_draft`. Do not use
`_send_draft` unless the user separately approves sending.

For safety, handoff is rejected unless:

- `--reviewed` is present
- request `intent` is `email_draft`
- request `connector` is `gmail_mcp`
- `requires_confirmation` is `true`
- `auto_execute` is `false`
- reviewed `to`, `subject`, and `body` are non-empty

## Smoke Test

```bash
cd /Users/junxia/codex-projects/projects/ai-infra
.venv/bin/python agents/tool_agent/agent.py --dry-run "请帮我草拟一封邮件，确认下周三会议"
```

Expected result:

- `intent` is `email_draft`
- `dry_run` is `true`
- `request_path` is empty
- no Gmail or Calendar action is taken

## Verified Gmail Send Flow

On 2026-06-13, the Tool Agent Gmail path was verified end to end with a real
external recipient:

1. Local request JSON was generated under `logs/tool_agent_requests/`.
2. The request was reviewed and converted to Gmail MCP `create_draft`
   arguments.
3. Gmail MCP created a draft.
4. The user reviewed the draft in Gmail.
5. After explicit confirmation, Gmail MCP sent the existing draft.
6. The recipient confirmed receipt.

This verification does not change the default safety boundary: future sends
still require explicit user approval after draft review.

## Calendar Event Handoff

Google Calendar MCP is connected and profile-verified for
`Jun Xia <junexia2018@gmail.com>`. The local Python process still does not
create events directly; it validates reviewed request JSON and prints the exact
Google Calendar MCP `create_event` arguments.

```bash
.venv/bin/python agents/tool_agent/agent.py \
  --calendar-event-handoff logs/tool_agent_requests/<request>.json \
  --reviewed \
  --title "Customer visit" \
  --start-time "2026-06-17T14:00:00+08:00" \
  --end-time "2026-06-17T15:00:00+08:00" \
  --timezone "Asia/Shanghai" \
  --reminder-minutes 4320
```

Expected result:

- `mode` is `calendar_event_handoff`
- `status` is `ready_for_mcp`
- `mcp_tool` is `mcp__codex_apps__google_calendar._create_event`
- `safety.creates_event` is `false`

For safety, handoff is rejected unless:

- `--reviewed` is present
- request `intent` is `calendar_event`
- request `connector` is `calendar_mcp`
- `requires_confirmation` is `true`
- `auto_execute` is `false`
- reviewed `title`, `start_time`, and `end_time` are non-empty
- `start_time` and `end_time` include date and time. If they omit `Z` or a UTC
  offset, Tool Agent interprets them in the connected calendar display timezone
  (`America/New_York` as currently verified).

When `reminder_minutes` is present, the handoff emits a Google Calendar popup
reminder override. Reminder offsets apply to the connected calendar user's
event reminders; attendee invitations require attendee email addresses.

Timezone policy: use the connected Google Calendar display timezone by default;
only override it when the user explicitly names another timezone such as
`Asia/Shanghai` or provides datetimes with explicit offsets.

## Local Task Log

Task requests stay local until a real task system is selected. A non-dry-run
`task_note` writes two local artifacts:

- `logs/tool_agent_requests/<timestamp>_task_note.json`
- `logs/tool_tasks/task_<timestamp>.json`

Task records include:

- `task_id`
- `status`, initially `planned`
- `title`
- `due`
- `context`
- `source_request_path`

Example:

```bash
.venv/bin/python agents/tool_agent/agent.py \
  "任务：准备会议讲稿 截止：2026-06-20 上下文：AI应用研讨会"
```

No Gmail, Calendar, or external task-system action is taken.

List local tasks:

```bash
.venv/bin/python agents/tool_agent/agent.py --list-tasks
```

Filter by status:

```bash
.venv/bin/python agents/tool_agent/agent.py --list-tasks --task-status planned
```

Search text and due dates:

```bash
.venv/bin/python agents/tool_agent/agent.py \
  --list-tasks \
  --task-query seminar \
  --due-after 2026-06-01 \
  --due-before 2026-06-30
```

Update status:

```bash
.venv/bin/python agents/tool_agent/agent.py \
  --update-task-status task_20260613T2035001234560800 \
  --new-status done
```

Supported statuses:

- `planned`
- `in_progress`
- `done`
- `blocked`
- `canceled`

## Next Steps

- Exercise the Calendar path with a real reviewed event, first by creating a
  draft-equivalent request JSON and then by explicitly approving MCP event
  creation.
- Decide whether local tasks should stay file-based or graduate to a richer
  task store after real usage.
