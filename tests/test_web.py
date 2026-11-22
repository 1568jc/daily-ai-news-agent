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
        self.assertIn('id="workbench"', response.text)
        self.assertIn('id="split-divider"', response.text)
        self.assertIn('class="brief-switcher"', response.text)
        self.assertIn('data-brief-panel=', response.text)
        self.assertIn("/static/app.js", response.text)

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

    def test_recent_fallback_is_clearly_labelled_in_workspace(self):
        database = self.client.app.state.database
        user = database.create_user("近期补充", "recent@example.com", "2026-01-15T00:00:00Z")
        database.save_subscription(user["id"], ["AI 研究"], [], "2026-01-15T00:00:00Z")
        brief_id, _ = database.reserve_brief(user["id"], "2026-01-15", "2026-01-15T00:00:00Z")
        content = {"items": [], "note": "今日暂无新发布，最近 7 天也没有匹配内容。", "content_window": "recent_7d", "demo_sample": False}
        database.save_generated_brief(brief_id, "no_news", content, "# 近期补充", "近期补充", "preview", "2026-01-15T00:00:00Z")
        response = self.client.get(f"/?user_id={user['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("近期 7 天补充", response.text)
        self.assertIn("今日暂无新发布", response.text)
        self.assertIn("非今日新闻", response.text)

    def test_generating_page_automatically_refreshes(self):
        database = self.client.app.state.database
        user = database.create_user("后台任务", "background@example.com", "2026-01-15T00:00:00Z")
        database.save_subscription(user["id"], ["AI 研究"], [], "2026-01-15T00:00:00Z")
        database.reserve_brief(user["id"], "2026-01-15", "2026-01-15T00:00:00Z")
        response = self.client.get(f"/?user_id={user['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("setTimeout", response.text)
        self.assertIn("generation-status", response.text)
        self.assertNotIn("window.location.href", response.text)
        self.assertIn("生成中", response.text)
        status = self.client.get(f"/users/{user['id']}/generation-status")
        self.assertTrue(status.json()["active"])
        self.assertEqual(status.json()["status"], "generating")
        response = self.client.post(f"/users/{user['id']}/delete", follow_redirects=True)
        self.assertIn("仍有生成或投递任务", response.text)
        self.assertIsNotNone(database.get_user(user["id"]))

    def test_query_users_by_nickname_or_email(self):
        database = self.client.app.state.database
        database.create_user("Alice", "alice@example.com", "2026-01-15T00:00:00Z")
        database.create_user("Bob", "bob@example.com", "2026-01-15T00:00:00Z")
        response = self.client.get("/?q=ALI")
        self.assertIn("Alice", response.text)
        self.assertNotIn("Bob", response.text)
        response = self.client.get("/?q=bob%40example.com")
        self.assertIn("Bob", response.text)
        self.assertNotIn("Alice", response.text)
        response = self.client.get("/?q=nobody")
        self.assertIn("未找到匹配", response.text)

    def test_update_user_and_subscription(self):
        database = self.client.app.state.database
        user = database.create_user("旧昵称", "old@example.com", "2026-01-15T00:00:00Z")
        database.save_subscription(user["id"], ["AI 研究"], ["论文"], "2026-01-15T00:00:00Z")
        response = self.client.post("/subscriptions", data={"user_id": user["id"], "nickname": "新昵称", "email": "new@example.com", "topics": ["AI 编程工具"], "custom_topics": "机器人", "keywords": "MCP，Claude"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        updated = database.get_user(user["id"])
        subscription = database.get_subscription(user["id"])
        self.assertEqual(updated["nickname"], "新昵称")
        self.assertEqual(updated["email"], "new@example.com")
        self.assertEqual(subscription["topics"], ["AI 编程工具", "机器人"])
        self.assertEqual(subscription["keywords"], ["MCP", "Claude"])
        self.assertIn("保存用户修改", response.text)

    def test_delete_user_cascades_subscription_briefs_and_tool_records(self):
        database = self.client.app.state.database
        user = database.create_user("待删除", "delete@example.com", "2026-01-15T00:00:00Z")
        database.save_subscription(user["id"], ["AI 编程工具"], [], "2026-01-15T00:00:00Z")
        self.client.post(f"/users/{user['id']}/generate")
        brief = database.list_briefs(user["id"])[0]
        self.assertTrue(database.list_tool_calls(brief["run_id"]))
        response = self.client.post(f"/users/{user['id']}/delete", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("已删除", response.text)
        self.assertIsNone(database.get_user(user["id"]))
        self.assertIsNone(database.get_subscription(user["id"]))
        self.assertEqual(database.list_briefs(user["id"]), [])
        with database.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM agent_runs WHERE user_id=?", (user["id"],)).fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM tool_calls WHERE run_id=?", (brief["run_id"],)).fetchone()[0], 0)

    def test_email_settings_are_editable_without_exposing_password(self):
        secret = "smtp-test-secret"
        response = self.client.post("/email-settings", data={"host": "smtp.qq.com", "port": "587", "username": "sender@qq.com", "password": secret, "sender": "sender@qq.com", "use_tls": "true"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("设置已保存并立即生效", response.text)
        self.assertNotIn(secret, response.text)
        config = self.client.app.state.service.email_config()
        self.assertTrue(config.configured)
        self.assertEqual(config.password, secret)
        response = self.client.post("/email-settings", data={"host": "smtp.qq.com", "port": "587", "username": "new@qq.com", "password": "", "sender": "new@qq.com", "use_tls": "true"}, follow_redirects=True)
        self.assertNotIn(secret, response.text)
        self.assertEqual(self.client.app.state.service.email_config().password, secret)
        self.assertEqual(self.client.app.state.service.email_config().username, "new@qq.com")
        self.client.post("/email-settings", data={"host": "", "port": "587", "username": "", "password": "", "sender": ""})
        self.assertFalse(self.client.app.state.service.email_config().configured)

    def test_duplicate_feedback_and_force_regeneration_history(self):
        database = self.client.app.state.database
        user = database.create_user("重复测试", "repeat@example.com", "2026-01-15T00:00:00Z")
        database.save_subscription(user["id"], ["AI 编程工具"], [], "2026-01-15T00:00:00Z")
        self.client.post(f"/users/{user['id']}/generate")
        first = database.list_briefs(user["id"])[0]
        response = self.client.post(f"/users/{user['id']}/generate", follow_redirects=True)
        self.assertIn("今日简报已生成", response.text)
        self.assertIn("未重复生成", response.text)
        self.assertIn("重新生成并预览", response.text)
        response = self.client.post(f"/users/{user['id']}/regenerate", follow_redirects=True)
        self.assertIn("历史版本", response.text)
        current = database.list_briefs(user["id"])[0]
        self.assertNotEqual(current["run_id"], first["run_id"])
        versions = database.list_brief_versions(first["id"])
        self.assertEqual(len(versions), 1)
        self.assertTrue(database.list_tool_calls(first["run_id"]))

    def test_delivered_duplicate_and_explicit_resend_have_distinct_feedback(self):
        class SuccessfulMailer:
            def __init__(self):
                self.messages = []

            def send(self, recipient, subject, markdown, config=None):
                self.messages.append(markdown)

        database = self.client.app.state.database
        mailer = SuccessfulMailer()
        self.client.app.state.service.mailer = mailer
        database.save_email_settings("smtp.qq.com", 587, "sender@qq.com", "secret", "sender@qq.com", True, "2026-01-15T00:00:00Z")
        user = database.create_user("重发测试", "resend@example.com", "2026-01-15T00:00:00Z")
        database.save_subscription(user["id"], ["AI 编程工具"], [], "2026-01-15T00:00:00Z")
        self.client.post(f"/users/{user['id']}/generate")
        brief = database.list_briefs(user["id"])[0]
        self.assertEqual(brief["status"], "delivered")
        response = self.client.post(f"/users/{user['id']}/generate", follow_redirects=True)
        self.assertIn("已生成并投递", response.text)
        self.assertIn("未重复执行", response.text)
        self.assertEqual(len(mailer.messages), 1)
        response = self.client.post(f"/users/{user['id']}/briefs/{brief['id']}/resend", follow_redirects=True)
        self.assertIn("再次发送同一简报", response.text)
        self.assertEqual(len(mailer.messages), 2)


if __name__ == "__main__":
    unittest.main()
