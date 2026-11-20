from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.agent import AgentError, AgentRunner
from app.database import Database
from app.news import NewsRepository, parse_datetime
from app.tools import ToolRegistry

from .helpers import test_settings


class AdaptiveClient:
    def __init__(self):
        self.rounds = 0
        self.returned_call_ids = []

    def _call(self, name, arguments):
        call_id = f"call-{self.rounds}"
        return {"role": "assistant", "content": None, "tool_calls": [{"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]}

    def complete(self, messages, tools):
        self.rounds += 1
        if messages[-1]["role"] == "tool":
            previous_id = messages[-2]["tool_calls"][0]["id"]
            self.asserted_id = messages[-1]["tool_call_id"]
            assert self.asserted_id == previous_id
        if self.rounds == 1:
            return self._call("list_dir", {"path": "news"})
        result = json.loads(messages[-1]["content"])
        if self.rounds == 2:
            entries = result["entries"]
            if entries:
                return self._call("read_file", {"path": f"news/{entries[0]['name']}"})
            return self._call("fetch_news", {"source_id": "demo_coding", "since": "2026-01-14T00:00:00+00:00"})
        if messages[-2]["tool_calls"][0]["function"]["name"] == "fetch_news":
            return self._call("read_file", {"path": result["material_path"]})
        payload = json.loads(result["content"])
        record = payload["items"][0]
        return self._call("submit_brief", {"items": [{"news_id": record["news_id"], "title_zh": "中文标题", "summary": record["summary"], "reason": "符合编程工具订阅"}], "note": "测试"})


class AgentLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.settings = test_settings(self.root)
        self.db = Database(self.settings.database)
        self.now = parse_datetime(self.settings.demo_now)

    def tearDown(self):
        self.temp.cleanup()

    def _runner(self, client, preload=True):
        self.db.create_user("测试", "test@example.com", "2026-01-15T00:00:00Z")
        brief_id, _ = self.db.reserve_brief(self.db.list_users()[0]["id"], "2026-01-15", "2026-01-15T00:00:00Z")
        user_id = self.db.list_users()[0]["id"]
        run_id = self.db.create_run(user_id, brief_id, "test", "2026-01-15T00:00:00Z")
        workspace = self.root / "workspace"
        (workspace / "news").mkdir(parents=True)
        (workspace / "output").mkdir()
        repository = NewsRepository(workspace, self.now, 2, True)
        if preload:
            repository.preload_demo()
        registry = ToolRegistry(workspace, repository)
        return AgentRunner(self.settings, self.db, client, registry, run_id), run_id

    def test_model_chooses_next_tool_from_real_result_and_submit_stops(self):
        client = AdaptiveClient()
        runner, run_id = self._runner(client)
        kind, content, rounds = runner.run()
        self.assertEqual(kind, "news")
        self.assertEqual(rounds, 3)
        self.assertEqual(client.rounds, 3)
        self.assertEqual(len(content["items"]), 1)
        calls = self.db.list_tool_calls(run_id)
        self.assertEqual([call["tool_name"] for call in calls], ["list_dir", "read_file", "submit_brief"])
        self.assertTrue(all(call["ok"] for call in calls))

    def test_empty_material_result_causes_fetch(self):
        client = AdaptiveClient()
        runner, run_id = self._runner(client, preload=False)
        kind, _, _ = runner.run()
        self.assertEqual(kind, "news")
        self.assertEqual([call["tool_name"] for call in self.db.list_tool_calls(run_id)], ["list_dir", "fetch_news", "read_file", "submit_brief"])

    def test_ending_without_submit_is_failure(self):
        class NoToolClient:
            def complete(self, messages, tools):
                return {"role": "assistant", "content": "没有提交"}

        runner, _ = self._runner(NoToolClient())
        with self.assertRaises(AgentError):
            runner.run()


if __name__ == "__main__":
    unittest.main()
