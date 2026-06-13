import unittest

from agents.tool_agent.agent import (
    HandoffValidationError,
    build_action,
    extract_calendar_fields,
    extract_email_fields,
    prepare_calendar_event_handoff,
    prepare_gmail_draft_handoff,
)


def email_request(**field_overrides):
    fields = {
        "to": "person@example.com",
        "subject": "Meeting follow-up",
        "body": "Thanks for the discussion. Here are the next steps.",
    }
    fields.update(field_overrides)
    return {
        "schema_version": 1,
        "agent": "tool_agent",
        "intent": "email_draft",
        "connector": "gmail_mcp",
        "operation": "create_or_update_draft",
        "requires_confirmation": True,
        "auto_execute": False,
        "fields": fields,
    }


def calendar_request(**field_overrides):
    fields = {
        "title": "Customer visit",
        "time_window": "",
        "start_time": "2026-06-17T14:00:00+08:00",
        "end_time": "2026-06-17T15:00:00+08:00",
        "attendees": ["person@example.com"],
        "timezone_str": "Asia/Shanghai",
        "calendar_id": "primary",
        "location": "",
        "reminder_minutes": "",
        "description": "Discuss the project plan.",
    }
    fields.update(field_overrides)
    return {
        "schema_version": 1,
        "agent": "tool_agent",
        "intent": "calendar_event",
        "connector": "calendar_mcp",
        "operation": "create_event_draft",
        "requires_confirmation": True,
        "auto_execute": False,
        "fields": fields,
    }


class GmailDraftHandoffTests(unittest.TestCase):
    def test_extracts_chinese_email_fields(self):
        fields = extract_email_fields(
            "收件人：person@example.com 主题：项目更新 正文：这是今天的进展。"
        )

        self.assertEqual(fields["to"], "person@example.com")
        self.assertEqual(fields["subject"], "项目更新")
        self.assertEqual(fields["body"], "这是今天的进展。")

    def test_extracts_english_email_fields(self):
        fields = extract_email_fields(
            "to: person@example.com subject: Project update body: Progress is on track."
        )

        self.assertEqual(fields["to"], "person@example.com")
        self.assertEqual(fields["subject"], "Project update")
        self.assertEqual(fields["body"], "Progress is on track.")

    def test_email_action_uses_extracted_fields(self):
        action = build_action(
            "email_draft",
            "收件人：person@example.com "
            "主题：项目更新 "
            "正文：这是今天的进展。",
        )

        self.assertEqual(action["fields"]["to"], "person@example.com")
        self.assertEqual(action["fields"]["subject"], "项目更新")
        self.assertEqual(action["fields"]["body"], "这是今天的进展。")

    def test_email_action_keeps_request_when_body_missing(self):
        request = "请草拟邮件，收件人：person@example.com 主题：项目更新"
        action = build_action("email_draft", request)

        self.assertEqual(action["fields"]["to"], "person@example.com")
        self.assertEqual(action["fields"]["subject"], "项目更新")
        self.assertEqual(action["fields"]["body"], request)

    def test_requires_reviewed_flag(self):
        with self.assertRaisesRegex(HandoffValidationError, "reviewed"):
            prepare_gmail_draft_handoff(email_request(), reviewed=False)

    def test_rejects_non_email_request(self):
        action = email_request()
        action["intent"] = "calendar_event"

        with self.assertRaisesRegex(HandoffValidationError, "email_draft"):
            prepare_gmail_draft_handoff(action, reviewed=True)

    def test_rejects_missing_required_fields(self):
        with self.assertRaisesRegex(HandoffValidationError, "subject"):
            prepare_gmail_draft_handoff(email_request(subject=""), reviewed=True)

    def test_rejects_unconfirmed_request(self):
        action = email_request()
        action["requires_confirmation"] = False

        with self.assertRaisesRegex(HandoffValidationError, "requires_confirmation"):
            prepare_gmail_draft_handoff(action, reviewed=True)

    def test_builds_create_draft_arguments(self):
        result = prepare_gmail_draft_handoff(
            email_request(to="", subject=""),
            reviewed=True,
            overrides={
                "to": "reviewed@example.com",
                "subject": "Reviewed subject",
            },
        )

        self.assertEqual(result["mcp_tool"], "mcp__codex_apps__gmail._create_draft")
        self.assertEqual(result["arguments"]["to"], "reviewed@example.com")
        self.assertEqual(result["arguments"]["subject"], "Reviewed subject")
        self.assertEqual(result["arguments"]["content_type"], "text/markdown")
        self.assertFalse(result["safety"]["sends_email"])


