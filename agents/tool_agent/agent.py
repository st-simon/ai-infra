"""Tool Agent Phase 2 skeleton.

The local process plans tool requests only. Real Gmail and Calendar actions stay
behind MCP connectors and require an explicit confirmation step.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any, TypedDict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langgraph.graph import END, START, StateGraph

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REQUEST_DIR = PROJECT_ROOT / "logs" / "tool_agent_requests"
TASK_LOG_DIR = PROJECT_ROOT / "logs" / "tool_tasks"
DEFAULT_CALENDAR_TIMEZONE = "America/New_York"
TASK_STATUSES = {"planned", "in_progress", "done", "blocked", "canceled"}
WEEKDAY_ALIASES = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}
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
    "提醒",
    "reminder",
    "reminder_minutes",
    "日历",
    "calendar",
    "calendar_id",
    "参会人",
    "参与人",
    "attendees",
    "attendee",
    "描述",
    "description",
    "截止",
    "截止时间",
    "到期",
    "due",
    "deadline",
    "上下文",
    "背景",
    "context",
    "状态",
    "status",
)


class HandoffValidationError(ValueError):
    """Raised when a local request is not safe to hand to an MCP connector."""


class ToolAgentState(TypedDict):
    user_request: str
    dry_run: bool
    intent: str
    action: dict
    request_path: str
    task_path: str


def _now_bjt() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def classify_intent(text: str) -> str:
    lowered = text.lower()
    email_keywords = ("gmail", "email", "mail", "邮件", "草稿", "回复", "转发", "简报")
    calendar_keywords = (
        "calendar",
        "meeting",
        "schedule",
        "日程",
        "会议",
        "开会",
        "拜访",
        "安排",
    )
    task_keywords = ("todo", "task", "remind", "提醒", "待办", "任务", "跟进")

    if re.search(r"(任务|待办|todo|task)\s*[：:]", text, flags=re.IGNORECASE):
        return "task_note"
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


def _parse_positive_int(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(r"\d+", text)
    if not match:
        return None
    parsed = int(match.group(0))
    return parsed if parsed > 0 else None


def _detect_timezone(text: str) -> str:
    if any(keyword in text for keyword in ("北京时间", "上海时间", "中国时间")):
        return "Asia/Shanghai"
    if "纽约时间" in text or "美东时间" in text:
        return "America/New_York"
    return ""


def _apply_time_period(hour: int, period: str) -> int:
    if period in {"下午", "晚上", "傍晚"} and hour < 12:
        return hour + 12
    if period == "凌晨" and hour == 12:
        return 0
    return hour


def _parse_time_text(text: str, default_period: str = "") -> tuple[int, int] | None:
    match = re.search(
        r"(?P<hour>\d{1,2})(?:[:：](?P<minute>\d{1,2})|点(?P<minute_cn>\d{1,2})?分?)?",
        text,
    )
    if not match:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or match.group("minute_cn") or 0)
    if hour > 23 or minute > 59:
        return None

    period_match = re.search(r"(上午|下午|晚上|傍晚|中午|凌晨)", text)
    period = period_match.group(1) if period_match else default_period
    if period == "中午" and hour < 11:
        hour += 12
    else:
        hour = _apply_time_period(hour, period)
    return hour, minute


def _parse_date_text(text: str, today: date) -> tuple[date | None, str]:
    explicit = re.search(
        r"(?:(?P<year>\d{4})年)?(?P<month>\d{1,2})月(?P<day>\d{1,2})[日号]?",
        text,
    )
    if explicit:
        year = int(explicit.group("year") or today.year)
        month = int(explicit.group("month"))
        day = int(explicit.group("day"))
        try:
            return date(year, month, day), explicit.group(0)
        except ValueError:
            return None, ""

    relative = re.search(
        (
            r"(?P<prefix>下周|本周|这周|周|星期|礼拜)"
            r"(?P<weekday>[一二三四五六日天])"
        ),
        text,
    )
    if not relative:
        return None, ""

    target_weekday = WEEKDAY_ALIASES[relative.group("weekday")]
    days_ahead = target_weekday - today.weekday()
    if relative.group("prefix") == "下周":
        days_ahead += 7
    elif days_ahead < 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead), relative.group(0)


def parse_calendar_natural_language(
    text: str,
    *,
    today: date | None = None,
) -> dict[str, str]:
    timezone_str = _detect_timezone(text)
    today = today or _now_bjt().date()
    event_date, date_fragment = _parse_date_text(text, today)
    if not event_date:
        return {"start_time": "", "end_time": "", "timezone_str": timezone_str}

    time_pattern = re.compile(
        r"(?P<start_period>上午|下午|晚上|傍晚|中午|凌晨)?"
        r"(?P<start>\d{1,2}(?:[:：]\d{1,2}|点(?:\d{1,2}分?)?)?)"
        r"\s*(?:到|至|-|~|—)\s*"
        r"(?P<end_period>上午|下午|晚上|傍晚|中午|凌晨)?"
        r"(?P<end>\d{1,2}(?:[:：]\d{1,2}|点(?:\d{1,2}分?)?)?)"
    )
    match = time_pattern.search(text)
    if not match:
        period_match = re.search(r"(上午|下午|晚上|傍晚|中午|凌晨)", text)
        if not period_match:
            return {"start_time": "", "end_time": "", "timezone_str": timezone_str}
        period = period_match.group(1)
        period_ranges = {
            "上午": ((9, 0), (12, 0)),
            "下午": ((14, 0), (17, 0)),
            "傍晚": ((17, 0), (19, 0)),
            "晚上": ((19, 0), (21, 0)),
            "中午": ((12, 0), (13, 0)),
            "凌晨": ((0, 0), (2, 0)),
        }
        start, end = period_ranges[period]
        start_time = datetime.combine(event_date, datetime.min.time()).replace(
            hour=start[0],
            minute=start[1],
        )
        end_time = datetime.combine(event_date, datetime.min.time()).replace(
            hour=end[0],
            minute=end[1],
        )
        return {
            "start_time": start_time.isoformat(timespec="seconds"),
            "end_time": end_time.isoformat(timespec="seconds"),
            "timezone_str": timezone_str,
            "time_window": f"{date_fragment} {period}".strip(),
        }

    start_period = match.group("start_period") or ""
    end_period = match.group("end_period") or start_period
    start = _parse_time_text(match.group("start"), start_period)
    end = _parse_time_text(match.group("end"), end_period)
    if not start or not end:
        return {"start_time": "", "end_time": "", "timezone_str": timezone_str}

    start_time = datetime.combine(event_date, datetime.min.time()).replace(
        hour=start[0],
        minute=start[1],
    )
    end_time = datetime.combine(event_date, datetime.min.time()).replace(
        hour=end[0],
        minute=end[1],
    )
    if end_time <= start_time:
        end_time += timedelta(days=1)

    return {
        "start_time": start_time.isoformat(timespec="seconds"),
        "end_time": end_time.isoformat(timespec="seconds"),
        "timezone_str": timezone_str,
        "time_window": f"{date_fragment} {match.group(0)}".strip(),
    }


def infer_calendar_title(text: str) -> str:
    quoted = re.search(r"[“\"'](?P<title>[^”\"']+)[”\"']", text)
    subject = quoted.group("title").strip() if quoted else ""
    if subject and "准备会议" in text:
        return f"{subject}准备会议"
    if subject and "会议" in text:
        return f"{subject}会议"
    if subject:
        return subject

    visit = re.search(r"安排(?P<title>[^，,。；;]*拜访)", text)
    if visit:
        return visit.group("title").strip()

    meeting = re.search(
        r"(?:开|安排)(?:一个|一次|场)?(?P<title>[^，,。；;]*会议)",
        text,
    )
    if meeting:
        return meeting.group("title").strip()

    return ""


def extract_calendar_fields(user_request: str) -> dict[str, Any]:
    parsed = parse_calendar_natural_language(user_request)
    parsed_timezone = _detect_timezone(user_request) or parsed.get("timezone_str", "")
    return {
        "title": _extract_labeled_value(
            user_request,
            ("标题", "主题", "title", "subject"),
        ) or infer_calendar_title(user_request),
        "time_window": _extract_labeled_value(
            user_request,
            ("时间窗口", "时间", "time_window", "time", "when"),
        ) or parsed.get("time_window", ""),
        "start_time": _extract_labeled_value(
            user_request,
            ("开始时间", "开始", "start_time", "start"),
        ) or parsed.get("start_time", ""),
        "end_time": _extract_labeled_value(
            user_request,
            ("结束时间", "结束", "end_time", "end"),
        ) or parsed.get("end_time", ""),
        "attendees": _split_attendees(
            _extract_labeled_value(
                user_request,
                ("参会人", "参与人", "attendees", "attendee"),
            )
        ),
        "timezone_str": _extract_labeled_value(
            user_request,
            ("时区", "timezone_str", "timezone"),
        ) or parsed_timezone,
        "calendar_id": _extract_labeled_value(
            user_request,
            ("日历", "calendar_id", "calendar"),
        ),
        "location": _extract_labeled_value(user_request, ("地点", "location")),
        "reminder_minutes": _extract_labeled_value(
            user_request,
            ("提醒", "reminder_minutes", "reminder"),
        ),
        "description": _extract_labeled_value(
            user_request,
            ("描述", "description", "内容", "content", "正文", "body"),
        ),
    }


def extract_task_fields(user_request: str) -> dict[str, str]:
    return {
        "title": _extract_labeled_value(user_request, ("标题", "title", "任务", "task")),
        "due": _extract_labeled_value(
            user_request,
            ("截止时间", "截止", "到期", "due", "deadline"),
        ),
        "context": _extract_labeled_value(
            user_request,
            ("上下文", "背景", "context", "描述", "description", "内容", "content"),
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
                "reminder_minutes": calendar_fields["reminder_minutes"],
                "description": calendar_fields["description"] or user_request,
            },
            "notes": (
                "Prepare a calendar event draft only. "
                "Do not create it without explicit user approval."
            ),
        }
    if intent == "task_note":
        task_fields = extract_task_fields(user_request)
        return {
            **base,
            "connector": "local_task_log",
            "operation": "record_task_candidate",
            "fields": {
                "title": task_fields["title"] or user_request,
                "due": task_fields["due"],
                "context": task_fields["context"],
                "status": "planned",
            },
            "notes": "Record as a local task candidate. No external task system is used.",
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
        return {"request_path": "", "task_path": ""}

    REQUEST_DIR.mkdir(parents=True, exist_ok=True)
    stem = _now_bjt().strftime("%Y%m%d_%H%M%S") + f"_{state['intent']}"
    request_path = REQUEST_DIR / f"{stem}.json"
    request_path.write_text(
        json.dumps(state["action"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if state["intent"] != "task_note":
        return {"request_path": str(request_path), "task_path": ""}

    task_path = record_task_log(state["action"], request_path=request_path)
    return {"request_path": str(request_path), "task_path": str(task_path)}


def build_task_record(
    action: dict[str, Any],
    *,
    request_path: Path | None = None,
) -> dict[str, Any]:
    if action.get("schema_version") != 1:
        raise HandoffValidationError("Only schema_version=1 task actions are supported.")
    if action.get("agent") != "tool_agent":
        raise HandoffValidationError("Task action must come from tool_agent.")
    if action.get("intent") != "task_note":
        raise HandoffValidationError("Only task_note actions can be recorded as tasks.")
    if action.get("connector") != "local_task_log":
        raise HandoffValidationError("Task action must target local_task_log.")
    if action.get("auto_execute") is not False:
        raise HandoffValidationError("auto_execute must be false for local task logging.")

    fields = dict(action.get("fields") or {})
    title = _non_empty(fields.get("title"))
    if not title:
        raise HandoffValidationError("Task title is required.")

    created_at = _now_bjt().isoformat(timespec="microseconds")
    task_id = "task_" + re.sub(r"[^0-9T]", "", created_at)
    status = _non_empty(fields.get("status")) or "planned"
    if status not in TASK_STATUSES:
        raise HandoffValidationError(f"Unsupported task status: {status}")
    return {
        "schema_version": 1,
        "task_id": task_id,
        "agent": "tool_agent",
        "created_at": created_at,
        "updated_at": created_at,
        "status": status,
        "title": title,
        "due": _non_empty(fields.get("due")),
        "context": _non_empty(fields.get("context")),
        "source_request_path": str(request_path) if request_path else "",
        "user_request": _non_empty(action.get("user_request")),
    }


def record_task_log(
    action: dict[str, Any],
    *,
    request_path: Path | None = None,
    task_dir: Path = TASK_LOG_DIR,
) -> Path:
    task_dir.mkdir(parents=True, exist_ok=True)
    record = build_task_record(action, request_path=request_path)
    task_path = task_dir / f"{record['task_id']}.json"
    task_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return task_path


def load_task_record(path: Path) -> dict[str, Any]:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HandoffValidationError(f"Task file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise HandoffValidationError(f"Task file is not valid JSON: {path}") from exc

    if not isinstance(record, dict):
        raise HandoffValidationError("Task file must contain a JSON object.")
    if record.get("schema_version") != 1:
        raise HandoffValidationError("Only schema_version=1 task records are supported.")
    if not _non_empty(record.get("task_id")):
        raise HandoffValidationError("Task record is missing task_id.")
    return record


def find_task_path(identifier: str, *, task_dir: Path = TASK_LOG_DIR) -> Path:
    candidate = Path(identifier)
    if candidate.exists():
        return candidate

    task_id = candidate.stem if candidate.suffix == ".json" else identifier
    task_path = task_dir / f"{task_id}.json"
    if task_path.exists():
        return task_path

    raise HandoffValidationError(f"Task record not found: {identifier}")


def _parse_task_due(value: str) -> date:
    text = _non_empty(value)
    if not text:
        raise HandoffValidationError("Task due date is empty.")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise HandoffValidationError(f"Task due date must use YYYY-MM-DD: {value}") from exc


def _task_matches_query(record: dict[str, Any], query: str) -> bool:
    lowered = query.lower()
    haystack = "\n".join(
        str(record.get(field, ""))
        for field in ("task_id", "title", "due", "context", "status", "user_request")
    ).lower()
    return lowered in haystack


def list_task_records(
    *,
    task_dir: Path = TASK_LOG_DIR,
    status: str | None = None,
    query: str | None = None,
    due_before: str | None = None,
    due_after: str | None = None,
) -> list[dict[str, Any]]:
    if status and status not in TASK_STATUSES:
        raise HandoffValidationError(f"Unsupported task status: {status}")
    due_before_date = _parse_task_due(due_before) if due_before else None
    due_after_date = _parse_task_due(due_after) if due_after else None
    if not task_dir.exists():
        return []

    records = []
    for task_path in sorted(task_dir.glob("*.json")):
        record = load_task_record(task_path)
        if status and record.get("status") != status:
            continue
        if query and not _task_matches_query(record, query):
            continue
        if due_before_date or due_after_date:
            due_text = _non_empty(record.get("due"))
            if not due_text:
                continue
            due_date = _parse_task_due(due_text)
            if due_before_date and due_date > due_before_date:
                continue
            if due_after_date and due_date < due_after_date:
                continue
        records.append(record)
    return sorted(records, key=lambda record: str(record.get("created_at", "")))


def update_task_status(
    identifier: str,
    status: str,
    *,
    task_dir: Path = TASK_LOG_DIR,
) -> dict[str, Any]:
    if status not in TASK_STATUSES:
        raise HandoffValidationError(f"Unsupported task status: {status}")

    task_path = find_task_path(identifier, task_dir=task_dir)
    record = load_task_record(task_path)
    record["status"] = status
    record["updated_at"] = _now_bjt().isoformat(timespec="seconds")
    task_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


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


def _normalize_calendar_datetime(value: str, timezone_str: str) -> str:
    if _is_rfc3339_datetime(value):
        return value

    if not "T" in value:
        raise HandoffValidationError("Calendar datetime must include date and time.")

    try:
        timezone_info = ZoneInfo(timezone_str)
    except ZoneInfoNotFoundError as exc:
        raise HandoffValidationError(f"Unknown calendar timezone: {timezone_str}") from exc

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HandoffValidationError(f"Invalid calendar datetime: {value}") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone_info)
    return parsed.isoformat(timespec="seconds")


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

    timezone_str = _non_empty(fields.get("timezone_str")) or DEFAULT_CALENDAR_TIMEZONE
    args: dict[str, Any] = {
        "title": _non_empty(fields.get("title")),
        "time_window": _non_empty(fields.get("time_window")),
        "start_time": _non_empty(fields.get("start_time")),
        "end_time": _non_empty(fields.get("end_time")),
        "attendees": _split_attendees(fields.get("attendees")),
        "description": _non_empty(fields.get("description")),
        "timezone_str": timezone_str,
    }

    for optional_key in ("calendar_id", "location"):
        value = fields.get(optional_key)
        if _non_empty(value):
            args[optional_key] = _non_empty(value)

    reminder_minutes = _parse_positive_int(fields.get("reminder_minutes"))
    if reminder_minutes is not None:
        args["reminders"] = {
            "use_default": False,
            "overrides": [{"method": "popup", "minutes": reminder_minutes}],
        }

    add_google_meet = fields.get("add_google_meet")
    if isinstance(add_google_meet, bool):
        args["add_google_meet"] = add_google_meet

    missing = [key for key in ("title", "start_time", "end_time") if not args[key]]
    if missing:
        raise HandoffValidationError(
            "Missing required calendar field(s): " + ", ".join(missing)
        )
    args["start_time"] = _normalize_calendar_datetime(args["start_time"], timezone_str)
    args["end_time"] = _normalize_calendar_datetime(args["end_time"], timezone_str)

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
        "task_path": "",
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
    parser.add_argument("--reminder-minutes", help="Reviewed reminder offset in minutes.")
    parser.add_argument("--list-tasks", action="store_true", help="List local task records.")
    parser.add_argument("--task-status", help="Filter local tasks by status.")
    parser.add_argument(
        "--update-task-status",
        metavar="TASK_ID_OR_PATH",
        help="Update a local task record status.",
    )
    parser.add_argument("--new-status", help="New status for --update-task-status.")
    parser.add_argument("--task-query", help="Filter local tasks by text query.")
    parser.add_argument("--due-before", help="Filter local tasks due on or before YYYY-MM-DD.")
    parser.add_argument("--due-after", help="Filter local tasks due on or after YYYY-MM-DD.")
    args = parser.parse_args()

    mode_count = sum(
        bool(value)
        for value in (
            args.gmail_draft_handoff,
            args.calendar_event_handoff,
            args.list_tasks,
            args.update_task_status,
        )
    )
    if mode_count > 1:
        parser.error("use only one handoff or task-management mode at a time")

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
                    "reminder_minutes": args.reminder_minutes,
                },
            )
        except HandoffValidationError as exc:
            parser.error(str(exc))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.list_tasks:
        try:
            tasks = list_task_records(
                status=args.task_status,
                query=args.task_query,
                due_before=args.due_before,
                due_after=args.due_after,
            )
        except HandoffValidationError as exc:
            parser.error(str(exc))
        print(json.dumps({
            "mode": "local_task_list",
            "status_filter": args.task_status or "",
            "query": args.task_query or "",
            "due_before": args.due_before or "",
            "due_after": args.due_after or "",
            "count": len(tasks),
            "tasks": tasks,
        }, ensure_ascii=False, indent=2))
        return

    if args.update_task_status:
        if not args.new_status:
            parser.error("--new-status is required with --update-task-status")
        try:
            task = update_task_status(args.update_task_status, args.new_status)
        except HandoffValidationError as exc:
            parser.error(str(exc))
        print(json.dumps({
            "mode": "local_task_status_update",
            "task": task,
        }, ensure_ascii=False, indent=2))
        return

    if args.task_status:
        parser.error("--task-status requires --list-tasks")
    if args.task_query:
        parser.error("--task-query requires --list-tasks")
    if args.due_before:
        parser.error("--due-before requires --list-tasks")
    if args.due_after:
        parser.error("--due-after requires --list-tasks")

    if not args.request:
        parser.error("request is required unless a handoff mode is used")

    result = run(" ".join(args.request), dry_run=args.dry_run)
    print(json.dumps({
        "intent": result["intent"],
        "dry_run": result["dry_run"],
        "request_path": result["request_path"],
        "task_path": result["task_path"],
        "action": result["action"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
