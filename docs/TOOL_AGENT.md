# Tool Agent

Date: 2026-06-13
Scope: Phase 2 local planner, reviewed Gmail draft handoff, and local Calendar handoff

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
  fields from labeled natural language requests.
- Run in `--dry-run` mode without writing files.
- Persist request JSON for later MCP handoff when not in dry-run mode.
- Validate reviewed `email_draft` JSON and prepare Gmail MCP
  `create_draft` arguments.
- Validate reviewed `calendar_event` JSON locally, while clearly blocking real
  event creation until Calendar MCP is available.

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

Calendar support is currently local-only because no Google Calendar MCP tool is
available in this Codex session. The Tool Agent can still prepare and validate
Calendar-shaped requests so the connector can be attached later without changing
the local request contract.

```bash
.venv/bin/python agents/tool_agent/agent.py \
  --calendar-event-handoff logs/tool_agent_requests/<request>.json \
  --reviewed \
  --title "Customer visit" \
  --time-window "next Wednesday afternoon"
```

Expected result:

- `mode` is `calendar_event_handoff`
- `status` is `blocked_missing_connector`
- `safety.creates_event` is `false`

For safety, handoff is rejected unless:

- `--reviewed` is present
- request `intent` is `calendar_event`
- request `connector` is `calendar_mcp`
- `requires_confirmation` is `true`
- `auto_execute` is `false`
- reviewed `title` and `time_window` are non-empty

## Next Steps

- Add Calendar MCP once a Codex-accessible connector is available.
- Add a local task-log target before selecting a real task system.
