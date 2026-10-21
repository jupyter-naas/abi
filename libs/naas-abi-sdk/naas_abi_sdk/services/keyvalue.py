from __future__ import annotations

from naas_abi_sdk.services._codec import ServiceProxy


class KeyValueService(ServiceProxy):
    domain = "keyvalue"

    async def get(self, key: str) -> bytes:
        return await self._request("get", key=key)

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        await self._request("set", key=key, value=value, ttl=ttl)

    async def set_if_not_exists(
        self, key: str, value: bytes, ttl: int | None = None
    ) -> bool:
        return await self._request("set_if_not_exists", key=key, value=value, ttl=ttl)

    async def delete(self, key: str) -> None:
        await self._request("delete", key=key)

    async def delete_if_value_matches(self, key: str, value: bytes) -> bool:
        return await self._request("delete_if_value_matches", key=key, value=value)

    async def exists(self, key: str) -> bool:
        return await self._request("exists", key=key)

    def lock(
        self,
        key: str,
        *,
        ttl: int = 30,
        timeout: float = 10.0,
        retry_delay: float = 0.05,
    ):
        raise NotImplementedError(
            "Distributed lock ownership/expiry requires an explicit remote lease contract"
        )
