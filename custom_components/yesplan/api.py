"""Minimal async client for the Yesplan REST API."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import aiohttp

from .parsing import normalize_base_url

MAX_PAGES = 20


class YesplanError(Exception):
    """Base error."""


class YesplanAuthError(YesplanError):
    """API key rejected."""


class YesplanConnectionError(YesplanError):
    """Could not reach Yesplan."""


class YesplanClient:
    """Talks to https://<installation>.yesplan.nl/api."""

    def __init__(
        self, session: aiohttp.ClientSession, base_url: str, api_key: str
    ) -> None:
        self._session = session
        self._api = f"{normalize_base_url(base_url)}/api"
        self._api_key = api_key

    async def _get(self, url: str) -> dict[str, Any]:
        try:
            async with self._session.get(
                url,
                params={"api_key": self._api_key},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (401, 403):
                    raise YesplanAuthError("API key rejected")
                if resp.status == 429:
                    raise YesplanConnectionError("Rate limited by Yesplan")
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise YesplanConnectionError(str(err)) from err

    async def _get_all(self, url: str) -> list[dict[str, Any]]:
        """Follow pagination.next until exhausted."""
        items: list[dict[str, Any]] = []
        next_url: str | None = url
        for _ in range(MAX_PAGES):
            data = await self._get(next_url)
            items.extend(data.get("data") or [])
            next_url = (data.get("pagination") or {}).get("next")
            if not next_url:
                break
        return items

    async def get_events(self, day: date) -> list[dict[str, Any]]:
        """All events planned on one day (date format dd-mm-yyyy)."""
        return await self._get_all(f"{self._api}/events/date:{day:%d-%m-%Y}")

    async def get_locations(self) -> list[str]:
        """Names of all locations (also validates URL + key)."""
        items = await self._get_all(f"{self._api}/locations")
        return sorted({i["name"] for i in items if i.get("name")})
