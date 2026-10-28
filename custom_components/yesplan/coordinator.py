"""Data update coordinator."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import YesplanAuthError, YesplanClient, YesplanConnectionError, YesplanError
from .const import (
    CONF_CUSTOM_FIELDS,
    CONF_DAYS_AHEAD,
    CONF_LOCATIONS,
    CONF_SCAN_INTERVAL,
    CONF_TICKET_AVAILABLE,
    CONF_TICKET_CAPACITY,
    CONF_TICKET_SOLD,
    DEFAULT_DAYS_AHEAD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .parsing import (
    events_between,
    fetch_days,
    group_by_location,
    normalize_keywords,
    parse_schedule,
    week_bounds,
)

_LOGGER = logging.getLogger(__name__)

# Days earlier in the current week rarely change, so cache them.
PAST_TTL = timedelta(hours=1)

# Schedules are one request per event of today; keep that polite.
SCHEDULE_CONCURRENCY = 5


class YesplanCoordinator(DataUpdateCoordinator[dict[str, list[dict[str, Any]]]]):
    """Fetches events for the next N days, grouped per location."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: YesplanClient
    ) -> None:
        minutes = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(minutes=minutes),
        )
        self._client = client
        self._locations: list[str] = list(entry.options.get(CONF_LOCATIONS, []))
        self._days = int(entry.options.get(CONF_DAYS_AHEAD, DEFAULT_DAYS_AHEAD))
        self._ticket_keys: dict[str, str] = {
            name: str(entry.options.get(conf, "")).strip()
            for name, conf in (
                ("capacity", CONF_TICKET_CAPACITY),
                ("sold", CONF_TICKET_SOLD),
                ("available", CONF_TICKET_AVAILABLE),
            )
            if str(entry.options.get(conf, "")).strip()
        }
        # Without a capacity field there is nothing to report on ticket sales.
        if "capacity" not in self._ticket_keys:
            self._ticket_keys = {}
        self._custom_keys: list[str] = normalize_keywords(
            entry.options.get(CONF_CUSTOM_FIELDS)
        )
        # Everything we want from the custom data, asked in the same request.
        self._keywords: list[str] = list(
            dict.fromkeys([*self._ticket_keys.values(), *self._custom_keys])
        )
        self._past: dict[date, tuple[datetime, list[dict[str, Any]]]] = {}
        self._schedules: dict[str, list[dict[str, Any]]] = {}

    async def _fetch_day(
        self, day: date, today: date, now: datetime
    ) -> list[dict[str, Any]]:
        """One day's events; days before today are cached and may fall back to stale data."""
        if day >= today:
            return await self._client.get_events(day, self._keywords)
        cached = self._past.get(day)
        if cached and now - cached[0] < PAST_TTL:
            return cached[1]
        try:
            events = await self._client.get_events(day, self._keywords)
        except YesplanConnectionError:
            return cached[1] if cached else []
        self._past[day] = (now, events)
        return events

    async def _attach_schedules(
        self, data: dict[str, list[dict[str, Any]]], today: date
    ) -> None:
        """Fetch the schedule of every event that starts today.

        Event dicts are shared between locations, so setting the schedule once is
        enough. A failing request keeps the last known schedule instead of breaking
        the update.
        """
        todays: dict[str, dict[str, Any]] = {}
        for events in data.values():
            for event in events_between(events, today, today, dt_util.as_local):
                todays[event["id"]] = event

        semaphore = asyncio.Semaphore(SCHEDULE_CONCURRENCY)

        async def fetch(event: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
            async with semaphore:
                try:
                    entries = await self._client.get_schedule(event["id"])
                except YesplanAuthError:
                    raise
                except YesplanError as err:
                    _LOGGER.debug("No schedule for %s: %s", event["id"], err)
                    return event["id"], self._schedules.get(event["id"], [])
            return event["id"], parse_schedule(entries)

        results = await asyncio.gather(*(fetch(e) for e in todays.values()))
        self._schedules = dict(results)  # also drops schedules of past days
        for event_id, rows in results:
            todays[event_id]["schedule"] = rows

    async def _async_update_data(self) -> dict[str, list[dict[str, Any]]]:
        today = dt_util.now().date()
        now = dt_util.utcnow()
        raw: list[dict[str, Any]] = []
        try:
            # The API only supports one day per date query, so one request per day.
            for day in fetch_days(today, self._days):
                raw.extend(await self._fetch_day(day, today, now))
        except YesplanAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except YesplanError as err:
            raise UpdateFailed(f"Error talking to Yesplan: {err}") from err

        week_start, _ = week_bounds(today)
        self._past = {d: v for d, v in self._past.items() if d >= week_start}

        data = group_by_location(raw, self._locations, self._ticket_keys, self._custom_keys)
        try:
            await self._attach_schedules(data, today)
        except YesplanAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        _LOGGER.debug(
            "Fetched %d raw events, per location: %s",
            len(raw),
            {k: len(v) for k, v in data.items()},
        )
        return data


type YesplanConfigEntry = ConfigEntry[YesplanCoordinator]
