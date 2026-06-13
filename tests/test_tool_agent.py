import unittest

from agents.tool_agent.agent import HandoffValidationError, prepare_gmail_draft_handoff


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


class GmailDraftHandoffTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
