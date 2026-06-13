"""Tool Agent Phase 2 skeleton.

The local process plans tool requests only. Real Gmail and Calendar actions stay
behind MCP connectors and require an explicit confirmation step.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUEST_DIR = PROJECT_ROOT / "logs" / "tool_agent_requests"


class ToolAgentState(TypedDict):
    user_request: str
    dry_run: bool
    intent: str
    action: dict
    request_path: str


def _now_bjt() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def classify_intent(text: str) -> str:
    lowered = text.lower()
    email_keywords = ("gmail", "email", "mail", "邮件", "草稿", "回复", "转发", "简报")
    calendar_keywords = ("calendar", "meeting", "schedule", "日程", "会议", "拜访", "安排")
    task_keywords = ("todo", "task", "remind", "提醒", "待办", "任务", "跟进")

    if any(keyword in lowered for keyword in email_keywords):
        return "email_draft"
    if any(keyword in lowered for keyword in calendar_keywords):
        return "calendar_event"
    if any(keyword in lowered for keyword in task_keywords):
        return "task_note"
    return "clarification_needed"


def build_action(intent: str, user_request: str) -> dict:
    base = {
        "schema_version": 1,
        "agent": "tool_agent",
        "created_at": _now_bjt().isoformat(timespec="seconds"),
        "intent": intent,
        "user_request": user_request,
        "requires_confirmation": True,
        "auto_execute": False,
    }

    if intent == "email_draft":
        return {
            **base,
            "connector": "gmail_mcp",
            "operation": "create_or_update_draft",
            "fields": {
                "to": "",
                "subject": "",
                "body": user_request,
            },
            "notes": "Prepare a Gmail draft only. Do not send without explicit user approval.",
        }
    if intent == "calendar_event":
        return {
            **base,
            "connector": "calendar_mcp",
            "operation": "create_event_draft",
            "fields": {
                "title": "",
                "time_window": "",
                "attendees": [],
                "description": user_request,
            },
            "notes": "Prepare a calendar event draft only. Do not create it without explicit user approval.",
        }
    if intent == "task_note":
        return {
            **base,
            "connector": "local_task_log",
            "operation": "record_task_candidate",
            "fields": {
                "title": user_request,
                "due": "",
                "context": "",
            },
            "notes": "Record as a local task candidate until a task system is selected.",
        }
    return {
        **base,
        "connector": "none",
        "operation": "ask_clarifying_question",
        "fields": {
            "question": "Please clarify whether this is an email, calendar, or task request.",
        },
        "notes": "No external action should be taken.",
    }


def node_classify(state: ToolAgentState) -> dict:
    return {"intent": classify_intent(state["user_request"])}


def node_plan(state: ToolAgentState) -> dict:
    return {"action": build_action(state["intent"], state["user_request"])}


def node_persist(state: ToolAgentState) -> dict:
    if state["dry_run"]:
        return {"request_path": ""}

    REQUEST_DIR.mkdir(parents=True, exist_ok=True)
    stem = _now_bjt().strftime("%Y%m%d_%H%M%S") + f"_{state['intent']}"
    request_path = REQUEST_DIR / f"{stem}.json"
    request_path.write_text(
        json.dumps(state["action"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"request_path": str(request_path)}


def build_graph():
    graph = StateGraph(ToolAgentState)
    graph.add_node("classify", node_classify)
    graph.add_node("plan", node_plan)
    graph.add_node("persist", node_persist)

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "plan")
    graph.add_edge("plan", "persist")
    graph.add_edge("persist", END)
    return graph.compile()


def run(user_request: str, *, dry_run: bool = False) -> ToolAgentState:
    graph = build_graph()
    return graph.invoke({
        "user_request": user_request,
        "dry_run": dry_run,
        "intent": "",
        "action": {},
        "request_path": "",
    })


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan a tool-agent request.")
    parser.add_argument("request", nargs="+", help="Natural language tool request.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write request files.")
    args = parser.parse_args()

    result = run(" ".join(args.request), dry_run=args.dry_run)
    print(json.dumps({
        "intent": result["intent"],
        "dry_run": result["dry_run"],
        "request_path": result["request_path"],
        "action": result["action"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
