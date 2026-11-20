from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.news import NewsRepository, parse_datetime
from app.tools import ToolError, ToolRegistry

from .helpers import test_settings


class ToolSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.workspace = root / "workspace"
        (self.workspace / "news").mkdir(parents=True)
        (self.workspace / "output").mkdir()
        (self.workspace / "preferences.json").write_text('{"keyword": "MCP"}', encoding="utf-8")
        settings = test_settings(root)
        self.tools = ToolRegistry(self.workspace, NewsRepository(self.workspace, parse_datetime(settings.demo_now), 2, True))

    def tearDown(self):
        self.temp.cleanup()

    def test_write_is_limited_to_output(self):
        self.assertTrue(self.tools.write_file("output/draft.md", "draft")["ok"])
        with self.assertRaises(ToolError):
            self.tools.write_file("preferences.json", "overwrite")

    def test_path_escape_is_rejected(self):
        with self.assertRaises(ToolError):
            self.tools.read_file("../outside.txt")

    def test_case_insensitive_content_search(self):
        result = self.tools.search_content("mcp", ".")
        self.assertEqual(result["matches"][0]["path"], "preferences.json")

    def test_shell_is_limited_to_read_only_wc(self):
        with self.assertRaises(ToolError):
            self.tools.bash("python --version")
        with self.assertRaises(ToolError):
            self.tools.bash("wc -l ../outside.txt")


if __name__ == "__main__":
    unittest.main()
