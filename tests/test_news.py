from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from app.clock import isoformat
from app.news import NewsError, NewsRepository, demo_items, item_id, parse_datetime

from .helpers import test_settings


class NewsValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.settings = test_settings(root)
        self.now = parse_datetime(self.settings.demo_now)
        self.workspace = root / "workspace"
        (self.workspace / "news").mkdir(parents=True)
        self.repository = NewsRepository(self.workspace, self.now, 2, True)
        self.repository.preload_demo()

    def tearDown(self):
        self.temp.cleanup()

    def _submission(self, identifier):
        return {"news_id": identifier, "title_zh": "中文标题", "summary": "来源材料支持的摘要", "reason": "匹配研究偏好"}

    def test_submit_backfills_source_url_and_limits_window(self):
        identifier = next(iter(self.repository.records))
        kind, content = self.repository.validate_submission([self._submission(identifier)], "")
        item = content["items"][0]
        self.assertEqual(kind, "news")
        self.assertEqual(item["source"], self.repository.records[identifier]["source"])
        self.assertEqual(item["url"], self.repository.records[identifier]["url"])
        self.assertEqual(item["news_id"], identifier)

    def test_unknown_and_expired_ids_are_rejected(self):
        with self.assertRaisesRegex(NewsError, "未知新闻 ID"):
            self.repository.validate_submission([self._submission("news_not_real")], "")
        old = dict(demo_items(self.now)[0])
        old["url"] = "https://example.com/demo/old"
        old["published_at"] = isoformat(self.now - timedelta(hours=25))
        self.repository._save("old", [self.repository._normalize(old, old["source"])])
        with self.assertRaisesRegex(NewsError, "24 小时"):
            self.repository.validate_submission([self._submission(item_id(old["url"]))], "")

    def test_at_most_five_items(self):
        items = [self._submission(identifier) for identifier in list(self.repository.records)[:4]]
        items.extend(items[:2])
        with self.assertRaisesRegex(NewsError, "最多 5 条"):
            self.repository.validate_submission(items, "")

    def test_empty_result_requires_a_successful_source_or_material(self):
        empty = NewsRepository(self.workspace / "empty", self.now, 2, True)
        with self.assertRaisesRegex(NewsError, "无法判断"):
            empty.validate_submission([], "没有新闻")
        kind, _ = self.repository.validate_submission([], "已有材料但没有匹配")
        self.assertEqual(kind, "no_news")

    def test_fetch_failure_is_visible(self):
        with self.assertRaisesRegex(NewsError, "故障"):
            self.repository.fetch("demo_broken", isoformat(self.now - timedelta(hours=24)))
        self.assertEqual(self.repository.fetch_failures, 1)


if __name__ == "__main__":
    unittest.main()
