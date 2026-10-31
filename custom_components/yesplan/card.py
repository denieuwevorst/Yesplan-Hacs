"""Serve the Lovelace card and keep a matching Lovelace resource registered."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_URL = f"/{DOMAIN}_static/yesplan-card.js"
_RESOURCE = {"res_type": "module"}


def _resources(hass: HomeAssistant) -> Any | None:
    """Lovelace resource collection; attribute in newer HA, dict key in older."""
    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None)
    if resources is None and isinstance(lovelace, dict):
        resources = lovelace.get("resources")
    return resources


def _ours(item: dict[str, Any]) -> bool:
    return str(item.get("url", "")).split("?")[0] == CARD_URL


async def _manageable(resources: Any) -> bool:
    """True for storage-mode dashboards; YAML-mode resources are read-only."""
    if resources is None or not hasattr(resources, "async_create_item"):
        return False
    if not getattr(resources, "loaded", True):
        await resources.async_load()
        resources.loaded = True
    return True


async def async_ensure_resource(hass: HomeAssistant, version: str) -> None:
    """Create or update the Lovelace resource. Never raises."""
    try:
        resources = _resources(hass)
        if not await _manageable(resources):
            _LOGGER.debug("Lovelace resources are not editable here (YAML mode?); skipping")
            return

        wanted = f"{CARD_URL}?v={version}"
        existing = [i for i in resources.async_items() if _ours(i)]
        if not existing:
            await resources.async_create_item({**_RESOURCE, "url": wanted})
            _LOGGER.info("Added Lovelace resource %s", wanted)
            return
        for item in existing:
            if item.get("url") != wanted:
                await resources.async_update_item(item["id"], {**_RESOURCE, "url": wanted})
                _LOGGER.info("Updated Lovelace resource to %s", wanted)
    except Exception:  # noqa: BLE001
        _LOGGER.warning("Could not register the Lovelace resource", exc_info=True)


async def async_remove_resource(hass: HomeAssistant) -> None:
    """Remove our Lovelace resource. Never raises."""
    try:
        resources = _resources(hass)
        if not await _manageable(resources):
            return
        for item in [i for i in resources.async_items() if _ours(i)]:
            await resources.async_delete_item(item["id"])
            _LOGGER.info("Removed Lovelace resource %s", item.get("url"))
    except Exception:  # noqa: BLE001
        _LOGGER.warning("Could not remove the Lovelace resource", exc_info=True)


async def async_setup_card(hass: HomeAssistant, version: str) -> None:
    """Serve the JS file, load it as extra module, and add the dashboard resource."""
    card_path = Path(__file__).parent / "frontend" / "yesplan-card.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card_path), cache_headers=False)]
    )
    add_extra_js_url(hass, f"{CARD_URL}?v={version}")

    async def _register(_hass: HomeAssistant) -> None:
        await async_ensure_resource(hass, version)

    # Wait until HA has started so the Lovelace resource collection exists.
    async_at_started(hass, _register)
