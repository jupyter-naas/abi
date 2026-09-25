from __future__ import annotations

from typing import Any

from naas_abi_sdk.services._codec import ServiceProxy


class SecretService(ServiceProxy):
    domain = "secret"

    async def get(self, key: str, default: Any = None) -> str | Any:
        value = await self._request("get", key=key)
        return default if value is None else value

    async def set(self, key: str, value: str) -> None:
        await self._request("set", key=key, value=value)

    async def remove(self, key: str) -> None:
        await self._request("remove", key=key)

    async def list(self) -> dict[str, str | None]:
        entries = await self._request("list")
        return {entry["key"]: entry["value"] for entry in entries}
