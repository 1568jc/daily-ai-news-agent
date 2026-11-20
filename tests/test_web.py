from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app

from .helpers import test_settings


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = test_settings(Path(self.temp.name))
        self.client = TestClient(create_app(self.settings))
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp.cleanup()

    def test_subscription_generate_history_and_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["scheduler_running"])
        response = self.client.post("/subscriptions", data={"nickname": "测试用户", "email": "web@example.com", "topics": ["AI 编程工具"], "keywords": "MCP"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("订阅已保存", response.text)
        database = self.client.app.state.database
        user = database.list_users()[0]
        response = self.client.post(f"/users/{user['id']}/generate", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("仅预览", response.text)
        self.assertIn("本次工具调用", response.text)
        self.assertIn("演示样例", response.text)

    def test_demo_seed_prepares_comparison_and_empty_workspace_runs(self):
        response = self.client.post("/demo/seed", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        database = self.client.app.state.database
        self.assertEqual(len(database.list_users()), 3)
        empty = next(user for user in database.list_users() if user["email"] == "empty.demo@example.com")
        brief = database.list_briefs(empty["id"])[0]
        names = [call["tool_name"] for call in database.list_tool_calls(brief["run_id"])]
        self.assertIn("fetch_news", names)

    def test_source_failure_is_shown_without_email_preview(self):
        database = self.client.app.state.database
        user = database.create_user("故障用户", "failure@example.com", "2026-01-15T00:00:00Z")
        database.save_subscription(user["id"], ["AI 研究"], [], "2026-01-15T00:00:00Z")
        brief_id, _ = database.reserve_brief(user["id"], "2026-01-15", "2026-01-15T00:00:00Z")
        database.mark_brief_failed(brief_id, "source_failed", "模拟来源失败", "2026-01-15T00:00:00Z")
        response = self.client.get(f"/?user_id={user['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("来源失败", response.text)
        self.assertIn("模拟来源失败", response.text)
        self.assertNotIn("最终邮件正文预览", response.text)

    def test_generating_page_automatically_refreshes(self):
        database = self.client.app.state.database
        user = database.create_user("后台任务", "background@example.com", "2026-01-15T00:00:00Z")
        database.save_subscription(user["id"], ["AI 研究"], [], "2026-01-15T00:00:00Z")
        database.reserve_brief(user["id"], "2026-01-15", "2026-01-15T00:00:00Z")
        response = self.client.get(f"/?user_id={user['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("setTimeout", response.text)
        self.assertIn("生成中", response.text)


if __name__ == "__main__":
    unittest.main()
