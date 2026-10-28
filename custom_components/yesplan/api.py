"""Minimal async client for the Yesplan REST API."""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import aiohttp

from .parsing import normalize_base_url

_LOGGER = logging.getLogger(__name__)

MAX_PAGES = 20


class YesplanError(Exception):
    """Base error."""


class YesplanAuthError(YesplanError):
    """API key rejected."""


class YesplanConnectionError(YesplanError):
    """Could not reach Yesplan."""


class YesplanRequestError(YesplanConnectionError):
    """Yesplan answered with a client error (4xx) for this request."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


class YesplanClient:
    """Talks to https://<installation>.yesplan.nl/api."""

    def __init__(
        self, session: aiohttp.ClientSession, base_url: str, api_key: str
    ) -> None:
        self._session = session
        self._api = f"{normalize_base_url(base_url)}/api"
        self._api_key = api_key

    async def _get(
        self, url: str, extra: dict[str, str] | None = None
    ) -> dict[str, Any]:
        try:
            async with self._session.get(
                url,
                params={**(extra or {}), "api_key": self._api_key},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (401, 403):
                    raise YesplanAuthError("API key rejected")
                if resp.status == 429:
                    raise YesplanConnectionError("Rate limited by Yesplan")
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except aiohttp.ClientResponseError as err:
            if 400 <= err.status < 500:
                raise YesplanRequestError(err.status, str(err)) from err
            raise YesplanConnectionError(str(err)) from err
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise YesplanConnectionError(str(err)) from err

    async def _get_all(
        self, url: str, extra: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        """Follow pagination.next until exhausted."""
        items: list[dict[str, Any]] = []
        next_url: str | None = url
        for _ in range(MAX_PAGES):
            data = await self._get(next_url, extra)
            items.extend(data.get("data") or [])
            next_url = (data.get("pagination") or {}).get("next")
            if not next_url:
                break
        return items

    async def get_events(
        self, day: date, keywords: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """All events planned on one day (date format dd-mm-yyyy).

        `keywords` are custom data fields to include with every event
        (documented variation: ?customdata_keywords=a,b,c). If Yesplan rejects
        the request because of them, retry without so the agenda keeps working.
        """
        url = f"{self._api}/events/date:{day:%d-%m-%Y}"
        if keywords:
            try:
                return await self._get_all(
                    url, {"customdata_keywords": ",".join(keywords)}
                )
            except YesplanRequestError as err:
                _LOGGER.warning(
                    "Yesplan rejected the ticket fields %s (HTTP %s); continuing "
                    "without ticket sales. Check the field names in the options.",
                    keywords,
                    err.status,
                )
        return await self._get_all(url)

    async def rejected_keywords(self, day: date, keywords: list[str]) -> list[str]:
        """Keywords Yesplan refuses (4xx) for an events query; empty list if all are fine.

        Checks them together first, then one by one to find the culprits.
        """
        url = f"{self._api}/events/date:{day:%d-%m-%Y}"
        try:
            await self._get(url, {"customdata_keywords": ",".join(keywords)})
            return []
        except YesplanRequestError:
            pass
        bad: list[str] = []
        for keyword in keywords:
            try:
                await self._get(url, {"customdata_keywords": keyword})
            except YesplanRequestError:
                bad.append(keyword)
        return bad or list(keywords)

    async def get_locations(self) -> list[str]:
        """Names of all locations (also validates URL + key)."""
        items = await self._get_all(f"{self._api}/locations")
        return sorted({i["name"] for i in items if i.get("name")})

    async def get_schedule(self, event_id: str) -> list[dict[str, Any]]:
        """Schedule entries of one event (start/stop lines, "Zaal dicht", ...)."""
        data = await self._get(f"{self._api}/event/{event_id}/schedule")
        return data.get("entries") or []
