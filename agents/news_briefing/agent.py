"""
新闻简报 Agent — Phase 1
LangGraph 线性流水线：加载配置 → 抓取 RSS → 过滤 → AI翻译 → 生成简报

核心设计决策：
- RSS 抓取用 httpx（trust_env=True，走 VPN 代理）
- 翻译用 coder 模型（qwen2.5-coder:7b），无 thinking 模式，输出干净
- 简报保存到 logs/ 目录

	用法:
	    cd ~/codex-projects/projects/ai-infra
	    source .venv/bin/activate
	    python agents/news_briefing/agent.py
"""

import argparse
import json
import re
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import feedparser
import httpx
import yaml
from datetime import datetime, timezone, timedelta
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from shared.models import chat

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../../config/news_sources.yaml')

# ─── 状态定义 ─────────────────────────────────────────────────────────────────

class BriefingState(TypedDict):
    config: dict
    raw_items: list[dict]
    filtered_items: list[dict]
    summaries: dict
    briefing: str


def _normalize_title(title: str) -> str:
    text = re.sub(r"https?://\S+", "", title.lower())
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff ]+", " ", text)
    words = [w for w in text.split() if len(w) > 2]
    return " ".join(words[:14])


def _dedupe_items(items: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for item in sorted(items, key=lambda x: x.get("priority", 99)):
        key = _normalize_title(item.get("title", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _category_quotas(categories: dict, total_items: int) -> dict[str, int]:
    raw = {}
    for cat_key, cat_conf in categories.items():
        weight = float(cat_conf.get("weight", 0))
        raw[cat_key] = total_items * weight

    quotas = {k: int(v) for k, v in raw.items()}
    remaining = total_items - sum(quotas.values())
    ranked = sorted(raw, key=lambda k: raw[k] - quotas[k], reverse=True)
    for cat_key in ranked[:remaining]:
        quotas[cat_key] += 1
    return quotas


def _select_diverse_items(items: list[dict], limit: int) -> list[dict]:
    by_source: dict[str, list[dict]] = {}
    for item in sorted(items, key=lambda x: x.get("priority", 99)):
        by_source.setdefault(item["source_name"], []).append(item)

    selected = []
    source_names = sorted(
        by_source,
        key=lambda name: by_source[name][0].get("priority", 99),
    )
    while len(selected) < limit and any(by_source.values()):
        for source_name in source_names:
            source_items = by_source[source_name]
            if source_items:
                selected.append(source_items.pop(0))
                if len(selected) >= limit:
                    break
    return selected


def _extract_json_array(text: str) -> list[dict]:
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("model output did not contain a JSON array")
    raw_json = text[start:end + 1]
    raw_json = re.sub(r",\s*([}\]])", r"\1", raw_json)
    return json.loads(raw_json)


def _plain_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _fallback_summary(item: dict) -> dict:
    return {
        "title_zh": _plain_text(item.get("title", "")),
        "summary_zh": _plain_text(item.get("summary", "")) or _plain_text(item.get("title", "")),
        "source": item.get("source_name", ""),
        "link": item.get("link", ""),
    }


def _summarize_category(cat_conf: dict, cat_items: list[dict]) -> list[dict]:
    payload = []
    for idx, item in enumerate(cat_items, 1):
        payload.append({
            "index": idx,
            "title": item.get("title", ""),
            "summary": item.get("summary", "")[:500],
            "source": item.get("source_name", ""),
        })

    prompt = (
        "你是中文新闻简报编辑。请把下列英文新闻整理成 JSON 数组，"
        "每条包含 index、title_zh、summary_zh。"
        "title_zh 是中文标题；summary_zh 用 2-3 句中文总结事实和影响。"
        "不要编造材料中没有的信息，不要输出 Markdown，不要输出 JSON 之外的文字。\n\n"
        f"类别：{cat_conf['label']}\n"
        f"新闻：{json.dumps(payload, ensure_ascii=False)}"
    )

    try:
        result = chat("coder", prompt, num_ctx=4096, temperature=0.2, mode="local_only")
        parsed = _extract_json_array(result)
        by_index = {int(row["index"]): row for row in parsed if "index" in row}
        rows = []
        for idx, item in enumerate(cat_items, 1):
            row = by_index.get(idx, {})
            fallback = _fallback_summary(item)
            rows.append({
                "title_zh": str(row.get("title_zh", "")).strip() or fallback["title_zh"],
                "summary_zh": str(row.get("summary_zh", "")).strip() or fallback["summary_zh"],
                "source": fallback["source"],
                "link": fallback["link"],
            })
        print(f"       ✓ {cat_conf['label']}: {len(rows)} 条")
        return rows
    except Exception as e:
        print(f"       ✗ {cat_conf['label']} 批量失败: {e}")
        return [_fallback_summary(item) for item in cat_items]

# ─── 节点函数 ─────────────────────────────────────────────────────────────────

def node_load_config(state: BriefingState) -> dict:
    print("  [1/4] 加载配置...")
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    print(f"       已加载 {len(config['categories'])} 个类别")
    return {"config": config}


def node_fetch_rss(state: BriefingState) -> dict:
    print("  [2/4] 抓取 RSS 源...")
    config = state["config"]
    categories = config["categories"]
    timeout_seconds = float(config.get("briefing", {}).get("rss_timeout_seconds", 8))
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    all_items = []
    for cat_key, cat_conf in categories.items():
        sources = cat_conf.get("sources", [])
        enabled = [s for s in sources if s.get("enabled", True)]

        for source in enabled:
            try:
                # trust_env=True：走系统 VPN 代理
                resp = httpx.get(
                    source["url"],
                    headers=headers,
                    timeout=timeout_seconds,
                    follow_redirects=True,
                    trust_env=True,
                )
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)
                count = 0
                for entry in feed.entries[:15]:
                    title = entry.get("title", "").strip()
                    if not title:
                        continue
                    # 过滤掉明显的非新闻条目
                    if len(title) < 10:
                        continue
                    all_items.append({
                        "category": cat_key,
                        "category_label": cat_conf["label"],
                        "source_name": source["name"],
                        "priority": source.get("priority", 2),
                        "title": title,
                        "summary": (
                            entry.get("summary", "")
                            or entry.get("description", "")
                            or ""
                        )[:300],
                        "link": entry.get("link", ""),
                    })
                    count += 1
                if count > 0:
                    print(f"       ✓ {source['name']}: {count} 条")
                else:
                    print(f"       - {source['name']}: 0 条")
            except Exception as e:
                print(f"       ✗ {source['name']}: {type(e).__name__}")

    print(f"       共抓取 {len(all_items)} 条原始条目")
    return {"raw_items": all_items}


def node_filter_items(state: BriefingState) -> dict:
    print("  [3/4] 去重并按权重筛选...")
    config = state["config"]
    categories = config["categories"]
    briefing_conf = config.get("briefing", {})
    total_items = int(briefing_conf.get("total_items", 20))
    raw = _dedupe_items(state["raw_items"])
    quotas = _category_quotas(categories, total_items)

    filtered = []
    for cat_key, cat_conf in categories.items():
        max_items = min(int(cat_conf.get("max_items", total_items)), quotas.get(cat_key, 0))
        cat_items = [i for i in raw if i["category"] == cat_key]
        selected = _select_diverse_items(cat_items, max_items)
        filtered.extend(selected)
        print(f"       {cat_conf['label']}: {len(selected)}/{max_items} 条")

    return {"filtered_items": filtered}


def node_translate(state: BriefingState) -> dict:
    """
    用 coder 模型翻译标题。
    coder = qwen2.5-coder:7b，无 thinking 模式，输出稳定干净。
    """
    print("  [4/4] 翻译标题...")
    config = state["config"]
    categories = config["categories"]
    items = state["filtered_items"]

    summaries: dict = {k: [] for k in categories}

    for item in items:
        cat = item["category"]
        title = item["title"]
        source = item["source_name"]

        # 极简 prompt，给 coder 模型
        # 用标题+摘要生成中文概括
        summary = item.get("summary", "")
        if summary:
            prompt = (
                f"Based on this news title and summary, write one informative "
                f"Chinese sentence (do not mention the source name):\n"
                f"Title: {title}\n"
                f"Summary: {summary[:200]}"
            )
        else:
            prompt = f"Translate to Chinese, output only the translation:\n{title}"
        try:
            result = chat("coder", prompt, num_ctx=1024)
            result = result.strip()

            # 清理常见的多余输出
            # 去掉引号包裹
            if result.startswith('"') and result.endswith('"'):
                result = result[1:-1]
            if result.startswith("'") and result.endswith("'"):
                result = result[1:-1]
            # 去掉 "Translation:" 前缀
            for prefix in ["Translation:", "翻译:", "Chinese:", "中文:"]:
                if result.startswith(prefix):
                    result = result[len(prefix):].strip()
            # 只取第一行
            result = result.splitlines()[0].strip()

            if result:
                line = f"{result}【{source}】"
                summaries[cat].append(line)
                print(f"       ✓ {result[:40]}")
            else:
                summaries[cat].append(f"{title}【{source}】")
                print(f"       ~ 兜底: {title[:40]}")

        except Exception as e:
            print(f"       ✗ 失败: {e}")
            summaries[cat].append(f"{title}【{source}】")

    return {"summaries": summaries}


def node_summarize(state: BriefingState) -> dict:
    """按类别批量生成中文标题和 2-3 句中文摘要。"""
    print("  [4/4] 批量生成中文标题和摘要...")
    config = state["config"]
    categories = config["categories"]
    items = state["filtered_items"]

    summaries: dict = {k: [] for k in categories}

    for cat_key, cat_conf in categories.items():
        cat_items = [item for item in items if item["category"] == cat_key]
        if not cat_items:
            continue
        summaries[cat_key].extend(_summarize_category(cat_conf, cat_items))

    return {"summaries": summaries}


def node_generate_briefing(state: BriefingState) -> dict:
    print("\n  组装简报...")
    config = state["config"]
    categories = config["categories"]
    summaries = state["summaries"]
    now = datetime.now(timezone(timedelta(hours=8)))
    date_str = now.strftime("%Y年%m月%d日")

    lines = [
        f"# 每日简报  {date_str}",
        f"生成时间：{now.strftime('%H:%M')} BJT",
        "",
    ]

    for cat_key, cat_conf in categories.items():
        cat_summaries = summaries.get(cat_key, [])
        if not cat_summaries:
            continue
        weight_pct = int(cat_conf["weight"] * 100)
        lines.append(f"## {cat_conf['label']}")
        lines.append("")
        for i, item in enumerate(cat_summaries, 1):
            if isinstance(item, dict):
                lines.append(f"{i}. **{item['title_zh']}**")
                lines.append(f"   {item['summary_zh']}")
                if item.get("link"):
                    lines.append(f"   原文：{item['link']}【{item['source']}】")
                else:
                    lines.append(f"   来源：{item['source']}")
            else:
                lines.append(f"{i}. {item}")
        lines.append("")

    return {"briefing": "\n".join(lines)}


# ─── 构建图 ───────────────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(BriefingState)
    graph.add_node("load_config",       node_load_config)
    graph.add_node("fetch_rss",         node_fetch_rss)
    graph.add_node("filter_items",      node_filter_items)
    graph.add_node("summarize",         node_summarize)
    graph.add_node("generate_briefing", node_generate_briefing)

    graph.add_edge(START,              "load_config")
    graph.add_edge("load_config",      "fetch_rss")
    graph.add_edge("fetch_rss",        "filter_items")
    graph.add_edge("filter_items",     "summarize")
    graph.add_edge("summarize",        "generate_briefing")
    graph.add_edge("generate_briefing", END)

    return graph.compile()


# ─── 主入口 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate the daily news briefing.")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing a log file.")
    args = parser.parse_args()

    print("=" * 50)
    print("  新闻简报 Agent 启动")
    print("=" * 50)

    graph = build_graph()
    result = graph.invoke({
        "config": {}, "raw_items": [], "filtered_items": [],
        "summaries": {}, "briefing": "",
    })

    briefing = result["briefing"]
    print("\n" + "=" * 50)
    print(briefing)
    print("=" * 50)

    if args.dry_run:
        print("\nDry run: 未写入简报文件")
    else:
        log_dir = os.path.join(os.path.dirname(__file__), '../../logs')
        os.makedirs(log_dir, exist_ok=True)
        filename = datetime.now().strftime("%Y%m%d_%H%M") + "_briefing.md"
        out_path = os.path.join(log_dir, filename)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(briefing)
        print(f"\n简报已保存：{out_path}")
