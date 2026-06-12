"""Run lightweight local Ollama benchmarks for ai-infra model roles."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import httpx

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODELS = [
    "qwen35-fast:latest",
    "qwen3.5:9b",
    "qwen2.5-coder:7b",
]

TASKS = [
    {
        "id": "news_title_translation",
        "prompt": "Translate to Chinese, output only the title: Fed signals caution as markets await inflation data",
    },
    {
        "id": "news_summary",
        "prompt": (
            "用 2-3 句中文总结这条新闻："
            "Title: UK regulator moves to allow mutual funds limited exposure to crypto ETNs. "
            "Summary: The proposal would permit up to 10% exposure while adding risk controls."
        ),
    },
    {
        "id": "category_classification",
        "prompt": (
            "Classify this news into one category: politics, finance, tech, crypto. "
            "Output only the category. News: Bitcoin falls as ETF outflows accelerate."
        ),
    },
    {
        "id": "structured_markdown",
        "prompt": (
            "Return valid JSON only with keys title_zh and summary_zh for this news: "
            "OpenAI launches new tools for enterprise AI agents."
        ),
    },
]


def run_prompt(model: str, prompt: str) -> dict:
    started = time.perf_counter()
    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": f"/no_think\n{prompt}"}],
            "stream": False,
            "options": {"temperature": 0.2, "num_ctx": 2048},
        },
        timeout=180.0,
        trust_env=False,
    )
    elapsed = time.perf_counter() - started
    response.raise_for_status()
    content = response.json().get("message", {}).get("content", "").strip()
    return {
        "seconds": round(elapsed, 2),
        "chars": len(content),
        "output": content,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark local Ollama models.")
    parser.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    parser.add_argument("--quick", action="store_true", help="Run only the first two tasks.")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    tasks = TASKS[:2] if args.quick else TASKS
    results = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "tasks": [task["id"] for task in tasks],
        "models": {},
    }

    for model in args.models:
        model_results = {}
        for task in tasks:
            try:
                model_results[task["id"]] = run_prompt(model, task["prompt"])
            except Exception as exc:
                model_results[task["id"]] = {"error": f"{type(exc).__name__}: {exc}"}
        results["models"][model] = model_results

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
