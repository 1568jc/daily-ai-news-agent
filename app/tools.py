from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from .news import NewsRepository


class ToolError(Exception):
    pass


TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "list_dir", "description": "列出当前任务工作区指定目录的内容。", "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "相对任务目录的路径，例如 . 或 news"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "读取任务工作区中的文本文件，如偏好、来源清单和新闻材料。", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "search_content", "description": "在任务目录的文本文件中搜索关键词，英文忽略大小写。", "parameters": {"type": "object", "properties": {"keyword": {"type": "string"}, "dir": {"type": "string"}}, "required": ["keyword", "dir"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "在 output/ 中写入候选清单或草稿，不能覆盖偏好和原始材料。", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "bash", "description": "执行受限只读命令，仅允许 wc -l/-w/-c 后接工作区内的文件路径。", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "fetch_news", "description": "按 sources.json 中的来源 ID 拉取 RSS/Atom。since 必须是带时区的 ISO 时间。返回真实状态、材料路径和候选摘要；候选足够时可直接提交，无需重复读取整个文件。", "parameters": {"type": "object", "properties": {"source_id": {"type": "string"}, "since": {"type": "string"}}, "required": ["source_id", "since"]}}},
    {"type": "function", "function": {"name": "submit_brief", "description": "提交最终简报，最多 5 条。只能引用实际材料中的 news_id；摘要必须忠实于材料，reason 说明与用户偏好的关系。没有匹配新闻且来源可用时，items 可为空并在 note 说明。成功提交即结束。", "parameters": {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {"news_id": {"type": "string"}, "title_zh": {"type": "string"}, "summary": {"type": "string"}, "reason": {"type": "string"}}, "required": ["news_id", "title_zh", "summary", "reason"]}}, "note": {"type": "string"}}, "required": ["items", "note"]}}},
]


class ToolRegistry:
    def __init__(self, workspace: Path, news: NewsRepository):
        self.workspace = workspace.resolve()
        self.news = news
        self.submitted: tuple[str, dict] | None = None
        self.handlers = {
            "list_dir": self.list_dir,
            "read_file": self.read_file,
            "search_content": self.search_content,
            "write_file": self.write_file,
            "bash": self.bash,
            "fetch_news": self.fetch_news,
            "submit_brief": self.submit_brief,
        }

    def _resolve(self, value: str, must_exist: bool = False) -> tuple[Path, Path]:
        if not isinstance(value, str) or not value.strip():
            raise ToolError("路径不能为空")
        candidate = Path(value)
        if candidate.is_absolute():
            raise ToolError("只允许任务工作区内的相对路径")
        resolved = (self.workspace / candidate).resolve()
        try:
            relative = Path(".") if resolved == self.workspace else resolved.relative_to(self.workspace)
        except ValueError as exc:
            raise ToolError("禁止访问任务工作区之外的路径") from exc
        if must_exist and not resolved.exists():
            raise ToolError(f"路径不存在：{value}")
        return resolved, relative

    @staticmethod
    def _text(path: Path) -> str:
        if path.stat().st_size > 2_000_000:
            raise ToolError("文件超过 2 MB 读取限制")
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError("只能读取 UTF-8 文本文件") from exc

    def list_dir(self, path: str) -> dict:
        directory, relative = self._resolve(path, must_exist=True)
        if not directory.is_dir():
            raise ToolError("list_dir 的目标必须是目录")
        entries = []
        for item in sorted(directory.iterdir()):
            entries.append({"name": item.name + ("/" if item.is_dir() else ""), "size": item.stat().st_size if item.is_file() else None})
        return {"ok": True, "path": str(relative), "entries": entries[:200]}

    def read_file(self, path: str) -> dict:
        file_path, relative = self._resolve(path, must_exist=True)
        if not file_path.is_file():
            raise ToolError("read_file 的目标必须是文件")
        content = self._text(file_path)
        return {"ok": True, "path": str(relative), "content": content[:20000], "truncated": len(content) > 20000}

    def search_content(self, keyword: str, dir: str) -> dict:
        if not isinstance(keyword, str) or not keyword.strip():
            raise ToolError("keyword 不能为空")
        directory, _ = self._resolve(dir, must_exist=True)
        if not directory.is_dir():
            raise ToolError("dir 必须是目录")
        needle = keyword.casefold()
        matches = []
        for file_path in sorted(directory.rglob("*")):
            try:
                resolved_file = file_path.resolve()
                resolved_file.relative_to(self.workspace)
            except (OSError, ValueError):
                continue
            if not resolved_file.is_file() or resolved_file.suffix.lower() not in {".json", ".md", ".txt"}:
                continue
            try:
                content = self._text(resolved_file)
            except (OSError, ToolError):
                continue
            folded = content.casefold()
            start = 0
            while (position := folded.find(needle, start)) >= 0:
                matches.append({"path": str(file_path.relative_to(self.workspace)), "snippet": content[max(0, position - 80):position + len(keyword) + 120]})
                if len(matches) >= 50:
                    return {"ok": True, "matches": matches, "truncated": True}
                start = position + len(needle)
        return {"ok": True, "matches": matches, "truncated": False}

    def write_file(self, path: str, content: str) -> dict:
        file_path, relative = self._resolve(path)
        if not relative.parts or relative.parts[0] != "output":
            raise ToolError("write_file 只能写入 output/ 目录")
        if not isinstance(content, str):
            raise ToolError("content 必须是字符串")
        if len(content) > 50000:
            raise ToolError("写入内容超过 50000 字符限制")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(relative), "characters": len(content)}

    def bash(self, command: str) -> dict:
        try:
            parts = shlex.split(command, posix=True)
        except ValueError as exc:
            raise ToolError(f"命令解析失败：{exc}") from exc
        if not parts or parts[0] != "wc":
            raise ToolError("bash 只允许 wc 命令")
        options = []
        files = []
        for part in parts[1:]:
            if part in {"-l", "-w", "-c"}:
                options.append(part)
            elif part.startswith("-"):
                raise ToolError(f"不允许的 wc 参数：{part}")
            else:
                files.append(part)
        if not options or not files:
            raise ToolError("wc 至少需要一个只读选项 (-l/-w/-c) 和一个文件")
        for filename in files:
            file_path, _ = self._resolve(filename, must_exist=True)
            if not file_path.is_file():
                raise ToolError("wc 只能读取工作区内的普通文件")
        try:
            completed = subprocess.run(["wc", *options, *files], cwd=self.workspace, shell=False, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ToolError(f"wc 执行失败：{exc}") from exc
        if completed.returncode != 0:
            raise ToolError(f"wc 返回错误：{completed.stderr[:500]}")
        return {"ok": True, "output": completed.stdout[:4000]}

    def fetch_news(self, source_id: str, since: str) -> dict:
        return self.news.fetch(source_id, since)

    def submit_brief(self, items: object, note: str) -> dict:
        if self.submitted is not None:
            raise ToolError("本次任务已经提交过简报")
        kind, content = self.news.validate_submission(items, note)
        output = self.workspace / "output" / "submission.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
        self.submitted = (kind, content)
        return {"ok": True, "status": "submitted", "kind": kind, "item_count": len(content["items"])}

    def execute(self, name: str, arguments: dict) -> dict:
        handler = self.handlers.get(name)
        if handler is None:
            raise ToolError(f"未注册的工具：{name}")
        try:
            return handler(**arguments)
        except TypeError as exc:
            raise ToolError(f"工具参数不匹配：{exc}") from exc
