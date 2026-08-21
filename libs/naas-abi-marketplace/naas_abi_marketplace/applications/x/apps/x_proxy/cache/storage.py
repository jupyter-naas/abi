"""Object-storage helpers shared by the projection and its reader.

``ObjectStorageService.list_objects`` is a *directory* listing, not a deep one: it
returns the entries directly under a prefix, with nested prefixes marked by a
trailing ``/``. Both the envelope archive
(``x/search_recent_tweets/<query>/<file>.json``) and the partitioned cache
(``x/cache/posts/ym=YYYY-MM/part-*.parquet``) are nested, so every caller here
needs the recursive form.
"""

from __future__ import annotations

from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)

# Depth guard: the layouts walked here are two levels deep, so anything beyond
# this is a loop or an unexpected tree and should stop rather than run away.
MAX_DEPTH = 6


def walk(
    object_storage: ObjectStorageService,
    prefix: str,
    *,
    suffix: str = "",
    _depth: int = 0,
) -> list[str]:
    """Every object under *prefix*, recursively, optionally filtered by *suffix*.

    Directory markers (``.nexus_folder`` and the trailing-slash entries) are not
    returned. A prefix that does not exist yields an empty list rather than
    raising — an absent partition is a normal state before the first build.
    """
    if _depth > MAX_DEPTH:
        logger.warning(f"X cache: stopped walking below {prefix} (max depth)")
        return []
    try:
        entries = object_storage.list_objects(prefix)
    except Exception as exc:  # noqa: BLE001 — absent prefix, or storage hiccup
        logger.debug(f"X cache: could not list {prefix} ({exc})")
        return []

    found: list[str] = []
    for entry in entries:
        name = entry.rstrip("/").rsplit("/", 1)[-1]
        if name == ".nexus_folder":
            continue
        if entry.endswith("/"):
            found.extend(
                walk(
                    object_storage, entry.rstrip("/"), suffix=suffix, _depth=_depth + 1
                )
            )
        elif not suffix or entry.endswith(suffix):
            found.append(entry)
    return found


def split_key(key: str) -> tuple[str, str]:
    """``(prefix, name)`` for an object key, the shape get/put_object expect."""
    directory, _, name = key.rpartition("/")
    return directory, name
