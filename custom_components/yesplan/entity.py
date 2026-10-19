"""Base entity: one HA device per Yesplan location."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import YesplanConfigEntry, YesplanCoordinator


class YesplanEntity(CoordinatorEntity[YesplanCoordinator]):
    """Entity bound to one location."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: YesplanCoordinator,
        entry: YesplanConfigEntry,
        location: str,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._location = location
        slug = slugify(location)
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_{slug}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{slug}")},
            name=location,
            manufacturer="Yesplan",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def _events(self) -> list[dict[str, Any]]:
        return (self.coordinator.data or {}).get(self._location, [])

    async def async_added_to_hass(self) -> None:
        """Re-evaluate every minute so start/end times are hit without polling."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_interval(self.hass, self._tick, timedelta(minutes=1))
        )

    @callback
    def _tick(self, _now: datetime) -> None:
        self.async_write_ha_state()
