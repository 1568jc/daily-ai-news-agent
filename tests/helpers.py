from __future__ import annotations

from pathlib import Path

from app.config import Settings


def test_settings(root: Path, **overrides) -> Settings:
    values = {
        "deepseek_api_key": "",
        "deepseek_base_url": "https://api.deepseek.com",
        "deepseek_model": "deepseek-flash",
        "demo_mode": True,
        "demo_now": "2026-01-15T00:00:00+00:00",
        "database": root / "test.db",
        "task_dir": root / "tasks",
        "max_rounds": 10,
        "agent_timeout_seconds": 20,
        "news_timeout_seconds": 2,
        "daily_hour": 8,
        "daily_minute": 0,
        "smtp_host": "",
        "smtp_port": 587,
        "smtp_username": "",
        "smtp_password": "",
        "smtp_from": "",
        "smtp_use_tls": True,
    }
    values.update(overrides)
    return Settings(**values)
