from __future__ import annotations

import json
import re
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .clock import BEIJING, isoformat, utc_now
from .config import BASE_DIR, Settings, get_settings
from .database import Database
from .scheduler import create_scheduler
from .service import BriefService

TOPICS = ["大模型发布", "AI 编程工具", "开源模型", "AI 研究"]
STATUS_LABELS = {
    "generating": "生成中",
    "pending_delivery": "待投递",
    "sending": "投递中",
    "delivered": "已投递",
    "preview": "仅预览",
    "delivery_failed": "投递失败",
    "failed": "生成失败",
    "source_failed": "来源失败",
}


def split_values(value: str) -> list[str]:
    return list(dict.fromkeys(part.strip() for part in re.split(r"[,，\n]", value) if part.strip()))


def format_time(value: str | None) -> str:
    if not value:
        return "—"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    database = Database(settings.database)
    service = BriefService(settings, database)
    scheduler = create_scheduler(settings, service)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if not scheduler.running:
            scheduler.start()
        yield
        if scheduler.running:
            scheduler.shutdown(wait=False)

    application = FastAPI(title="每日 AI 新闻助手 Agent", lifespan=lifespan)
    application.state.settings = settings
    application.state.database = database
    application.state.service = service
    application.state.scheduler = scheduler
    templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
    templates.env.filters["beijing_time"] = format_time
    application.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

    def redirect(user_id: str | None = None, **message) -> RedirectResponse:
        query = {key: value for key, value in {"user_id": user_id, **message}.items() if value}
        return RedirectResponse("/" + ("?" + urlencode(query) if query else ""), status_code=303)

    @application.get("/")
    def index(request: Request, user_id: str | None = None, new: int = 0, message: str = "", error: str = ""):
        users = database.list_users()
        selected = database.get_user(user_id) if user_id else (None if new else (users[0] if users else None))
        subscription = database.get_subscription(selected["id"]) if selected else None
        briefs = database.list_briefs(selected["id"]) if selected else []
        for brief in briefs:
            brief["status_label"] = STATUS_LABELS.get(brief["status"], brief["status"])
            brief["content"] = json.loads(brief["content_json"]) if brief["content_json"] else None
            brief["run"] = database.get_run(brief["run_id"]) if brief["run_id"] else None
            brief["tool_calls"] = database.list_tool_calls(brief["run_id"]) if brief["run_id"] else []
        job = scheduler.get_job("daily_ai_news")
        return templates.TemplateResponse(request=request, name="index.html", context={
            "users": users,
            "selected": selected,
            "subscription": subscription,
            "briefs": briefs,
            "topics": TOPICS,
            "settings": settings,
            "custom_topics_value": "，".join(topic for topic in (subscription["topics"] if subscription else []) if topic not in TOPICS),
            "next_run": getattr(job, "next_run_time", None),
            "message": message,
            "error": error,
        })

    @application.post("/subscriptions")
    def save_subscription(
        user_id: str = Form(default=""),
        nickname: str = Form(...),
        email: str = Form(...),
        topics: list[str] = Form(default=[]),
        custom_topics: str = Form(default=""),
        keywords: str = Form(default=""),
    ):
        nickname = nickname.strip()
        email = email.strip()
        selected_topics = list(dict.fromkeys([topic for topic in topics if topic in TOPICS] + split_values(custom_topics)))
        keyword_list = split_values(keywords)
        if not nickname or len(nickname) > 50:
            return redirect(user_id or None, error="昵称不能为空，且不能超过 50 个字符")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            return redirect(user_id or None, error="请输入有效邮箱")
        if not selected_topics and not keyword_list:
            return redirect(user_id or None, error="至少选择一个话题或填写一个关键词")
        try:
            now = isoformat(utc_now(settings))
            if user_id:
                if not database.get_user(user_id):
                    return redirect(error="用户不存在")
                database.update_user(user_id, nickname, email, now)
            else:
                user_id = database.create_user(nickname, email, now)["id"]
            database.save_subscription(user_id, selected_topics, keyword_list, now)
        except sqlite3.IntegrityError:
            return redirect(user_id or None, error="该邮箱已绑定其他用户")
        return redirect(user_id, message="订阅已保存")

    @application.post("/users/{user_id}/generate")
    def generate(user_id: str, empty_materials: bool = Form(default=False)):
        try:
            brief = service.generate_for_user(user_id, empty_materials=empty_materials and settings.demo_mode)
            messages = {
                "delivered": "简报已生成并投递",
                "preview": "简报已生成；SMTP 未配置，仅预览",
                "generating": "相同任务正在执行，请稍后刷新",
                "delivery_failed": "简报已保存，但邮件投递失败，可重试",
                "source_failed": "新闻来源不可用，未发送无新闻邮件",
                "failed": "生成失败，请查看错误后重试",
            }
            return redirect(user_id, message=messages.get(brief["status"], "任务已处理"))
        except ValueError as exc:
            return redirect(user_id, error=str(exc))

    @application.post("/users/{user_id}/briefs/{brief_id}/retry")
    def retry_delivery(user_id: str, brief_id: str):
        try:
            brief = service.deliver_existing(brief_id, user_id)
            return redirect(user_id, message="邮件已投递" if brief["status"] == "delivered" else "尚未投递，请检查状态和 SMTP 配置")
        except ValueError as exc:
            return redirect(user_id, error=str(exc))

    @application.post("/demo/seed")
    def seed_demo():
        if not settings.demo_mode:
            return redirect(error="只有离线演示模式提供演示用户")
        examples = [
            ("演示甲·编程", "coding.demo@example.com", ["AI 编程工具"], False),
            ("演示乙·研究", "research.demo@example.com", ["AI 研究"], False),
            ("演示丙·空目录", "empty.demo@example.com", ["AI 编程工具"], True),
        ]
        first_user_id = None
        for nickname, email, topic_list, empty in examples:
            existing = next((user for user in database.list_users() if user["email"] == email), None)
            user = existing or database.create_user(nickname, email, isoformat(utc_now(settings)))
            first_user_id = first_user_id or user["id"]
            database.save_subscription(user["id"], topic_list, [], isoformat(utc_now(settings)))
            service.generate_for_user(user["id"], empty_materials=empty)
        return redirect(first_user_id, message="三位演示用户已就绪；丙展示了空目录补抓")

    @application.get("/health")
    def health():
        return {"ok": True, "mode": "demo" if settings.demo_mode else "deepseek", "scheduler_running": scheduler.running}

    return application


app = create_app()


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
