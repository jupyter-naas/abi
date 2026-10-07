"""Search topic responses, cached for a day per workspace.

A results page or a detail is the output of one or more SPARQL queries over the
workspace's graphs; they change when the graphs are reloaded, not from one search
to the next. Responses are kept for ``TTL`` and keyed by everything that shapes
them: the workspace, the graphs its member can read (the scope's cache key), the
topic as defined (an edit is a new key), the request, and the workspace's cache
generation. "Refresh" replaces the generation, which retires every entry of the
workspace at once; the TTL reaps them.

The cache is best-effort: a cache failure answers from the graphs, never an error.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import uuid
from typing import Any

TTL = datetime.timedelta(days=1)
_SEMVER = "v1"


class SearchCache:
    """``fetch``/``store`` JSON responses over a naas-abi-core CacheService."""

    def __init__(self, cache: Any, ttl: datetime.timedelta = TTL) -> None:
        self._cache = cache
        self._ttl = ttl

    def _generation_key(self, workspace_id: str) -> str:
        return f"search_topics_generation_{hashlib.sha256(workspace_id.encode()).hexdigest()}"

    def generation(self, workspace_id: str) -> str:
        """The workspace's current generation, created on first use."""
        key = self._generation_key(workspace_id)
        try:
            value = self._cache.get(key)
            if isinstance(value, dict) and value.get("token"):
                return str(value["token"])
        except Exception:  # noqa: BLE001 - absent or unreadable: start a new generation
            pass
        return self.refresh(workspace_id)

    def refresh(self, workspace_id: str) -> str:
        """Retire every cached response of the workspace."""
        token = uuid.uuid4().hex
        try:
            self._write(self._generation_key(workspace_id), {"token": token})
        except Exception:  # noqa: BLE001
            pass
        return token

    def key(self, workspace_id: str, *, scope: str, topic: dict, request: dict) -> str:
        payload = {
            "semver": _SEMVER,
            "workspace": workspace_id,
            "generation": self.generation(workspace_id),
            "scope": scope,
            "topic": topic,
            "request": request,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return "search_topics_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def fetch(self, key: str) -> dict | None:
        try:
            value = self._cache.get(key, ttl=self._ttl)
        except Exception:  # noqa: BLE001 - miss, expired or broken: answer from the graphs
            return None
        return value if isinstance(value, dict) else None

    def store(self, key: str, value: dict) -> None:
        try:
            self._write(key, value)
        except Exception:  # noqa: BLE001
            pass

    def _write(self, key: str, value: dict) -> None:
        self._cache.set_json(key, value)  # cold tier (durable)
        hot_available = getattr(self._cache, "hot_available", None)
        if callable(hot_available) and hot_available():
            self._cache.hot.set_json(key, value)  # hot tier (fast reads)
