# Model Policy And Execution Roadmap

Date: 2026-06-10
Scope: `ai-infra`

## Decision

Use a hybrid local-plus-cloud model strategy.

Local models remain the default execution path for frequent, routine, low-cost tasks. Cloud frontier models are reserved for high-value reasoning, long-context synthesis, research reports, and final deliberation synthesis.

Do not hard-code one cloud provider or one cloud model into agent logic. Model choices must stay configurable.

## Role And Mode Model

Separate model role from execution mode.

Roles describe task intent:

- `fast`: high-throughput classification, extraction, and simple transformations
- `general`: ordinary writing, light reasoning, and tool-agent drafting
- `reasoner`: analysis, research, and difficult judgment
- `coder`: code generation, code review support, formatting, and structured output
- `embedding`: vectorization for retrieval and memory

Modes describe cost, privacy, and quality preference:

- `local_only`: use only local models
- `low_cost`: prefer small local models, keep output short
- `auto`: use local first, then stronger configured models only when policy allows
- `quality`: prefer the strongest configured model for the role

## Agent Defaults

| Agent | Stage | Default mode | Notes |
|---|---|---:|---|
| News Briefing local fallback | fetch, filter, summarize, format | `local_only` | Mac launchd/manual runs remain local-first. |
| News Briefing cloud production | fetch, filter, summarize, format | `quality` | Cloud Run uses a configured cloud model so it does not depend on local Ollama. |
| Tool Agent | calendar and email drafting | `local_only` or `auto` | Cloud use requires explicit privacy and authorization boundaries. |
| Research | ingest, clean, embed, retrieve | `local_only` | Keep source collection and indexing cheap and private. |
| Research | deep analysis and report generation | `quality` | Use cloud frontier models when configured. |
| Deliberation | initial proposals and critiques | `auto` | Local models can provide cheaper multiple perspectives. |
| Deliberation | final synthesis / judge | `quality` | Final synthesizer should allow a cloud frontier model. |

## Implementation Roadmap

1. Record this model strategy and execution order in project docs.
2. Close Phase 1 infrastructure:
   - rebuild `.venv`
   - add dependency management
   - add `.gitignore`
   - confirm runtime commands and log behavior
3. Inventory locally installed models and run task-specific benchmarks.
4. Implement the `shared/models.py` strategy layer:
   - role-based routing
   - mode-based routing
   - provider abstraction
   - no cloud provider hard-coded in agents
5. Implement News Briefing v2:
   - Chinese title
   - 2-3 sentence Chinese summary
   - original link
   - dedupe
   - category quota
   - batch summarization
6. Implement Research cloud analysis nodes.
7. Implement Deliberation final cloud synthesizer.

## Local Model Evaluation Plan

Evaluate local models against project tasks before replacing defaults.

Benchmark tasks:

- Chinese news title translation
- 2-3 sentence Chinese news summary
- politics / finance / tech / crypto classification
- duplicate event detection across sources
- crypto regulation summary
- industrial AI technical-route analysis
- long-context synthesis
- Markdown and JSON format reliability
- latency, memory pressure, and failure rate

Selection rule:

- Replace a default model only when a candidate clearly improves quality, latency, memory use, or output reliability on project tasks.
- Treat unofficial community model names and third-party quantizations as candidates, not defaults, until verified.
- Keep at least one stable fallback model per role.
