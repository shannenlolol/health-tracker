"""Timezone choices and local day boundaries."""
from datetime import datetime, time, timedelta, timezone
from functools import cache
from zoneinfo import ZoneInfo, available_timezones

# Offered as buttons; anything else can be typed as a city or IANA name.
COMMON = {
    "Singapore": "Asia/Singapore",
    "Kuala Lumpur": "Asia/Kuala_Lumpur",
    "Jakarta": "Asia/Jakarta",
    "Hong Kong": "Asia/Hong_Kong",
    "Tokyo": "Asia/Tokyo",
    "Sydney": "Australia/Sydney",
    "London": "Europe/London",
    "New York": "America/New_York",
}


@cache
def _lookup() -> tuple[dict[str, str], dict[str, str]]:
    """Return lower-case city names (e.g. 'new york') and full IANA names, each mapped to the IANA name."""
    cities, full = {}, {}
    for name in sorted(available_timezones()):
        full[name.lower()] = name
        # Only canonical "Region/City" names, so 'singapore' means Asia/Singapore
        # rather than the legacy 'Singapore' alias.
        if "/" in name and not name.startswith(("Etc/", "SystemV/", "US/")):
            cities.setdefault(name.rsplit("/", 1)[1].replace("_", " ").lower(), name)
    return cities, full


def resolve_timezone(text: str) -> str | None:
    """Return the IANA name for typed text such as 'London' or 'asia/tokyo'."""
    key = " ".join(text.strip().replace("_", " ").split()).lower()
    cities, full = _lookup()
    return cities.get(key) or full.get(key) or full.get(key.replace(" ", "_"))


def day_bounds(timezone_name: str, now_utc: datetime | None = None) -> tuple[datetime, datetime]:
    """Return today's local midnight-to-midnight span in UTC.

    Both midnights are built in local time before converting, so days with a
    daylight-saving change are not assumed to be exactly 24 hours long.
    """
    tz = ZoneInfo(timezone_name)
    local_now = (now_utc or datetime.now(timezone.utc)).astimezone(tz)
    start = datetime.combine(local_now.date(), time.min, tzinfo=tz)
    end = datetime.combine(local_now.date() + timedelta(days=1), time.min, tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
