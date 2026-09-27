"""Client for the internal API of the web app (#14 section 7).

The agent has no database credentials; everything it reads or writes goes
through these four calls. Bodies and answers are never logged: a request
holds name, date of birth and phone number.
"""

from __future__ import annotations

from typing import Any

import aiohttp

# A caller waits in silence meanwhile; better a clear "not now" than a pause.
TIMEOUT_SECONDS = 5.0
# Creating sends the mails within the same HTTP request (#7). A timeout
# after the commit would tell the caller "failed" for a stored request.
CREATE_TIMEOUT_SECONDS = 20.0


class ApiUnavailable(Exception):
    """No answer to rely on: not configured, not reachable, timeout, 5xx, 403, 404."""


class ApiRejected(Exception):
    """The API refused the input (400); `errors` maps fields to German messages."""

    def __init__(self, errors: dict[str, list[str]]):
        super().__init__("rejected")
        self.errors = errors


class ApiClient:
    def __init__(self, url: str, key: str) -> None:
        self.url = url.rstrip("/") + "/" if url else ""
        self._key = key

    @property
    def configured(self) -> bool:
        return bool(self.url and self._key)

    async def _call(
        self, method: str, path: str, body: dict | None = None, timeout=TIMEOUT_SECONDS
    ) -> dict[str, Any]:
        if not self.configured:
            raise ApiUnavailable("VOICE_API_URL oder VOICE_API_KEY fehlt")
        headers = {"Authorization": f"Bearer {self._key}"}
        try:
            async with (
                aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as http,
                http.request(method, self.url + path, json=body, headers=headers) as response,
            ):
                if response.status == 400:
                    data = await response.json()
                    raise ApiRejected(data.get("errors") or {})
                if response.status >= 300:
                    # Only the status: the body may echo what was sent.
                    raise ApiUnavailable(f"HTTP {response.status}")
                return await response.json()
        except (aiohttp.ClientError, TimeoutError, ValueError) as error:
            raise ApiUnavailable(type(error).__name__) from None

    async def _field(self, method: str, path: str, name: str, body=None, **kwargs) -> Any:
        data = await self._call(method, path, body, **kwargs)
        try:
            return data[name]
        except (KeyError, TypeError):
            raise ApiUnavailable(f"Antwort ohne {name}") from None

    async def practice_info(self) -> dict[str, str]:
        return await self._field("GET", "auskunft/", "topics")

    async def appointment_types(self) -> list[dict[str, Any]]:
        return await self._field("GET", "terminarten/", "types")

    async def check_time_window(self, day: str, part_of_day: str) -> dict[str, Any]:
        return await self._call("POST", "wunschzeit/", {"date": day, "part_of_day": part_of_day})

    async def create_request(self, data: dict[str, Any]) -> str:
        return await self._field(
            "POST", "anfragen/", "reference", data, timeout=CREATE_TIMEOUT_SECONDS
        )
