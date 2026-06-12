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
