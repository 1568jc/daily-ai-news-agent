from __future__ import annotations

import json

from .agent import AgentError, AgentRunner
from .clock import beijing_date, isoformat, utc_now
from .config import Settings
from .database import Database
from .demo_llm import DemoLLMClient
from .llm import DeepSeekClient
from .mailer import EmailConfig, Mailer
from .news import NewsRepository
from .render import brief_markdown, brief_subject
from .sources import sources_as_dicts
from .tools import ToolRegistry


class BriefService:
    def __init__(self, settings: Settings, database: Database, client_factory=None, mailer=None):
        self.settings = settings
        self.database = database
        self.client_factory = client_factory or (DemoLLMClient if settings.demo_mode else DeepSeekClient)
        self.mailer = mailer or Mailer(settings)

    def email_config(self) -> EmailConfig:
        stored = self.database.get_email_settings()
        return EmailConfig.from_row(stored) if stored else EmailConfig.from_settings(self.settings)

    def _now(self) -> str:
        return isoformat(utc_now(self.settings))

    def generate_for_user(self, user_id: str, empty_materials: bool = False) -> dict:
        user = self.database.get_user(user_id)
        subscription = self.database.get_subscription(user_id)
        if not user or not subscription:
            raise ValueError("用户或订阅不存在")
        brief_date = beijing_date(self.settings)
        brief_id, should_generate = self.database.reserve_brief(user_id, brief_date, self._now())
        if not should_generate:
            brief = self.database.get_brief(brief_id)
            if brief["status"] in {"pending_delivery", "delivery_failed"} or (brief["status"] == "preview" and self.email_config().configured):
                return self.deliver_existing(brief_id, user_id)
            return brief
        run_id = self.database.create_run(user_id, brief_id, "demo" if self.settings.demo_mode else "deepseek", self._now())
        runner = None
        try:
            registry = self._prepare_task(run_id, user_id, brief_date, user, subscription, empty_materials)
            client = self.client_factory(self.settings)
            runner = AgentRunner(self.settings, self.database, client, registry, run_id)
            kind, content, rounds = runner.run()
            markdown = brief_markdown(content)
            subject = brief_subject(brief_date, content)
            status = "pending_delivery" if self.email_config().configured else "preview"
            self.database.save_generated_brief(brief_id, kind, content, markdown, subject, status, self._now())
            self.database.finish_run(run_id, "completed", rounds, self._now())
            if status == "pending_delivery":
                return self.deliver_existing(brief_id, user_id)
            return self.database.get_brief(brief_id)
        except AgentError as exc:
            self.database.finish_run(run_id, "failed", runner.rounds if runner else 0, self._now(), str(exc))
            self.database.mark_brief_failed(brief_id, exc.status, str(exc), self._now())
        except Exception as exc:
            self.database.finish_run(run_id, "failed", runner.rounds if runner else 0, self._now(), str(exc))
            self.database.mark_brief_failed(brief_id, "failed", str(exc), self._now())
        return self.database.get_brief(brief_id)

    def _prepare_task(self, run_id: str, user_id: str, brief_date: str, user: dict, subscription: dict, empty_materials: bool) -> ToolRegistry:
        workspace = self.settings.task_dir / user_id / f"{brief_date}_{run_id}"
        (workspace / "news").mkdir(parents=True, exist_ok=True)
        (workspace / "output").mkdir(parents=True, exist_ok=True)
        preferences = {"nickname": user["nickname"], "topics": subscription["topics"], "keywords": subscription["keywords"]}
        (workspace / "preferences.json").write_text(json.dumps(preferences, ensure_ascii=False, indent=2), encoding="utf-8")
        source_data = {"sources": sources_as_dicts(self.settings.demo_mode), "note": "source_id 是 fetch_news 使用的 ID；URL 仅供识别来源。"}
        (workspace / "sources.json").write_text(json.dumps(source_data, ensure_ascii=False, indent=2), encoding="utf-8")
        history = []
        for brief in self.database.list_briefs(user_id, limit=6):
            if brief["id"] == self.database.find_brief(user_id, brief_date)["id"] or not brief["content_json"]:
                continue
            content = json.loads(brief["content_json"])
            history.append({"brief_date": brief["brief_date"], "items": [{"title": item["title_zh"], "url": item["url"]} for item in content.get("items", [])]})
            if len(history) == 5:
                break
        (workspace / "history.json").write_text(json.dumps({"recent_briefs": history}, ensure_ascii=False, indent=2), encoding="utf-8")
        repository = NewsRepository(workspace, utc_now(self.settings), self.settings.news_timeout_seconds, self.settings.demo_mode)
        if self.settings.demo_mode and not empty_materials:
            repository.preload_demo()
        return ToolRegistry(workspace, repository)

    def deliver_existing(self, brief_id: str, user_id: str) -> dict:
        brief = self.database.get_brief(brief_id, user_id)
        if not brief or not brief["content_markdown"]:
            raise ValueError("简报不存在或尚未成功生成")
        if brief["status"] in {"delivered", "sending"}:
            return brief
        config = self.email_config()
        if not config.configured:
            return brief
        if not self.database.claim_delivery(brief_id, self._now()):
            return self.database.get_brief(brief_id)
        user = self.database.get_user(user_id)
        try:
            self.mailer.send(user["email"], brief["email_subject"], brief["content_markdown"], config=config)
            self.database.mark_delivered(brief_id, self._now())
        except Exception as exc:
            self.database.mark_delivery_failed(brief_id, str(exc), self._now())
        return self.database.get_brief(brief_id)

    def run_daily(self) -> None:
        for user in self.database.enabled_subscriptions():
            try:
                self.generate_for_user(user["id"])
            except Exception:
                continue
