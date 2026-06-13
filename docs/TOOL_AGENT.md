# Tool Agent

Date: 2026-06-13
Scope: Phase 2 skeleton for `agents/tool_agent/agent.py`

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
- Run in `--dry-run` mode without writing files.
- Persist request JSON for later MCP handoff when not in dry-run mode.

## Boundary

The local Python process does not read Gmail, send email, create calendar
events, or modify remote account state.

MCP-backed execution should happen in Codex after the user reviews the planned
action. For example:

1. Local Tool Agent writes a request JSON.
2. Codex reads the request.
3. Codex uses Gmail or Calendar MCP tools to create a draft.
4. User reviews.
5. Sending or calendar creation requires a separate explicit approval.

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

## Next Steps

- Add a reviewed Gmail draft handoff from Tool Agent request JSON.
- Add Calendar MCP once a Codex-accessible connector is available.
- Add a local task-log target before selecting a real task system.
