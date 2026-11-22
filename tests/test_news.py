from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

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

    def test_repeated_fetch_uses_cached_failure_without_retrying_network(self):
        since = isoformat(self.now - timedelta(hours=24))
        with self.assertRaises(NewsError):
            self.repository.fetch("demo_broken", since)
        repeated = self.repository.fetch("demo_broken", since)
        self.assertFalse(repeated["ok"])
        self.assertTrue(repeated["cached"])
        self.assertEqual(self.repository.fetch_failures, 1)

    def test_fetch_result_contains_summaries_for_direct_selection(self):
        result = self.repository.fetch("demo_coding", isoformat(self.now - timedelta(hours=24)))
        self.assertTrue(result["items"][0]["summary"])
        self.assertIn("news_id", result["items"][0])

    def test_large_feed_is_capped_and_digest_is_compact(self):
        repository = NewsRepository(self.workspace / "large", self.now, 2, False)
        records = []
        for index in range(40):
            entry = dict(demo_items(self.now)[0])
            entry["url"] = f"https://example.com/news/{index}"
            records.append(repository._normalize(entry, "测试来源"))
        repository._fetch_feed = lambda *_: records
        result = repository.fetch("openai", isoformat(self.now - timedelta(hours=24)))
        self.assertEqual(result["count"], 30)
        self.assertEqual(len(result["items"]), 12)
        self.assertTrue(result["digest_truncated"])

    @staticmethod
    def _rss(items: str = "") -> bytes:
        return f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>测试来源</title>{items}</channel></rss>'.encode("utf-8")

    def _recent_item(self) -> str:
        return "<item><title>新模型发布</title><link>https://example.com/news/1</link><pubDate>Wed, 14 Jan 2026 23:00:00 GMT</pubDate><description>模型发布摘要</description></item>"

    def test_valid_empty_feed_is_a_successful_empty_result(self):
        repository = NewsRepository(self.workspace / "empty_feed", self.now, 2, False)
        with patch("app.news.urllib.request.urlopen", return_value=BytesIO(self._rss())):
            result = repository.fetch("arxiv_ai", isoformat(self.now - timedelta(hours=24)))
        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(repository.fetch_successes, 1)
        self.assertEqual(repository.fetch_failures, 0)

    def test_transient_network_failure_is_retried(self):
        repository = NewsRepository(self.workspace / "network_retry", self.now, 2, False)
        responses = [TimeoutError("timed out"), BytesIO(self._rss(self._recent_item()))]
        with patch("app.news.urllib.request.urlopen", side_effect=responses) as request, patch("app.news.time.sleep") as sleep:
            result = repository.fetch("openai", isoformat(self.now - timedelta(hours=24)))
        self.assertEqual(result["count"], 1)
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once()

    def test_transient_malformed_feed_is_retried(self):
        repository = NewsRepository(self.workspace / "parse_retry", self.now, 2, False)
        responses = [BytesIO(b"<rss><channel>&</channel></rss>"), BytesIO(self._rss(self._recent_item()))]
        with patch("app.news.urllib.request.urlopen", side_effect=responses) as request, patch("app.news.time.sleep"):
            result = repository.fetch("deepmind", isoformat(self.now - timedelta(hours=24)))
        self.assertEqual(result["count"], 1)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(repository.fetch_failures, 0)

    def test_persistent_malformed_feed_retries_only_once(self):
        repository = NewsRepository(self.workspace / "persistent_parse_failure", self.now, 2, False)
        with patch("app.news.urllib.request.urlopen", side_effect=lambda *_args, **_kwargs: BytesIO(b"<rss><channel>&</channel></rss>")) as request, patch("app.news.time.sleep"):
            with self.assertRaisesRegex(NewsError, "RSS 解析失败"):
                repository.fetch("deepmind", isoformat(self.now - timedelta(hours=24)))
        self.assertEqual(request.call_count, 2)
        self.assertEqual(repository.fetch_failures, 1)


if __name__ == "__main__":
    unittest.main()
