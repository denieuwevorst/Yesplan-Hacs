"""Data update coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import YesplanAuthError, YesplanClient, YesplanError
from .const import (
    CONF_DAYS_AHEAD,
    CONF_LOCATIONS,
    CONF_SCAN_INTERVAL,
    DEFAULT_DAYS_AHEAD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .parsing import group_by_location

_LOGGER = logging.getLogger(__name__)


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

    async def _async_update_data(self) -> dict[str, list[dict[str, Any]]]:
        today = dt_util.now().date()
        raw: list[dict[str, Any]] = []
        try:
            # The API only supports one day per date query, so one request per day.
            for offset in range(self._days):
                raw.extend(await self._client.get_events(today + timedelta(days=offset)))
        except YesplanAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except YesplanError as err:
            raise UpdateFailed(f"Error talking to Yesplan: {err}") from err

        data = group_by_location(raw, self._locations)
        _LOGGER.debug(
            "Fetched %d raw events, per location: %s",
            len(raw),
            {k: len(v) for k, v in data.items()},
        )
        return data


type YesplanConfigEntry = ConfigEntry[YesplanCoordinator]
