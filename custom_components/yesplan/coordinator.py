"""Data update coordinator."""

from __future__ import annotations

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
    CONF_DAYS_AHEAD,
    CONF_LOCATIONS,
    CONF_SCAN_INTERVAL,
    DEFAULT_DAYS_AHEAD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .parsing import fetch_days, group_by_location, week_bounds

_LOGGER = logging.getLogger(__name__)

# Days earlier in the current week rarely change, so cache them.
PAST_TTL = timedelta(hours=1)


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
        self._past: dict[date, tuple[datetime, list[dict[str, Any]]]] = {}

    async def _fetch_day(
        self, day: date, today: date, now: datetime
    ) -> list[dict[str, Any]]:
        """One day's events; days before today are cached and may fall back to stale data."""
        if day >= today:
            return await self._client.get_events(day)
        cached = self._past.get(day)
        if cached and now - cached[0] < PAST_TTL:
            return cached[1]
        try:
            events = await self._client.get_events(day)
        except YesplanConnectionError:
            return cached[1] if cached else []
        self._past[day] = (now, events)
        return events

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

        data = group_by_location(raw, self._locations)
        _LOGGER.debug(
            "Fetched %d raw events, per location: %s",
            len(raw),
            {k: len(v) for k, v in data.items()},
        )
        return data


type YesplanConfigEntry = ConfigEntry[YesplanCoordinator]
