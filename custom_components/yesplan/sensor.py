"""Sensors: next start (timestamp) and number of events today."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_LOCATIONS
from .coordinator import YesplanConfigEntry, YesplanCoordinator
from .entity import YesplanEntity
from .parsing import event_to_attrs, next_event


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YesplanConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for location in entry.options.get(CONF_LOCATIONS, []):
        entities.append(YesplanNextStartSensor(coordinator, entry, location))
        entities.append(YesplanEventsTodaySensor(coordinator, entry, location))
    async_add_entities(entities)


class YesplanNextStartSensor(YesplanEntity, SensorEntity):
    """Start time of the next event that has not begun yet."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, coordinator: YesplanCoordinator, entry: YesplanConfigEntry, location: str
    ) -> None:
        super().__init__(coordinator, entry, location, "next_start")

    @property
    def _next(self) -> dict[str, Any] | None:
        return next_event(self._events, dt_util.utcnow())

    @property
    def native_value(self):
        event = self._next
        return event["start"] if event else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        event = self._next
        return event_to_attrs(event) if event else {}


class YesplanEventsTodaySensor(YesplanEntity, SensorEntity):
    """Number of events that start today."""

    def __init__(
        self, coordinator: YesplanCoordinator, entry: YesplanConfigEntry, location: str
    ) -> None:
        super().__init__(coordinator, entry, location, "events_today")

    @property
    def _today(self) -> list[dict[str, Any]]:
        today = dt_util.now().date()
        return [
            e for e in self._events if dt_util.as_local(e["start"]).date() == today
        ]

    @property
    def native_value(self) -> int:
        return len(self._today)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"events": [event_to_attrs(e) for e in self._today]}
