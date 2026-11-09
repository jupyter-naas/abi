"""Archive integration results to the engine's object storage, as the in-engine
modules did with ``StorageUtils.save_json``."""

from __future__ import annotations

import json
from typing import Any, Protocol


class ObjectStorage(Protocol):
    """What an integration needs from ``engine.services.object_storage``."""

    async def put_object(self, prefix: str, key: str, content: bytes) -> None: ...


async def archive_json(
    storage: ObjectStorage | None, prefix: str, key: str, value: Any
) -> None:
    """Write ``value`` as indented JSON at ``prefix/key``; no storage: nothing."""
    if storage is None:
        return
    content = json.dumps(value, indent=4, ensure_ascii=False, default=str)
    await storage.put_object(prefix, key, content.encode("utf-8"))
