from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from naas_abi_proto.cache.v1 import cache_pb2 as pb

from naas_abi_sdk.services.errors import (
    CacheExpiredError,
    CacheNotFoundError,
    domain_error,
)
from naas_abi_sdk.transport import RPCError


class CacheService:
    def __init__(self, client, selector: str | None = None):
        self._client, self._selector = client, selector

    @property
    def hot(self) -> CacheService:
        return CacheService(self._client, "hot")

    @property
    def cold(self) -> CacheService:
        return CacheService(self._client, "cold")

    async def _views(self, write=False):
        description = await self._client.describe(pb.DescribeRequest())
        tiers = list(description.tiers)
        if not tiers:
            if self._selector == "hot":
                raise ValueError("No hot cache tier configured")
            return [self._client]
        selector = self._selector or ("cold" if write else None)
        if selector is None:
            return [self._client.tier(i) for i in range(len(tiers))]
        indices = [i for i, tier in enumerate(tiers) if tier == selector]
        if not indices and selector == "hot":
            raise ValueError("No hot cache tier configured")
        return [self._client.tier(indices[-1] if indices else len(tiers) - 1)]

    async def hot_available(self) -> bool:
        return "hot" in (await self._client.describe(pb.DescribeRequest())).tiers

    async def get(self, key: str, ttl: timedelta | None = None) -> Any:
        for client in await self._views():
            try:
                cached = (await client.get(pb.GetRequest(key=key))).value
            except RPCError as exc:
                if (
                    exc.code in ("CACHE_NOT_FOUND", "CACHE_EXPIRED")
                    and self._selector is None
                ):
                    continue
                raise domain_error(exc) from exc
            if ttl is not None:
                created = datetime.fromisoformat(cached.created_at)
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if created + ttl < datetime.now(timezone.utc):
                    if self._selector is not None:
                        raise CacheExpiredError("CACHE_EXPIRED", key)
                    continue
            if cached.data_type == pb.DATA_TYPE_TEXT:
                return cached.data
            if cached.data_type == pb.DATA_TYPE_JSON:
                return json.loads(cached.data)
            if cached.data_type == pb.DATA_TYPE_BINARY:
                return base64.b64decode(cached.data)
            raise NotImplementedError(
                "Remote pickle cache deserialization is not supported"
            )
        raise CacheNotFoundError("CACHE_NOT_FOUND", key)

    async def exists(self, key: str) -> bool:
        for client in await self._views():
            if (await client.exists(pb.ExistsRequest(key=key))).value:
                return True
        return False

    async def delete(self, key: str) -> None:
        for client in await self._views():
            try:
                await client.delete(pb.DeleteRequest(key=key))
            except RPCError as exc:
                if exc.code != "CACHE_NOT_FOUND":
                    raise domain_error(exc) from exc

    async def _set(self, key, value, data_type, absent=False):
        client = (await self._views(write=True))[0]
        cached = pb.CachedData(
            key=key,
            data=value,
            data_type=data_type,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        try:
            if absent:
                return (
                    await client.set_if_absent(
                        pb.SetIfAbsentRequest(key=key, value=cached)
                    )
                ).value
            await client.set(pb.SetRequest(key=key, value=cached))
        except RPCError as exc:
            raise domain_error(exc) from exc

    async def set_text(self, key: str, value: str) -> None:
        await self._set(key, value, pb.DATA_TYPE_TEXT)

    async def set_json(self, key: str, value: Any) -> None:
        await self._set(key, json.dumps(value), pb.DATA_TYPE_JSON)

    async def set_binary(self, key: str, value: bytes) -> None:
        await self._set(key, base64.b64encode(value).decode(), pb.DATA_TYPE_BINARY)

    async def set_json_if_absent(self, key: str, value: Any) -> bool:
        return await self._set(key, json.dumps(value), pb.DATA_TYPE_JSON, True)

    async def set_binary_if_absent(self, key: str, value: bytes) -> bool:
        return await self._set(
            key, base64.b64encode(value).decode(), pb.DATA_TYPE_BINARY, True
        )

    async def set_pickle(self, key: str, value: Any) -> None:
        raise NotImplementedError("Remote pickle cache serialization is not supported")

    def __call__(self, *args, **kwargs):
        raise NotImplementedError(
            "Cache decorators are not implemented in the async SDK"
        )
