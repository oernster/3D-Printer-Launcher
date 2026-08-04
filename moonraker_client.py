"""The one async Moonraker client used by every bundled dashboard.

Separate from :mod:`moonraker` because this module needs ``aiohttp``, which
the launcher itself has no reason to import. The bundled tools run as their
own processes out of the shared virtualenv, so they all have it.
"""

from __future__ import annotations

import logging

import aiohttp

from moonraker import display_host, swap_scheme

logger = logging.getLogger(__name__)

# Total seconds allowed for one Moonraker query. The dashboards poll on a
# short cycle and show the previous reading on failure, so waiting longer
# costs responsiveness without buying reliability.
REQUEST_TIMEOUT_SECONDS = 2.0

# A longer allowance for the one-off connectivity probe at startup.
PROBE_TIMEOUT_SECONDS = 5.0

# Payload that asks Moonraker for nothing, used purely to check reachability.
EMPTY_QUERY: dict[str, dict] = {"objects": {}}

HTTPS_SCHEME_PREFIX = "https://"


def _connector_for(url: str) -> aiohttp.TCPConnector | None:
    """Disable certificate checks for https only.

    Moonraker behind a reverse proxy is routinely self-signed. This affects
    the local printer connection only, never anything on the internet.
    """

    if url.lower().startswith(HTTPS_SCHEME_PREFIX):
        return aiohttp.TCPConnector(ssl=False)
    return None


class MoonrakerClient:
    """Posts object queries to Moonraker, with a one-step scheme fallback."""

    def __init__(self, api_url: str) -> None:
        self.api_url = api_url
        # Remembers the URL that last worked so later polls skip the retry.
        self._working_url = api_url

    @property
    def host_label(self) -> str:
        """Short "host:port" label for display in a dashboard template."""

        return display_host(self.api_url)

    def candidate_urls(self) -> list[str]:
        """Every URL worth trying, best first, with duplicates removed."""

        ordered = (
            self._working_url,
            self.api_url,
            swap_scheme(self._working_url),
            swap_scheme(self.api_url),
        )

        urls: list[str] = []
        for url in ordered:
            if url and url not in urls:
                urls.append(url)
        return urls

    async def query(
        self, objects: dict, timeout: float = REQUEST_TIMEOUT_SECONDS
    ) -> dict | None:
        """Query Moonraker objects, returning ``None`` if nothing answered."""

        return await self._post({"objects": objects}, timeout)

    async def _post(self, payload: dict, timeout: float) -> dict | None:
        tried: list[str] = []
        last_error: Exception | None = None

        for url in self.candidate_urls():
            tried.append(url)
            try:
                client_timeout = aiohttp.ClientTimeout(total=timeout)
                async with (
                    aiohttp.ClientSession(
                        connector=_connector_for(url), timeout=client_timeout
                    ) as session,
                    session.post(url, json=payload) as response,
                ):
                    response.raise_for_status()
                    data = await response.json()
            except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
                last_error = exc
                continue

            self._working_url = url
            return data

        logger.error(
            "Moonraker query failed for %s; last error was %r", tried, last_error
        )
        return None

    async def probe(self, timeout: float = PROBE_TIMEOUT_SECONDS) -> bool:
        """Best-effort reachability check, logged but never fatal.

        A timeout counts as reachable: a printer that is merely slow to wake
        should still get a dashboard, which fills in once it answers.
        """

        try:
            client_timeout = aiohttp.ClientTimeout(total=timeout)
            async with (
                aiohttp.ClientSession(
                    connector=_connector_for(self.api_url), timeout=client_timeout
                ) as session,
                session.post(self.api_url, json=EMPTY_QUERY) as response,
            ):
                response.raise_for_status()
                return True
        except TimeoutError:
            logger.warning(
                "Moonraker probe timed out for %s; starting the dashboard anyway",
                self.api_url,
            )
            return True
        except (aiohttp.ClientError, ValueError):
            logger.error("Moonraker probe failed for %s", self.api_url, exc_info=True)
            return False


def status_of(data: dict | None) -> dict:
    """Pull the status mapping out of a Moonraker response.

    Every response shape this project does not recognise collapses to an
    empty mapping, so callers can use ``.get`` without further guarding.
    """

    if not isinstance(data, dict):
        return {}
    result = data.get("result")
    if not isinstance(result, dict):
        return {}
    status = result.get("status")
    return status if isinstance(status, dict) else {}
