"""Server-side date helpers. The pod clock is UTC — anchor "today" here, never in the browser."""

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    """Aware UTC now — store aware datetimes so Pydantic serialises with the offset."""
    return datetime.now(timezone.utc)


def to_aware_utc(dt: datetime) -> datetime:
    """Motor hands back naive datetimes; normalise on read to avoid naive/aware TypeError."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def today_iso(tz: str | None = None) -> str:
    """Today's date as YYYY-MM-DD in `tz` (default: APP_TZ env, else UTC)."""
    zone = tz or os.environ.get("APP_TZ", "UTC")
    return datetime.now(ZoneInfo(zone)).strftime("%Y-%m-%d")
