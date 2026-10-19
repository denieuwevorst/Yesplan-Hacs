"""Binary sensor: is there an event running right now?"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_LOCATIONS
from .coordinator import YesplanConfigEntry, YesplanCoordinator
from .entity import YesplanEntity
from .parsing import active_event, event_to_attrs


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YesplanConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        YesplanActiveSensor(coordinator, entry, location)
        for location in entry.options.get(CONF_LOCATIONS, [])
    )


class YesplanActiveSensor(YesplanEntity, BinarySensorEntity):
    """On while an event is running in this location."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(
        self, coordinator: YesplanCoordinator, entry: YesplanConfigEntry, location: str
    ) -> None:
        super().__init__(coordinator, entry, location, "active")

    @property
    def _active(self) -> dict[str, Any] | None:
        return active_event(self._events, dt_util.utcnow())

    @property
    def is_on(self) -> bool:
        return self._active is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        event = self._active
        return event_to_attrs(event) if event else {}
