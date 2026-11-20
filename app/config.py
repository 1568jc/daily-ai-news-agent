from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    demo_mode: bool
    demo_now: str
    database: Path
    task_dir: Path
    max_rounds: int
    agent_timeout_seconds: int
    news_timeout_seconds: int
    daily_hour: int
    daily_minute: int
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from: str
    smtp_use_tls: bool

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    @classmethod
    def from_env(cls) -> "Settings":
        db = Path(os.getenv("AINEWS_DB", "data/ainews.db"))
        tasks = Path(os.getenv("AINEWS_TASK_DIR", "data/tasks"))
        return cls(
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
            demo_mode=_bool("AINEWS_DEMO_MODE", True),
            demo_now=os.getenv("AINEWS_NOW", "").strip(),
            database=db if db.is_absolute() else BASE_DIR / db,
            task_dir=tasks if tasks.is_absolute() else BASE_DIR / tasks,
            max_rounds=_int("AINEWS_MAX_ROUNDS", 12),
            agent_timeout_seconds=_int("AINEWS_AGENT_TIMEOUT_SECONDS", 240),
            news_timeout_seconds=_int("AINEWS_NEWS_TIMEOUT_SECONDS", 15),
            daily_hour=_int("AINEWS_DAILY_HOUR", 8),
            daily_minute=_int("AINEWS_DAILY_MINUTE", 0),
            smtp_host=os.getenv("SMTP_HOST", "").strip(),
            smtp_port=_int("SMTP_PORT", 587),
            smtp_username=os.getenv("SMTP_USERNAME", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_from=os.getenv("SMTP_FROM", "").strip(),
            smtp_use_tls=_bool("SMTP_USE_TLS", True),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
