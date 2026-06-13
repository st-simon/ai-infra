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
        "time_window": "next Wednesday afternoon",
        "attendees": ["person@example.com"],
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
            "参会人：a@example.com，b@example.com 描述：讨论方案。"
        )

        self.assertEqual(fields["title"], "客户拜访")
        self.assertEqual(fields["time_window"], "下周三下午")
        self.assertEqual(fields["attendees"], ["a@example.com", "b@example.com"])
        self.assertEqual(fields["description"], "讨论方案。")

    def test_calendar_action_uses_extracted_fields(self):
        action = build_action(
            "calendar_event",
            "meeting title: Customer visit when: next Wednesday afternoon "
            "attendees: a@example.com, b@example.com description: Discuss plan.",
        )

        self.assertEqual(action["fields"]["title"], "Customer visit")
        self.assertEqual(action["fields"]["time_window"], "next Wednesday afternoon")
        self.assertEqual(action["fields"]["attendees"], ["a@example.com", "b@example.com"])
        self.assertEqual(action["fields"]["description"], "Discuss plan.")

    def test_calendar_handoff_requires_reviewed_flag(self):
        with self.assertRaisesRegex(HandoffValidationError, "reviewed"):
            prepare_calendar_event_handoff(calendar_request(), reviewed=False)

    def test_calendar_handoff_rejects_missing_required_fields(self):
        with self.assertRaisesRegex(HandoffValidationError, "time_window"):
            prepare_calendar_event_handoff(calendar_request(time_window=""), reviewed=True)

    def test_calendar_handoff_validates_but_does_not_create_event(self):
        result = prepare_calendar_event_handoff(
            calendar_request(attendees="a@example.com; b@example.com"),
            reviewed=True,
        )

        self.assertEqual(result["mode"], "calendar_event_handoff")
        self.assertEqual(result["status"], "blocked_missing_connector")
        self.assertEqual(result["arguments"]["title"], "Customer visit")
        self.assertEqual(result["arguments"]["attendees"], ["a@example.com", "b@example.com"])
        self.assertFalse(result["safety"]["creates_event"])


if __name__ == "__main__":
    unittest.main()
