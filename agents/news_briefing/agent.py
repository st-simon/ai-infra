"""
新闻简报 Agent — Phase 1
LangGraph 线性流水线：加载配置 → 抓取 RSS → 过滤 → AI摘要 → 生成简报

用法:
    cd ~/ai-infra
    source .venv/bin/activate
    python agents/news_briefing/agent.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import feedparser
import httpx
import ssl
import yaml
from datetime import datetime, timezone, timedelta
from typing import TypedDict, Any
from langgraph.graph import StateGraph, START, END
from shared.models import chat

# ─── 配置路径 ────────────────────────────────────────────────────────────────

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../../config/news_sources.yaml')

# ─── 状态定义 ─────────────────────────────────────────────────────────────────

class BriefingState(TypedDict):
    config: dict                    # 从 YAML 加载的配置
    raw_items: list[dict]           # 抓取的原始条目
    filtered_items: list[dict]      # 过滤后的条目（按权重分配）
    summaries: dict[str, list[str]] # 每个类别的摘要列表
    briefing: str                   # 最终简报文本

# ─── 节点函数 ─────────────────────────────────────────────────────────────────

def node_load_config(state: BriefingState) -> dict:
    """节点1：加载新闻来源配置"""
    print("  [1/4] 加载配置...")
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    print(f"       已加载 {len(config['categories'])} 个类别")
    return {"config": config}


def node_fetch_rss(state: BriefingState) -> dict:
    """节点2：用 httpx（走系统代理/VPN）抓取 RSS"""
    print("  [2/4] 抓取 RSS 源...")
    config = state["config"]
    categories = config["categories"]
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
                # trust_env=True 走系统代理/VPN
                resp = httpx.get(
                    source["url"],
                    headers=headers,
                    timeout=15.0,
                    follow_redirects=True,
                    trust_env=True,
                )
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)
                count = 0
                for entry in feed.entries[:10]:
                    title = entry.get("title", "").strip()
                    if not title:
                        continue
                    summary = (
                        entry.get("summary", "")
                        or entry.get("description", "")
                        or ""
                    )[:500]
                    all_items.append({
                        "category": cat_key,
                        "category_label": cat_conf["label"],
                        "source_name": source["name"],
                        "priority": source.get("priority", 2),
                        "title": title,
                        "summary": summary,
                        "link": entry.get("link", ""),
                    })
                    count += 1
                print(f"       {source['name']}: {count} 条")
            except Exception as e:
                print(f"       {source['name']}: 失败 ({type(e).__name__})")

    print(f"       共抓取 {len(all_items)} 条原始条目")
    return {"raw_items": all_items}

def node_filter_items(state: BriefingState) -> dict:
    """节点3：按权重和优先级筛选条目"""
    print("  [3/4] 按权重筛选...")
    config = state["config"]
    categories = config["categories"]
    raw = state["raw_items"]

    filtered = []
    for cat_key, cat_conf in categories.items():
        max_items = cat_conf.get("max_items", 6)
        cat_items = [i for i in raw if i["category"] == cat_key]

        # 按 priority 排序（1最高），同优先级保持原顺序
        cat_items.sort(key=lambda x: x["priority"])
        selected = cat_items[:max_items]
        filtered.extend(selected)
        print(f"       {cat_conf['label']}: 选取 {len(selected)} 条")

    return {"filtered_items": filtered}


def node_summarize(state: BriefingState) -> dict:
    """节点4：用 AI 对每条新闻生成中文摘要"""
    print("  [4/4] AI 摘要生成...")
    config = state["config"]
    categories = config["categories"]
    items = state["filtered_items"]
    max_len = config["briefing"].get("summary_length", 150)

    summaries: dict[str, list[str]] = {k: [] for k in categories}

    for item in items:
        cat = item["category"]
        title = item["title"]
        raw_summary = item["summary"]
        source = item["source_name"]

        if not title:
            continue
        prompt = (
            f"/no_think\n"
            f"将以下英文新闻标题直接翻译成中文，只输出译文，末尾加【{source}】，不要解释：\n"
            f"{title}"
        )
        try:
            result = chat("generalist", prompt, num_ctx=2048)
            if "</think>" in result:
                result = result.split("</think>")[-1]
            result = result.strip()
            if result:
                summaries[cat].append(result)
                print(f"       ✓ {title[:40]}...")
            else:
                # AI 返回空，直接用翻译好的标题兜底
                fallback = f"{title[:80]}【{source}】"
                summaries[cat].append(fallback)
                print(f"       ~ 兜底: {title[:40]}...")
        except Exception as e:
            print(f"       ✗ 摘要失败: {e}")
            summaries[cat].append(f"{title}【{source}】")

    return {"summaries": summaries}


def node_generate_briefing(state: BriefingState) -> dict:
    """节点5：组装最终简报"""
    print("\n  组装简报...")
    config = state["config"]
    categories = config["categories"]
    summaries = state["summaries"]
    now = datetime.now(timezone(timedelta(hours=8)))  # 北京时间
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
        lines.append(f"## {cat_conf['label']}（{weight_pct}%）")
        lines.append("")
        for i, s in enumerate(cat_summaries, 1):
            lines.append(f"{i}. {s}")
        lines.append("")

    briefing = "\n".join(lines)
    return {"briefing": briefing}


# ─── 构建 LangGraph 图 ───────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(BriefingState)

    graph.add_node("load_config",        node_load_config)
    graph.add_node("fetch_rss",          node_fetch_rss)
    graph.add_node("filter_items",       node_filter_items)
    graph.add_node("summarize",          node_summarize)
    graph.add_node("generate_briefing",  node_generate_briefing)

    graph.add_edge(START,              "load_config")
    graph.add_edge("load_config",      "fetch_rss")
    graph.add_edge("fetch_rss",        "filter_items")
    graph.add_edge("filter_items",     "summarize")
    graph.add_edge("summarize",        "generate_briefing")
    graph.add_edge("generate_briefing", END)

    return graph.compile()


# ─── 主入口 ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  新闻简报 Agent 启动")
    print("=" * 50)

    graph = build_graph()

    initial_state: BriefingState = {
        "config": {},
        "raw_items": [],
        "filtered_items": [],
        "summaries": {},
        "briefing": "",
    }

    result = graph.invoke(initial_state)
    briefing = result["briefing"]

    # 打印到终端
    print("\n" + "=" * 50)
    print(briefing)
    print("=" * 50)

    # 保存到文件
    log_dir = os.path.join(os.path.dirname(__file__), '../../logs')
    os.makedirs(log_dir, exist_ok=True)
    filename = datetime.now().strftime("%Y%m%d_%H%M") + "_briefing.md"
    out_path = os.path.join(log_dir, filename)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(briefing)
    print(f"\n简报已保存：{out_path}")
