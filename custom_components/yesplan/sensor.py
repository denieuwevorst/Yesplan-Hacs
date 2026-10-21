"""Sensors: next start (timestamp) and event counts for today / tomorrow / this week."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_LOCATIONS
from .coordinator import YesplanConfigEntry, YesplanCoordinator
from .entity import YesplanEntity
from .parsing import event_to_attrs, events_between, next_event, week_bounds


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
        entities.append(YesplanEventsTomorrowSensor(coordinator, entry, location))
        entities.append(YesplanEventsWeekSensor(coordinator, entry, location))
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


class YesplanEventsSensor(YesplanEntity, SensorEntity):
    """Number of events starting in a period; the list is in the `events` attribute."""

    # Event lists can be large; keep them out of the recorder database.
    _unrecorded_attributes = frozenset({"events"})
    _key = ""

    def __init__(
        self, coordinator: YesplanCoordinator, entry: YesplanConfigEntry, location: str
    ) -> None:
        super().__init__(coordinator, entry, location, self._key)

    def _period(self, today: date) -> tuple[date, date]:
        raise NotImplementedError

    @property
    def _selected(self) -> list[dict[str, Any]]:
        first, last = self._period(dt_util.now().date())
        return events_between(self._events, first, last, dt_util.as_local)

    @property
    def native_value(self) -> int:
        return len(self._selected)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"events": [event_to_attrs(e) for e in self._selected]}


class YesplanEventsTodaySensor(YesplanEventsSensor):
    _key = "events_today"

    def _period(self, today: date) -> tuple[date, date]:
        return today, today


class YesplanEventsTomorrowSensor(YesplanEventsSensor):
    _key = "events_tomorrow"

    def _period(self, today: date) -> tuple[date, date]:
        tomorrow = today + timedelta(days=1)
        return tomorrow, tomorrow


class YesplanEventsWeekSensor(YesplanEventsSensor):
    """Calendar week (Monday to Sunday) containing today."""

    _key = "events_week"

    def _period(self, today: date) -> tuple[date, date]:
        return week_bounds(today)
