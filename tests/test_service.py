from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.database import Database
from app.service import BriefService

from .helpers import test_settings


class RecordingMailer:
    def __init__(self, fail=False):
        self.fail = fail
        self.messages = []

    def send(self, recipient, subject, markdown):
        if self.fail:
            raise RuntimeError("模拟 SMTP 故障")
        self.messages.append((recipient, subject, markdown))


class BriefServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.settings = test_settings(self.root)
        self.db = Database(self.settings.database)
        self.service = BriefService(self.settings, self.db)

    def tearDown(self):
        self.temp.cleanup()

    def _user(self, nickname, email, topics):
        user = self.db.create_user(nickname, email, "2026-01-15T00:00:00Z")
        self.db.save_subscription(user["id"], topics, [], "2026-01-15T00:00:00Z")
        return user

    def test_same_samples_produce_different_personalized_briefs(self):
        coding = self._user("甲", "coding@example.com", ["AI 编程工具"])
        research = self._user("乙", "research@example.com", ["AI 研究"])
        first = self.service.generate_for_user(coding["id"])
        second = self.service.generate_for_user(research["id"])
        first_content = json.loads(first["content_json"])
        second_content = json.loads(second["content_json"])
        self.assertTrue(first_content["items"])
        self.assertTrue(second_content["items"])
        self.assertNotEqual({item["news_id"] for item in first_content["items"]}, {item["news_id"] for item in second_content["items"]})
        self.assertTrue(all("编程" in item["reason"] for item in first_content["items"]))
        self.assertTrue(all("研究" in item["reason"] for item in second_content["items"]))

    def test_repeat_trigger_reuses_daily_brief(self):
        user = self._user("甲", "coding@example.com", ["AI 编程工具"])
        first = self.service.generate_for_user(user["id"])
        second = self.service.generate_for_user(user["id"])
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["status"], "preview")
        with self.db.connect() as conn:
            runs = conn.execute("SELECT COUNT(*) FROM agent_runs WHERE user_id=?", (user["id"],)).fetchone()[0]
            briefs = conn.execute("SELECT COUNT(*) FROM briefs WHERE user_id=?", (user["id"],)).fetchone()[0]
        self.assertEqual(runs, 1)
        self.assertEqual(briefs, 1)

    def test_empty_workspace_can_fetch_before_submit(self):
        user = self._user("甲", "coding@example.com", ["AI 编程工具"])
        brief = self.service.generate_for_user(user["id"], empty_materials=True)
        self.assertEqual(brief["status"], "preview")
        names = [call["tool_name"] for call in self.db.list_tool_calls(brief["run_id"])]
        self.assertIn("fetch_news", names)
        self.assertLess(names.index("fetch_news"), names.index("submit_brief"))

    def test_delivery_failure_retries_saved_brief_without_regenerating(self):
        self.settings = test_settings(self.root, smtp_host="smtp.example.com", smtp_from="news@example.com")
        self.db = Database(self.settings.database)
        mailer = RecordingMailer(fail=True)
        self.service = BriefService(self.settings, self.db, mailer=mailer)
        user = self._user("甲", "coding@example.com", ["AI 编程工具"])
        failed = self.service.generate_for_user(user["id"])
        self.assertEqual(failed["status"], "delivery_failed")
        self.assertTrue(failed["content_markdown"])
        successful_mailer = RecordingMailer()
        self.service.mailer = successful_mailer
        delivered = self.service.generate_for_user(user["id"])
        self.assertEqual(delivered["status"], "delivered")
        self.service.generate_for_user(user["id"])
        self.assertEqual(len(successful_mailer.messages), 1)
        with self.db.connect() as conn:
            runs = conn.execute("SELECT COUNT(*) FROM agent_runs WHERE brief_id=?", (failed["id"],)).fetchone()[0]
        self.assertEqual(runs, 1)

    def test_source_failure_does_not_create_or_send_normal_brief(self):
        class BrokenSourceClient:
            def __init__(self):
                self.round = 0

            def complete(self, messages, tools):
                self.round += 1
                if self.round > 1:
                    return {"role": "assistant", "content": "来源失败，无法判断"}
                return {"role": "assistant", "content": None, "tool_calls": [{"id": "broken-1", "type": "function", "function": {"name": "fetch_news", "arguments": '{"source_id":"demo_broken","since":"2026-01-14T00:00:00+00:00"}'}}]}

        mailer = RecordingMailer()
        self.service.client_factory = lambda _: BrokenSourceClient()
        self.service.mailer = mailer
        user = self._user("故障演练", "broken@example.com", ["AI 研究"])
        brief = self.service.generate_for_user(user["id"], empty_materials=True)
        self.assertEqual(brief["status"], "source_failed")
        self.assertIsNone(brief["content_json"])
        self.assertEqual(mailer.messages, [])
        self.assertEqual(self.db.get_run(brief["run_id"])["rounds"], 2)


if __name__ == "__main__":
    unittest.main()
