# Local Model Evaluation

Date: 2026-06-10
Scope: 16 GB Mac local model choices for `ai-infra`

## Installed Models

Observed with `ollama list`:

| Model | Size | Current role |
|---|---:|---|
| `qwen35-fast:latest` | 6.6 GB | current `reasoner` / `generalist` default |
| `qwen3.5:9b` | 6.6 GB | available local general model |
| `qwen2.5-coder:7b` | 4.7 GB | current `coder` default |

## Current Recommendation

Do not replace defaults immediately.

The project should first run task-specific benchmarks against the installed models, then compare any new candidate on the same prompts and runtime constraints.

Near-term default posture:

- Keep `qwen2.5-coder:7b` for News Briefing v2 formatting, translation, and short summaries.
- Keep `qwen35-fast` or `qwen3.5:9b` available for local reasoning until benchmarks show a better default.
- Treat 12B-14B local models as optional quality candidates, not mandatory defaults.
- Treat 30B+ or MoE models as experiments on this 16 GB machine unless latency and memory are proven acceptable.

## Candidate Directions

Candidate models should be judged by project tasks, not leaderboard scores alone.

Worth evaluating:

- Gemma 4 12B class models, because Google positions Gemma 4 12B as laptop-ready for 16 GB VRAM or unified memory.
- Qwen3 small and medium dense models, if available in a stable local runtime.
- Qwen3 MoE GGUF variants, such as 30B-A3B, only as quality experiments because total memory footprint can still matter even when active parameters are smaller.
- New coder-specialized Qwen variants only if they improve structured output reliability over `qwen2.5-coder:7b`.

Avoid making unofficial community names the default until source, license, quantization quality, and runtime stability are verified.

## Benchmark Tasks

Run every candidate through the same prompts:

1. Chinese title translation from English RSS titles.
2. 2-3 sentence Chinese summaries from title plus RSS description.
3. Politics / finance / tech / crypto classification.
4. Duplicate event detection across similar article titles.
5. Crypto regulation summary.
6. Industrial AI technical-route analysis.
7. Long-context synthesis from a multi-section source document.
8. Markdown and JSON format compliance.
9. Latency and memory pressure on the local Mac.

## Acceptance Criteria

Replace a role default only when the candidate shows a clear advantage in at least one of:

- output quality
- structured format reliability
- latency
- memory use
- lower failure rate

Keep a stable fallback for each role even after a new model is adopted.

## Quick Baseline Result

Recorded in `docs/local_model_benchmark_quick.json`.

Initial quick baseline on `qwen2.5-coder:7b`:

| Task | Seconds | Result |
|---|---:|---|
| Chinese title translation | 3.53 | Clean Chinese title output |
| 2-3 sentence news summary | 2.19 | Clean concise Chinese summary |

The full multi-model benchmark was stopped because loading and switching all installed models took too long for a quick validation pass. Future benchmark runs should start with one model at a time, then expand only when needed.

## Source Notes

- Google announced Gemma 4 12B on 2026-06-03 and describes it as suitable for laptops with 16 GB VRAM or unified memory.
- Qwen's official Qwen3-30B-A3B-GGUF model card lists 30.5B total parameters, 3.3B activated parameters, GGUF support, Ollama usage, and 32K native context.
