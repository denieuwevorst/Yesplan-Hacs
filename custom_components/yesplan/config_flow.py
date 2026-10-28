"""Config flow: URL + key, then pick locations from the list Yesplan returns."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)
from homeassistant.util import dt as dt_util

from .api import YesplanAuthError, YesplanClient, YesplanConnectionError, YesplanError
from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
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
from .parsing import normalize_base_url, normalize_keywords

_LOGGER = logging.getLogger(__name__)


def _options_schema(
    locations: list[str], defaults: dict[str, Any], extras: bool = False
) -> vol.Schema:
    fields: dict[Any, Any] = {
        vol.Required(
            CONF_LOCATIONS, default=defaults.get(CONF_LOCATIONS, [])
        ): SelectSelector(
            SelectSelectorConfig(
                options=locations,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(
            CONF_DAYS_AHEAD,
            default=defaults.get(CONF_DAYS_AHEAD, DEFAULT_DAYS_AHEAD),
        ): NumberSelector(
            NumberSelectorConfig(min=1, max=14, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Required(
            CONF_SCAN_INTERVAL,
            default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        ): NumberSelector(
            NumberSelectorConfig(
                min=5,
                max=120,
                step=1,
                unit_of_measurement="min",
                mode=NumberSelectorMode.BOX,
            )
        ),
    }
    if extras:
        # suggested_value (not default) so a field can really be cleared in the form
        for conf in (CONF_TICKET_CAPACITY, CONF_TICKET_SOLD, CONF_TICKET_AVAILABLE):
            fields[
                vol.Optional(conf, description={"suggested_value": defaults.get(conf, "")})
            ] = str
        fields[
            vol.Optional(
                CONF_CUSTOM_FIELDS,
                description={"suggested_value": list(defaults.get(CONF_CUSTOM_FIELDS, []))},
            )
        ] = TextSelector(TextSelectorConfig(multiple=True))
    return vol.Schema(fields)


def _clean_options(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_LOCATIONS: list(user_input[CONF_LOCATIONS]),
        CONF_DAYS_AHEAD: int(user_input[CONF_DAYS_AHEAD]),
        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
        CONF_TICKET_CAPACITY: str(user_input.get(CONF_TICKET_CAPACITY, "")).strip(),
        CONF_TICKET_SOLD: str(user_input.get(CONF_TICKET_SOLD, "")).strip(),
        CONF_TICKET_AVAILABLE: str(user_input.get(CONF_TICKET_AVAILABLE, "")).strip(),
        CONF_CUSTOM_FIELDS: normalize_keywords(user_input.get(CONF_CUSTOM_FIELDS)),
    }


def _requested_keywords(options: dict[str, Any]) -> list[str]:
    """Every custom data field the options would make us ask Yesplan for."""
    return list(
        dict.fromkeys(
            [
                *(
                    options[conf]
                    for conf in (CONF_TICKET_CAPACITY, CONF_TICKET_SOLD, CONF_TICKET_AVAILABLE)
                    if options.get(conf)
                ),
                *options.get(CONF_CUSTOM_FIELDS, []),
            ]
        )
    )


class YesplanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Yesplan."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._locations: list[str] = []

    async def _try_connect(
        self, base_url: str, api_key: str, errors: dict[str, str]
    ) -> list[str] | None:
        client = YesplanClient(async_get_clientsession(self.hass), base_url, api_key)
        try:
            return await client.get_locations()
        except YesplanAuthError:
            errors["base"] = "invalid_auth"
        except YesplanConnectionError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error connecting to Yesplan")
            errors["base"] = "unknown"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            base = normalize_base_url(user_input[CONF_BASE_URL])
            locations = await self._try_connect(base, user_input[CONF_API_KEY], errors)
            if locations is not None:
                await self.async_set_unique_id(base)
                self._abort_if_unique_id_configured()
                self._data = {
                    CONF_BASE_URL: base,
                    CONF_API_KEY: user_input[CONF_API_KEY],
                }
                self._locations = locations
                return await self.async_step_locations()

        schema = vol.Schema(
            {vol.Required(CONF_BASE_URL): str, vol.Required(CONF_API_KEY): str}
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_locations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=urlparse(self._data[CONF_BASE_URL]).hostname
                or self._data[CONF_BASE_URL],
                data=self._data,
                options=_clean_options(user_input),
            )
        return self.async_show_form(
            step_id="locations", data_schema=_options_schema(self._locations, {})
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            ok = await self._try_connect(
                entry.data[CONF_BASE_URL], user_input[CONF_API_KEY], errors
            )
            if ok is not None:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return YesplanOptionsFlow()


class YesplanOptionsFlow(OptionsFlow):
    """Change locations, refresh settings, ticket fields and extra custom data fields."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self.config_entry
        client = YesplanClient(
            async_get_clientsession(self.hass),
            entry.data[CONF_BASE_URL],
            entry.data[CONF_API_KEY],
        )
        errors: dict[str, str] = {}
        invalid = ""
        defaults: dict[str, Any] = dict(entry.options)

        if user_input is not None:
            options = _clean_options(user_input)
            bad = await self._rejected(client, _requested_keywords(options))
            if not bad:
                return self.async_create_entry(data=options)
            _LOGGER.warning("Yesplan rejected these custom data fields: %s", bad)
            errors["base"] = "invalid_fields"
            invalid = "\n\n⚠ " + ", ".join(bad)
            defaults = options  # keep what the user typed

        try:
            available = await client.get_locations()
        except (YesplanAuthError, YesplanConnectionError):
            available = []
        locations = sorted(
            set(available) | set(defaults.get(CONF_LOCATIONS, entry.options.get(CONF_LOCATIONS, [])))
        )
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(locations, defaults, extras=True),
            errors=errors,
            description_placeholders={"invalid": invalid},
        )

    @staticmethod
    async def _rejected(client: YesplanClient, keywords: list[str]) -> list[str]:
        """Names Yesplan refuses. If Yesplan cannot be reached, do not block saving."""
        if not keywords:
            return []
        try:
            return await client.rejected_keywords(dt_util.now().date(), keywords)
        except YesplanError:
            return []
