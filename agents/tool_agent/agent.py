"""Tool Agent Phase 2 skeleton.

The local process plans tool requests only. Real Gmail and Calendar actions stay
behind MCP connectors and require an explicit confirmation step.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUEST_DIR = PROJECT_ROOT / "logs" / "tool_agent_requests"
FIELD_LABELS = (
    "收件人",
    "recipient",
    "to",
    "主题",
    "subject",
    "正文",
    "body",
    "内容",
    "content",
    "标题",
    "title",
    "时间",
    "时间窗口",
    "time",
    "time_window",
    "when",
    "开始",
    "开始时间",
    "start",
    "start_time",
    "结束",
    "结束时间",
    "end",
    "end_time",
    "时区",
    "timezone",
    "timezone_str",
    "地点",
    "location",
    "日历",
    "calendar",
    "calendar_id",
    "参会人",
    "参与人",
    "attendees",
    "attendee",
    "描述",
    "description",
)


class HandoffValidationError(ValueError):
    """Raised when a local request is not safe to hand to an MCP connector."""


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


def _extract_labeled_value(text: str, labels: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    next_pattern = "|".join(re.escape(label) for label in FIELD_LABELS)
    pattern = re.compile(
        rf"(?:{label_pattern})\s*[：:]\s*(.*?)(?=\s*(?:{next_pattern})\s*[：:]|$)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return ""
    return match.group(1).strip(" \n\t，,;；")


def extract_email_fields(user_request: str) -> dict[str, str]:
    return {
        "to": _extract_labeled_value(user_request, ("收件人", "recipient", "to")),
        "subject": _extract_labeled_value(user_request, ("主题", "subject")),
        "body": _extract_labeled_value(user_request, ("正文", "body", "内容", "content")),
    }


def _split_attendees(value: Any) -> list[str]:
    if isinstance(value, list):
        candidates = value
    else:
        candidates = re.split(r"[,，;；、\n]+", str(value or ""))
    return [str(candidate).strip() for candidate in candidates if str(candidate).strip()]


def extract_calendar_fields(user_request: str) -> dict[str, Any]:
    return {
        "title": _extract_labeled_value(user_request, ("标题", "主题", "title", "subject")),
        "time_window": _extract_labeled_value(
            user_request,
            ("时间窗口", "时间", "time_window", "time", "when"),
        ),
        "start_time": _extract_labeled_value(
            user_request,
            ("开始时间", "开始", "start_time", "start"),
        ),
        "end_time": _extract_labeled_value(
            user_request,
            ("结束时间", "结束", "end_time", "end"),
        ),
        "attendees": _split_attendees(
            _extract_labeled_value(
                user_request,
                ("参会人", "参与人", "attendees", "attendee"),
            )
        ),
        "timezone_str": _extract_labeled_value(
            user_request,
            ("时区", "timezone_str", "timezone"),
        ),
        "calendar_id": _extract_labeled_value(
            user_request,
            ("日历", "calendar_id", "calendar"),
        ),
        "location": _extract_labeled_value(user_request, ("地点", "location")),
        "description": _extract_labeled_value(
            user_request,
            ("描述", "description", "内容", "content", "正文", "body"),
        ),
    }


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
        email_fields = extract_email_fields(user_request)
        return {
            **base,
            "connector": "gmail_mcp",
            "operation": "create_or_update_draft",
            "fields": {
                "to": email_fields["to"],
                "subject": email_fields["subject"],
                "body": email_fields["body"] or user_request,
            },
            "notes": "Prepare a Gmail draft only. Do not send without explicit user approval.",
        }
    if intent == "calendar_event":
        calendar_fields = extract_calendar_fields(user_request)
        return {
            **base,
            "connector": "calendar_mcp",
            "operation": "create_event_draft",
            "fields": {
                "title": calendar_fields["title"],
                "time_window": calendar_fields["time_window"],
                "start_time": calendar_fields["start_time"],
                "end_time": calendar_fields["end_time"],
                "attendees": calendar_fields["attendees"],
                "timezone_str": calendar_fields["timezone_str"],
                "calendar_id": calendar_fields["calendar_id"],
                "location": calendar_fields["location"],
                "description": calendar_fields["description"] or user_request,
            },
            "notes": (
                "Prepare a calendar event draft only. "
                "Do not create it without explicit user approval."
            ),
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


def load_request(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HandoffValidationError(f"Request file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise HandoffValidationError(f"Request file is not valid JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise HandoffValidationError("Request file must contain a JSON object.")
    return payload


def _non_empty(value: Any) -> str:
    return str(value or "").strip()


def _is_rfc3339_datetime(value: str) -> bool:
    if not re.search(r"(Z|[+-]\d{2}:\d{2})$", value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return "T" in value


def prepare_gmail_draft_handoff(
    action: dict[str, Any],
    *,
    reviewed: bool,
    source_path: Path | None = None,
    overrides: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    if not reviewed:
        raise HandoffValidationError("Gmail draft handoff requires --reviewed.")

    if action.get("schema_version") != 1:
        raise HandoffValidationError("Only schema_version=1 tool-agent requests are supported.")
    if action.get("agent") != "tool_agent":
        raise HandoffValidationError("Request must come from tool_agent.")
    if action.get("intent") != "email_draft":
        raise HandoffValidationError("Only email_draft requests can create Gmail drafts.")
    if action.get("connector") != "gmail_mcp":
        raise HandoffValidationError("Email draft request must target gmail_mcp.")
    if action.get("requires_confirmation") is not True:
        raise HandoffValidationError("requires_confirmation must be true.")
    if action.get("auto_execute") is not False:
        raise HandoffValidationError("auto_execute must be false for Gmail draft handoff.")

    operation = action.get("operation")
    if operation not in {"create_draft", "create_or_update_draft"}:
        raise HandoffValidationError("Unsupported Gmail draft operation.")

    fields = dict(action.get("fields") or {})
    for key, value in (overrides or {}).items():
        if value is not None:
            fields[key] = value

    args: dict[str, Any] = {
        "to": _non_empty(fields.get("to")),
        "subject": _non_empty(fields.get("subject")),
        "body": _non_empty(fields.get("body")),
        "content_type": _non_empty(fields.get("content_type")) or "text/markdown",
    }

    for optional_key in (
        "cc",
        "bcc",
        "html_body",
        "body_file",
        "attachment_files",
        "reply_message_id",
    ):
        value = fields.get(optional_key)
        if _non_empty(value):
            args[optional_key] = value

    missing = [key for key in ("to", "subject", "body") if not args[key]]
    if missing:
        raise HandoffValidationError(
            "Missing required Gmail draft field(s): " + ", ".join(missing)
        )
    if args["content_type"] not in {"text/markdown", "text/html", "text/plain"}:
        raise HandoffValidationError("Unsupported Gmail draft content_type.")

    return {
        "mode": "gmail_draft_handoff",
        "status": "ready_for_mcp",
        "provider": "gmail_mcp",
        "mcp_tool": "mcp__codex_apps__gmail._create_draft",
        "created_at": _now_bjt().isoformat(timespec="seconds"),
        "source_request_path": str(source_path) if source_path else "",
        "arguments": args,
        "safety": {
            "creates_draft_only": True,
            "sends_email": False,
            "requires_review": True,
        },
    }


def prepare_calendar_event_handoff(
    action: dict[str, Any],
    *,
    reviewed: bool,
    source_path: Path | None = None,
    overrides: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    if not reviewed:
        raise HandoffValidationError("Calendar event handoff requires --reviewed.")

    if action.get("schema_version") != 1:
        raise HandoffValidationError("Only schema_version=1 tool-agent requests are supported.")
    if action.get("agent") != "tool_agent":
        raise HandoffValidationError("Request must come from tool_agent.")
    if action.get("intent") != "calendar_event":
        raise HandoffValidationError("Only calendar_event requests can prepare calendar handoff.")
    if action.get("connector") != "calendar_mcp":
        raise HandoffValidationError("Calendar event request must target calendar_mcp.")
    if action.get("requires_confirmation") is not True:
        raise HandoffValidationError("requires_confirmation must be true.")
    if action.get("auto_execute") is not False:
        raise HandoffValidationError("auto_execute must be false for calendar handoff.")
    if action.get("operation") != "create_event_draft":
        raise HandoffValidationError("Unsupported calendar event operation.")

    fields = dict(action.get("fields") or {})
    for key, value in (overrides or {}).items():
        if value is not None:
            fields[key] = value

    args: dict[str, Any] = {
        "title": _non_empty(fields.get("title")),
        "time_window": _non_empty(fields.get("time_window")),
        "start_time": _non_empty(fields.get("start_time")),
        "end_time": _non_empty(fields.get("end_time")),
        "attendees": _split_attendees(fields.get("attendees")),
        "description": _non_empty(fields.get("description")),
    }

    for optional_key in ("calendar_id", "timezone_str", "location"):
        value = fields.get(optional_key)
        if _non_empty(value):
            args[optional_key] = _non_empty(value)

    add_google_meet = fields.get("add_google_meet")
    if isinstance(add_google_meet, bool):
        args["add_google_meet"] = add_google_meet

    missing = [key for key in ("title", "start_time", "end_time") if not args[key]]
    if missing:
        raise HandoffValidationError(
            "Missing required calendar field(s): " + ", ".join(missing)
        )
    invalid_times = [
        key for key in ("start_time", "end_time") if not _is_rfc3339_datetime(args[key])
    ]
    if invalid_times:
        raise HandoffValidationError(
            "Calendar field(s) must be RFC3339 datetime(s): " + ", ".join(invalid_times)
        )

    args.pop("time_window", None)

    return {
        "mode": "calendar_event_handoff",
        "status": "ready_for_mcp",
        "provider": "calendar_mcp",
        "mcp_tool": "mcp__codex_apps__google_calendar._create_event",
        "created_at": _now_bjt().isoformat(timespec="seconds"),
        "source_request_path": str(source_path) if source_path else "",
        "arguments": args,
        "safety": {
            "creates_event": False,
            "requires_review": True,
            "connector_available": True,
        },
        "message": "Pass arguments to Google Calendar MCP _create_event after user approval.",
    }


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
    parser.add_argument("request", nargs="*", help="Natural language tool request.")
    parser.add_argument("--dry-run", action="store_true", help="Do not write request files.")
    parser.add_argument(
        "--gmail-draft-handoff",
        type=Path,
        metavar="REQUEST_JSON",
        help="Validate a reviewed tool-agent request for Gmail draft creation.",
    )
    parser.add_argument(
        "--reviewed",
        action="store_true",
        help="Confirm the request JSON and resulting draft fields were reviewed.",
    )
    parser.add_argument("--to", help="Reviewed Gmail draft recipient override.")
    parser.add_argument("--subject", help="Reviewed Gmail draft subject override.")
    parser.add_argument("--body", help="Reviewed Gmail draft body override.")
    parser.add_argument(
        "--calendar-event-handoff",
        type=Path,
        metavar="REQUEST_JSON",
        help="Validate a reviewed tool-agent request for calendar event creation.",
    )
    parser.add_argument("--title", help="Reviewed calendar event title override.")
    parser.add_argument("--time-window", help="Reviewed calendar event time-window override.")
    parser.add_argument("--start-time", help="Reviewed RFC3339 calendar event start time.")
    parser.add_argument("--end-time", help="Reviewed RFC3339 calendar event end time.")
    parser.add_argument("--timezone", help="Reviewed IANA timezone name.")
    parser.add_argument("--attendees", help="Reviewed comma-separated attendees override.")
    parser.add_argument("--description", help="Reviewed calendar event description override.")
    parser.add_argument("--location", help="Reviewed calendar event location override.")
    parser.add_argument("--calendar-id", help="Reviewed Google Calendar ID override.")
    args = parser.parse_args()

    if args.gmail_draft_handoff and args.calendar_event_handoff:
        parser.error("use only one handoff mode at a time")

    if args.gmail_draft_handoff:
        try:
            action = load_request(args.gmail_draft_handoff)
            result = prepare_gmail_draft_handoff(
                action,
                reviewed=args.reviewed,
                source_path=args.gmail_draft_handoff,
                overrides={
                    "to": args.to,
                    "subject": args.subject,
                    "body": args.body,
                },
            )
        except HandoffValidationError as exc:
            parser.error(str(exc))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.calendar_event_handoff:
        try:
            action = load_request(args.calendar_event_handoff)
            result = prepare_calendar_event_handoff(
                action,
                reviewed=args.reviewed,
                source_path=args.calendar_event_handoff,
                overrides={
                    "title": args.title,
                    "time_window": args.time_window,
                    "start_time": args.start_time,
                    "end_time": args.end_time,
                    "timezone_str": args.timezone,
                    "attendees": args.attendees,
                    "description": args.description,
                    "location": args.location,
                    "calendar_id": args.calendar_id,
                },
            )
        except HandoffValidationError as exc:
            parser.error(str(exc))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if not args.request:
        parser.error("request is required unless a handoff mode is used")

    result = run(" ".join(args.request), dry_run=args.dry_run)
    print(json.dumps({
        "intent": result["intent"],
        "dry_run": result["dry_run"],
        "request_path": result["request_path"],
        "action": result["action"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
