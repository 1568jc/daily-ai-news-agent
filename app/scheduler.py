from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .clock import BEIJING
from .config import Settings
from .service import BriefService


def create_scheduler(settings: Settings, service: BriefService) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=BEIJING)
    scheduler.add_job(
        service.run_daily,
        CronTrigger(hour=settings.daily_hour, minute=settings.daily_minute, timezone=BEIJING),
        id="daily_ai_news",
        name="每日 AI 新闻简报",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    return scheduler
