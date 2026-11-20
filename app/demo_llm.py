from __future__ import annotations

import json
from datetime import timedelta

from .clock import isoformat, utc_now
from .config import Settings


class DemoLLMClient:
    """A deterministic test double; its runs are always labelled as demo, never real LLM runs."""

    mode = "demo_test_double"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.counter = 0
        self.preferences: dict = {}
        self.read_queue: list[str] = []
        self.records: list[dict] = []
        self.fetched: set[str] = set()

    def _call(self, name: str, arguments: dict) -> dict:
        self.counter += 1
        return {"role": "assistant", "content": None, "tool_calls": [{"id": f"demo_call_{self.counter}", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}]}

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        if messages[-1]["role"] != "tool":
            return self._call("list_dir", {"path": "."})
        assistant = messages[-2]
        name = assistant["tool_calls"][0]["function"]["name"]
        result = json.loads(messages[-1]["content"])
        if name == "list_dir" and assistant["tool_calls"][0]["function"]["arguments"] == '{"path": "."}':
            return self._call("read_file", {"path": "preferences.json"})
        if name == "read_file" and json.loads(assistant["tool_calls"][0]["function"]["arguments"])["path"] == "preferences.json":
            self.preferences = json.loads(result["content"])
            return self._call("list_dir", {"path": "news"})
        if name == "list_dir":
            self.read_queue = [f"news/{entry['name']}" for entry in result.get("entries", []) if entry["name"].endswith(".json")]
            if self.read_queue:
                return self._call("read_file", {"path": self.read_queue.pop(0)})
            return self._fetch_or_finish()
        if name == "fetch_news":
            if result.get("ok"):
                return self._call("read_file", {"path": result["material_path"]})
            return self._fetch_or_finish()
        if name == "read_file":
            if result.get("ok"):
                payload = json.loads(result["content"])
                self.records.extend(payload.get("items", []))
            if self.read_queue:
                return self._call("read_file", {"path": self.read_queue.pop(0)})
            if not self.records:
                return self._fetch_or_finish()
            return self._submit()
        return self._submit()

    def _fetch_or_finish(self) -> dict:
        wanted = self._wanted_sources()
        source_id = next((source for source in wanted if source not in self.fetched), None)
        if source_id is None:
            if self.records:
                return self._submit()
            return {"role": "assistant", "content": "演示模型：来源不可用，无法可靠判断今日新闻。"}
        self.fetched.add(source_id)
        since = isoformat(utc_now(self.settings) - timedelta(hours=24))
        return self._call("fetch_news", {"source_id": source_id, "since": since})

    def _wanted_sources(self) -> list[str]:
        text = " ".join(self.preferences.get("topics", []) + self.preferences.get("keywords", [])).casefold()
        research = any(word in text for word in ["研究", "论文", "多语言", "可靠性"])
        coding = any(word in text for word in ["编程", "代码", "codepilot", "devbench", "开源"])
        if not research and not coding:
            return ["demo_coding", "demo_research"]
        return (["demo_research"] if research else []) + (["demo_coding"] if coding else [])

    def _selected(self) -> list[dict]:
        topics = self.preferences.get("topics", [])
        keywords = self.preferences.get("keywords", [])
        selected = []
        for record in self.records:
            haystack = (record["title"] + " " + record["summary"]).casefold()
            score = sum(3 for keyword in keywords if keyword.casefold() in haystack)
            matched_topics = []
            for topic in topics:
                tokens = {
                    "AI 编程工具": ["编程", "代码", "codepilot", "devbench"],
                    "AI 研究": ["研究", "论文", "多语言", "可靠性"],
                    "大模型发布": ["模型", "发布"],
                    "开源模型": ["开源", "模型"],
                }.get(topic, [topic])
                if any(token.casefold() in haystack for token in tokens):
                    score += 1
                    matched_topics.append(topic)
            if score:
                item = dict(record)
                item["matched_topics"] = matched_topics
                selected.append(item)
        unique = {record["news_id"]: record for record in selected}
        return list(unique.values())[:5]

    def _submit(self) -> dict:
        items = []
        for record in self._selected():
            topics = record.get("matched_topics") or self.preferences.get("topics", [])
            reason = f"符合你关注的「{'、'.join(topics)}」偏好。"
            items.append({"news_id": record["news_id"], "title_zh": record["title"], "summary": record["summary"], "reason": reason})
        note = "离线演示样例；未调用真实模型或外部新闻源。" if items else "已成功读取演示来源，但没有找到符合当前偏好的样例新闻。"
        return self._call("submit_brief", {"items": items, "note": note})