class CalendarEventHandoffTests(unittest.TestCase):
    def test_extracts_chinese_calendar_fields(self):
        fields = extract_calendar_fields(
            "安排会议，标题：客户拜访 时间：下周三下午 "
            "开始：2026-06-17T14:00:00+08:00 "
            "结束：2026-06-17T15:00:00+08:00 "
            "参会人：a@example.com，b@example.com "
            "时区：Asia/Shanghai 地点：办公室 提醒：4320 描述：讨论方案。"
        )

        self.assertEqual(fields["title"], "客户拜访")
        self.assertEqual(fields["time_window"], "下周三下午")
        self.assertEqual(fields["start_time"], "2026-06-17T14:00:00+08:00")
        self.assertEqual(fields["end_time"], "2026-06-17T15:00:00+08:00")
        self.assertEqual(fields["attendees"], ["a@example.com", "b@example.com"])
        self.assertEqual(fields["timezone_str"], "Asia/Shanghai")
        self.assertEqual(fields["location"], "办公室")
        self.assertEqual(fields["reminder_minutes"], "4320")
        self.assertEqual(fields["description"], "讨论方案。")

    def test_calendar_action_uses_extracted_fields(self):
        action = build_action(
            "calendar_event",
            "meeting title: Customer visit start: 2026-06-17T14:00:00+08:00 "
            "end: 2026-06-17T15:00:00+08:00 "
            "attendees: a@example.com, b@example.com timezone: Asia/Shanghai "
            "reminder: 4320 description: Discuss plan.",
        )

        self.assertEqual(action["fields"]["title"], "Customer visit")
        self.assertEqual(action["fields"]["start_time"], "2026-06-17T14:00:00+08:00")
        self.assertEqual(action["fields"]["end_time"], "2026-06-17T15:00:00+08:00")
        self.assertEqual(action["fields"]["attendees"], ["a@example.com", "b@example.com"])
        self.assertEqual(action["fields"]["timezone_str"], "Asia/Shanghai")
        self.assertEqual(action["fields"]["reminder_minutes"], "4320")
        self.assertEqual(action["fields"]["description"], "Discuss plan.")

    def test_calendar_handoff_requires_reviewed_flag(self):
        with self.assertRaisesRegex(HandoffValidationError, "reviewed"):
            prepare_calendar_event_handoff(calendar_request(), reviewed=False)

    def test_calendar_handoff_rejects_missing_required_fields(self):
        with self.assertRaisesRegex(HandoffValidationError, "end_time"):
            prepare_calendar_event_handoff(calendar_request(end_time=""), reviewed=True)

    def test_calendar_handoff_rejects_non_datetime_values(self):
        with self.assertRaisesRegex(HandoffValidationError, "date and time"):
            prepare_calendar_event_handoff(
                calendar_request(start_time="next Wednesday afternoon"),
                reviewed=True,
            )

    def test_calendar_handoff_builds_create_event_arguments(self):
        result = prepare_calendar_event_handoff(
            calendar_request(attendees="a@example.com; b@example.com", reminder_minutes="4320"),
            reviewed=True,
        )

        self.assertEqual(result["mode"], "calendar_event_handoff")
        self.assertEqual(result["status"], "ready_for_mcp")
        self.assertEqual(result["mcp_tool"], "mcp__codex_apps__google_calendar._create_event")
        self.assertEqual(result["arguments"]["title"], "Customer visit")
        self.assertEqual(result["arguments"]["start_time"], "2026-06-17T14:00:00+08:00")
        self.assertEqual(result["arguments"]["end_time"], "2026-06-17T15:00:00+08:00")
        self.assertEqual(result["arguments"]["attendees"], ["a@example.com", "b@example.com"])
        self.assertEqual(result["arguments"]["calendar_id"], "primary")
        self.assertEqual(result["arguments"]["timezone_str"], "Asia/Shanghai")
        self.assertEqual(
            result["arguments"]["reminders"],
            {"use_default": False, "overrides": [{"method": "popup", "minutes": 4320}]},
        )
        self.assertFalse(result["safety"]["creates_event"])
        self.assertTrue(result["safety"]["connector_available"])

    def test_calendar_handoff_defaults_naive_times_to_calendar_timezone(self):
        result = prepare_calendar_event_handoff(
            calendar_request(
                start_time="2026-06-25T10:00:00",
                end_time="2026-06-25T12:00:00",
                timezone_str="",
            ),
            reviewed=True,
        )

        self.assertEqual(result["arguments"]["start_time"], "2026-06-25T10:00:00-04:00")
        self.assertEqual(result["arguments"]["end_time"], "2026-06-25T12:00:00-04:00")
        self.assertEqual(result["arguments"]["timezone_str"], "America/New_York")


if __name__ == "__main__":
    unittest.main()
