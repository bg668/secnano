"""
Timezone conversion utilities.
"""

from __future__ import annotations

from datetime import datetime, timezone


def format_local_time(utc_iso: str, tz_name: str = "UTC") -> str:
    """
    Convert a UTC ISO-8601 string to a human-readable local time string.

    Args:
        utc_iso: An ISO-8601 timestamp, e.g. ``"2024-01-15T10:30:00Z"`` or
                 ``"2024-01-15T10:30:00+00:00"``.
        tz_name: IANA timezone name, e.g. ``"America/New_York"``. Defaults to UTC.

    Returns:
        A formatted datetime string such as ``"2024-01-15 05:30:00 EST"``.
    """
    try:
        # Parse the UTC timestamp
        ts = utc_iso.replace("Z", "+00:00")
        dt_utc = datetime.fromisoformat(ts)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)

        # Convert to target timezone
        try:
            from zoneinfo import ZoneInfo  # Python 3.9+

            target_tz = ZoneInfo(tz_name)
        except (ImportError, KeyError):
            target_tz = timezone.utc

        dt_local = dt_utc.astimezone(target_tz)
        return dt_local.strftime("%Y-%m-%d %H:%M:%S %Z")
    except (ValueError, TypeError):
        return utc_iso
