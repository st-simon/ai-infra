# Decisions

## 2026-06-07: Continue Project, Do Not Rebuild

Decision: continue from the existing codebase and harden it around the daily news workflow.

Rationale:

- The current project already has a workable Phase 1 news agent, model gateway, RSS configuration, and scheduler draft.
- The architecture is small enough for Codex to take over safely.
- Rebuilding would spend effort on recreating the same basic shape instead of improving reliability and output quality.

Consequences:

- Preserve `LangGraph`, `shared/models.py`, Ollama, and YAML source configuration.
- Treat environment reproducibility, dependency files, model profiles, and `.gitignore` cleanup as the next foundation work.
- Delay Research Agent, Tool Agent, and Deliberation Agent until daily news is reliable.

## 2026-06-07: Daily News Is The Primary Product

Decision: make daily news the first product-grade workflow.

Required output per item:

- Chinese title
- 2-3 sentence Chinese summary
- Original link

Rationale:

- The user wants fast and broad daily coverage first.
- Research and personal assistant workflows are useful but lower priority.

Consequences:

- News Agent v2 should focus on breadth, dedupe, category quotas, source health, batch summarization, and stable Markdown.
- Existing TODO status should be interpreted through this priority.

## 2026-06-07: Local-First, Cloud-Acceptable Model Policy

Decision: optimize for the local Mac first, but allow cloud APIs when local model quality or latency is not enough.

Hardware baseline:

- MacBook Pro M4
- 16 GB unified memory
- 10 CPU cores
- 10 GPU cores

Model policy:

- Use 4B-9B local models as default.
- Use 14B only as optional quality mode.
- Avoid 27B+ as a normal local path.
- Load only one large model at a time.
- Keep model names in configuration instead of agent logic.

Consequences:

- `qwen3.5:9b` remains a reasonable local default.
- `qwen2.5-coder:7b` can remain for small local development.
- Add a small `fast` role for high-throughput translation/classification.
- Add an embedding role only when Research Agent begins.

## 2026-06-10: Hybrid Model Strategy And Execution Order

Decision: use a configurable hybrid local-plus-cloud strategy instead of binding the project to a single cloud provider or a single model name.

Execution model:

- Separate model role from execution mode.
- Roles: `fast`, `general`, `reasoner`, `coder`, `embedding`.
- Modes: `local_only`, `low_cost`, `auto`, `quality`.
- Keep provider and model selection in configuration, not agent logic.

Agent policy:

- News Briefing stays local-first and should not require cloud models for daily operation.
- Research uses local models for ingest, cleaning, embedding, and retrieval; deep analysis and reports may use `quality` mode.
- Deliberation may use local models for initial proposal and critique generation, but the final synthesizer should support `quality` mode with a cloud frontier model.

Implementation order:

1. Record model strategy in project docs.
2. Close Phase 1 infrastructure: `.venv`, dependency file, `.gitignore`, runtime/log behavior.
3. Inventory installed local models and benchmark against project tasks.
4. Implement `shared/models.py` role/mode strategy layer.
5. Implement News Briefing v2.
6. Add Research cloud analysis nodes.
7. Add Deliberation final cloud synthesizer.

Reference: `docs/MODEL_POLICY.md`.

## 2026-06-13: Tool Agent Starts With MCP Handoff Requests

Decision: start Phase 2 with a local request planner instead of direct Gmail or
Calendar account actions.

Rationale:

- Codex MCP connectors own Gmail and future Calendar account access.
- Local Python code should not store connector authorization material or perform
  remote account mutations in the background.
- Tool-agent actions need a review boundary before sending email, creating
  calendar events, deleting messages, or changing labels.

Consequences:

- `agents/tool_agent/agent.py` classifies natural-language requests and writes
  structured handoff JSON under `logs/tool_agent_requests/`.
- Reviewed `email_draft` request JSON can be validated with
  `--gmail-draft-handoff ... --reviewed` to produce Gmail MCP `create_draft`
  arguments; it never sends email.
- Gmail and Calendar execution happens later through Codex MCP tools after user
  review.
- Phase 2 can progress while Phase 1 launchd delivery is still being observed.

Reference: `docs/TOOL_AGENT.md`.

## 2026-06-13: Tool Agent Gmail Send Requires Draft Review First

Decision: allow Gmail sending only as a second step after the user has reviewed
an MCP-created draft and explicitly confirmed sending that existing draft.

Consequences:

- The verified flow is local request JSON -> reviewed handoff -> Gmail draft ->
  user review -> explicit send confirmation -> recipient receipt.
- Real Gmail draft and send actions are performed by Codex Gmail MCP, not by the
  local Python process.
- Tracked project records should not include personal recipient addresses; those
  remain in ignored local logs and Gmail itself.
- Future Tool Agent email improvements should reduce review friction, but not
  remove the draft-before-send boundary.

## 2026-06-13: Calendar Phase 2A Is Local-Only Until MCP Exists

Decision: add Calendar request shaping and reviewed handoff validation before
real Calendar account access is available.

Consequences:

- `calendar_event` requests can extract `title`, `time_window`, `attendees`, and
  `description` from labeled natural language.
- Reviewed Calendar handoff returns `blocked_missing_connector` and
  `safety.creates_event=false`.
- Real event creation stays blocked until a Codex-accessible Google Calendar MCP
  connector exists and the user separately approves creating an event.

## 2026-06-13: Google Calendar MCP Connected

Decision: install the Google Calendar plugin and connect Tool Agent reviewed
calendar handoff to Google Calendar MCP `create_event` arguments.

Consequences:

- Calendar MCP profile verification succeeded for `Jun Xia
  <junexia2018@gmail.com>`.
- `calendar_event` handoff requires reviewed `title`, `start_time`, and
  `end_time`; start/end must be RFC3339 datetimes with `Z` or an explicit UTC
  offset.
- Local Python still does not create events. It emits MCP arguments, and Codex
  only calls Google Calendar MCP after explicit user confirmation.
