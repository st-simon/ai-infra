# AI Infra Audit And Rebuild Plan

Date: 2026-06-07
Scope: `/Users/junxia/codex-projects/projects/ai-infra`

## Executive Decision

Codex should continue this project instead of rebuilding from scratch.

The current codebase is a small but workable prototype: it already has a news briefing agent, an Ollama abstraction, RSS source configuration, and a scheduler draft. The right next move is to harden the project around the first real product goal, not replace the architecture.

## Product Priority

Primary goal: daily news.

The briefing should optimize for fast and broad coverage. Each news item should include:

- A Chinese title
- A 2-3 sentence Chinese summary
- The original link

Research agents, tool agents, and deliberation agents remain useful, but they should not delay the daily news workflow.

## Local Hardware Constraint

Machine baseline:

- MacBook Pro M4
- 16 GB unified memory
- 10 CPU cores
- 10 GPU cores
- macOS 15.0

Design rule: local-first is preferred, but local-only is not mandatory. The system may use cloud APIs when quality, reliability, or latency require it.

Practical model ceiling:

- Default local models should stay around 4B-9B.
- 14B can be a quality mode when memory is available.
- 27B+ should not be treated as the normal local path on this machine.
- Only one large model should be loaded at a time.

## Current Findings

Keep:

- LangGraph per-agent structure
- `shared/models.py` as the model gateway
- Ollama for local model serving
- RSS sources in YAML
- Markdown output for the first delivery surface

Fix before expanding:

- Rebuild `.venv`; current pip entry points still reference an old path.
- Add dependency management through `requirements.txt` or `pyproject.toml`.
- Add or repair `.gitignore` for `.DS_Store`, `__pycache__`, runtime logs, and local env files.
- Align README, TODO, and AGENTS status with actual code.
- Make source health observable, because some RSS feeds fail by network, paywall, or anti-bot rules.

## Model Strategy

Current installed models:

- `qwen35-fast`
- `qwen3.5:9b`
- `qwen2.5-coder:7b`

Recommended roles:

- `fast`: small local model, ideally 4B class, for title translation, classification, and JSON formatting.
- `general`: `qwen3.5:9b` for normal news summarization and daily briefing assembly.
- `reasoner`: `qwen3.5:9b` initially; optional 14B trial only after benchmark.
- `coder`: keep `qwen2.5-coder:7b` for small local development tasks.
- `embedding`: add `mxbai-embed-large` or another small embedding model when Research Agent begins.

Model policy:

- Do not hard-code model names directly in agent logic.
- Put model profiles in configuration.
- Benchmark any new model against the actual daily news workload before changing defaults.
- Prefer throughput and stability over maximum benchmark score.

## News Agent Target Architecture

Target pipeline:

```text
load_config
  -> fetch_sources
  -> normalize_items
  -> dedupe_events
  -> rank_and_quota
  -> batch_summarize
  -> validate_output
  -> generate_markdown
  -> persist_and_notify
```

Required behavior:

- Maintain category balance: politics 30%, finance 30%, tech 25%, crypto 15%.
- Select enough items for broad daily coverage.
- Deduplicate same-event reports across sources.
- Prefer sources by priority, but keep source diversity.
- Summarize in batches to reduce local model overhead.
- Preserve source link per item.
- Record failed sources and reason class.
- Produce deterministic Markdown structure.

## Delivery Plan

Phase A: project hardening

- Apply the workspace `project-intake` skill before implementation.
- Rebuild environment and dependency files.
- Add `.gitignore`.
- Add model profile config.
- Add smoke test or dry-run mode that does not write a briefing.

Phase B: daily news v2

- Implement event dedupe.
- Implement quota-based ranking.
- Implement title plus 2-3 sentence summary plus link output.
- Add batch model calls and retry handling.
- Add source health report.

Phase C: delivery and scheduling

- Keep APScheduler only if the Mac is expected to stay awake.
- Otherwise prefer launchd or a lightweight manual command first.
- Add optional cloud model fallback for higher-quality summaries.
- Add optional email or folder export after the briefing format is stable.

Phase D: later agents

- Discuss Research Agent separately.
- Treat crypto and industrial AI research as likely hybrid local/cloud workflows.
- Do not build Gmail/Calendar automation until privacy boundaries and permission model are explicit.

## Open Follow-Up Questions

- What time should the daily briefing be ready?
- How many total items should the daily briefing contain?
- Should each source link be shown inline, footnoted, or as a separate line?
- Should cloud API fallback be automatic or manually enabled?
- Should logs be retained locally forever, rotated monthly, or archived by topic?
