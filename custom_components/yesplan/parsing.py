"""Pure helper functions (no Home Assistant imports, easy to test)."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from collections.abc import Callable
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


MAX_CUSTOM_FIELDS = 20


def normalize_keywords(values: Any, limit: int = MAX_CUSTOM_FIELDS) -> list[str]:
    """Clean user input: accepts a list or text, splits on commas/spaces, de-duplicates."""
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    out: list[str] = []
    for value in values:
        for part in re.split(r"[,\s]+", str(value)):
            if part and part not in out:
                out.append(part)
    return out[:limit]


def format_value(value: Any) -> str | None:
    """Readable text for any Yesplan custom data value; None if empty/not displayable."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else str(value)
    if isinstance(value, list):  # checkboxes, labels, resource fields
        return ", ".join(p for p in (format_value(i) for i in value) if p) or None
    if isinstance(value, dict):  # contact / resource booking / attachment
        for key in ("name", "contact", "resource", "comment", "dataurl"):
            if key in value:
                text = format_value(value[key])
                if text:
                    return text
    return None


def parse_custom(raw: dict[str, Any], keys: list[str] | None) -> list[dict[str, str]]:
    """The configured custom data fields of an event, in the configured order.

    Uses the field's own name from Yesplan as label and skips empty values.
    """
    if not keys:
        return []
    by_keyword = {
        item.get("keyword"): item
        for item in raw.get("customdata") or []
        if isinstance(item, dict)
    }
    rows: list[dict[str, str]] = []
    for keyword in keys:
        item = by_keyword.get(keyword)
        value = format_value(item.get("value")) if item else None
        if value is not None:
            rows.append(
                {"keyword": keyword, "name": item.get("name") or keyword, "value": value}
            )
    return rows


def _int(value: Any) -> int | None:
    """'144' / 144 / '144.0' -> 144; empty or non-numeric -> None."""
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return int(float(str(value).strip().replace(",", ".")))
    except ValueError:
        return None


def parse_tickets(
    raw: dict[str, Any], keys: dict[str, str] | None
) -> dict[str, int | None] | None:
    """Ticket sales from the event's `customdata` list.

    `keys` maps capacity/sold/available to custom data keywords. An event without
    a capacity is not ticketed, so there is nothing to report.
    """
    if not keys:
        return None
    values = {
        item.get("keyword"): item.get("value") for item in raw.get("customdata") or []
    }
    get = lambda name: _int(values.get(keys[name])) if keys.get(name) else None  # noqa: E731
    capacity = get("capacity")
    if capacity is None:
        return None
    sold = get("sold")
    available = get("available")
    if available is None and sold is not None:
        available = max(capacity - sold, 0)
    return {"capacity": capacity, "sold": sold, "available": available}


def parse_event(
    raw: dict[str, Any],
    ticket_keys: dict[str, str] | None = None,
    custom_keys: list[str] | None = None,
) -> dict[str, Any] | None:
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

    event = {
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
    tickets = parse_tickets(raw, ticket_keys)
    if tickets is not None:
        event["tickets"] = tickets
    custom = parse_custom(raw, custom_keys)
    if custom:
        event["custom"] = custom
    return event


def group_by_location(
    raw_events: list[dict[str, Any]],
    locations: list[str],
    ticket_keys: dict[str, str] | None = None,
    custom_keys: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Parse, de-duplicate by id and group per configured location."""
    parsed: dict[str, dict[str, Any]] = {}
    for raw in raw_events:
        event = parse_event(raw, ticket_keys, custom_keys)
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


_MARK = re.compile(r"\s*\((start|stop)\)\s*$", re.IGNORECASE)


def parse_schedule(entries: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Turn Yesplan schedule entries into rows.

    Yesplan lists "<label> (start)" and "<label> (stop)" as separate entries;
    those are merged into one row with a start and an end. Entries without a
    marker (e.g. "Zaal dicht") become single-time rows.
    """
    rows: list[dict[str, Any]] = []
    open_: dict[str, list[datetime]] = {}
    for raw in entries or []:
        start = _dt(raw.get("starttime"))
        text = (raw.get("description") or "").strip()
        if start is None or not text:
            continue
        marker = _MARK.search(text)
        label = text[: marker.start()].strip() if marker else text
        kind = marker.group(1).lower() if marker else None
        if kind == "start":
            open_.setdefault(label, []).append(start)
        elif kind == "stop" and open_.get(label):
            rows.append({"start": open_[label].pop(0), "end": start, "label": label})
        else:
            rows.append({"start": start, "end": None, "label": label})
    for label, starts in open_.items():  # a start that never got a stop
        rows.extend({"start": st, "end": None, "label": label} for st in starts)
    rows.sort(key=lambda r: (r["start"], r["end"] or r["start"]))
    return rows


def event_to_attrs(event: dict[str, Any], schedule: bool = False) -> dict[str, Any]:
    """JSON-serialisable view of an event for entity attributes."""
    attrs: dict[str, Any] = {
        "id": event["id"],
        "name": event["name"],
        "start": event["start"].isoformat(),
        "end": event["end"].isoformat() if event["end"] else None,
        "status": event["status"],
        "profile": event["profile"],
    }
    if "tickets" in event:
        attrs["tickets"] = dict(event["tickets"])
    if "custom" in event:
        attrs["custom"] = [dict(row) for row in event["custom"]]
    if schedule and "schedule" in event:
        attrs["schedule"] = [
            {
                "start": r["start"].isoformat(),
                "end": r["end"].isoformat() if r["end"] else None,
                "label": r["label"],
            }
            for r in event["schedule"]
        ]
    return attrs


def week_bounds(today: date) -> tuple[date, date]:
    """Monday and Sunday of the calendar week containing `today`."""
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


def fetch_days(today: date, days_ahead: int) -> list[date]:
    """Days to request: the whole current week, plus enough to cover tomorrow
    and `days_ahead` days (matters on Sundays and with a long look-ahead)."""
    start, week_end = week_bounds(today)
    last = max(week_end, today + timedelta(days=max(days_ahead, 2) - 1))
    return [start + timedelta(days=i) for i in range((last - start).days + 1)]


def events_between(
    events: list[dict[str, Any]],
    first: date,
    last: date,
    to_local: Callable[[datetime], datetime] = lambda d: d,
) -> list[dict[str, Any]]:
    """Events whose (local) start date lies within first..last inclusive."""
    return [e for e in events if first <= to_local(e["start"]).date() <= last]
