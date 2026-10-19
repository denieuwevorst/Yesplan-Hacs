"""Pure helper functions (no Home Assistant imports, easy to test)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

EXCLUDED_STATUSES = {"geannuleerd", "cancelled", "canceled"}


def normalize_base_url(url: str) -> str:
    """Return the installation root, without trailing slash or /api."""
    url = url.strip().rstrip("/")
    if url.lower().endswith("/api"):
        url = url[:-4]
    if not url.lower().startswith(("http://", "https://")):
        url = f"https://{url}"
    return url.rstrip("/")


def _dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def parse_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Reduce a Yesplan event to the fields we use.

    Performance time = defaultschedulestart/-end, falling back to the
    booking's starttime/endtime when no default schedule is set.
    """
    status = (raw.get("status") or {}).get("name") or ""
    if status.lower() in EXCLUDED_STATUSES:
        return None

    start = _dt(raw.get("defaultschedulestart")) or _dt(raw.get("starttime"))
    if start is None or not raw.get("id"):
        return None

    end = _dt(raw.get("defaultscheduleend")) or _dt(raw.get("endtime"))
    if end is not None and end < start:
        end = None

    return {
        "id": raw["id"],
        "name": raw.get("name") or "",
        "start": start,
        "end": end,
        "status": status,
        "profile": (raw.get("profile") or {}).get("name") or "",
        "locations": [
            loc["name"] for loc in raw.get("locations") or [] if loc.get("name")
        ],
    }


def group_by_location(
    raw_events: list[dict[str, Any]], locations: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Parse, de-duplicate by id and group per configured location."""
    parsed: dict[str, dict[str, Any]] = {}
    for raw in raw_events:
        event = parse_event(raw)
        if event:
            parsed[event["id"]] = event

    result: dict[str, list[dict[str, Any]]] = {loc: [] for loc in locations}
    for event in parsed.values():
        for loc in event["locations"]:
            if loc in result:
                result[loc].append(event)
    for events in result.values():
        events.sort(key=lambda e: e["start"])
    return result


def next_event(events: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    """First event that has not started yet."""
    return next((e for e in events if e["start"] > now), None)


def active_event(events: list[dict[str, Any]], now: datetime) -> dict[str, Any] | None:
    """First event that is running right now."""
    return next(
        (e for e in events if e["start"] <= now and e["end"] and now < e["end"]),
        None,
    )


def event_to_attrs(event: dict[str, Any]) -> dict[str, Any]:
    """JSON-serialisable view of an event for entity attributes."""
    return {
        "id": event["id"],
        "name": event["name"],
        "start": event["start"].isoformat(),
        "end": event["end"].isoformat() if event["end"] else None,
        "status": event["status"],
        "profile": event["profile"],
    }
