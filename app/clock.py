from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .config import Settings

BEIJING = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc


def utc_now(settings: Settings) -> datetime:
    if settings.demo_now:
        value = settings.demo_now.strip()
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError("AINEWS_NOW 必须包含时区，例如 2026-01-15T08:00:00+08:00")
        return parsed.astimezone(UTC)
    return datetime.now(UTC)


def beijing_date(settings: Settings) -> str:
    return utc_now(settings).astimezone(BEIJING).date().isoformat()


def isoformat(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
