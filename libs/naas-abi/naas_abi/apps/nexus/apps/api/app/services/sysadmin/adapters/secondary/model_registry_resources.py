"""The model registry, read-only: one item per canonical model id.

The registry is in memory and filled by modules at load time, per process, so
there is nothing to edit from here. Each item shows the models registered
under the id (provider, provider model id, kind, limits) and whether it is a
configured default. Ids are the canonical ids, percent-encoded (some contain
``/``, e.g. ``openai/gpt-4o``).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import quote, unquote

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    Action,
    InvalidResource,
    ResourceCapabilities,
    ResourceDetail,
    ResourceEntry,
    ResourceNotFound,
    ResourcePage,
    ResourceTooLarge,
    UnsupportedOperation,
    paginate,
    text_preview,
)

SERVICE = "model_registry"
ACTIONS: tuple[Action, ...] = ("read", "download")


def _kind(model: Any) -> str:
    model_type = getattr(model, "model_type", None)
    return str(getattr(model_type, "value", model_type or "unknown"))


def _first(models: list[Any], field: str) -> Any:
    for model in models:
        value = getattr(model, field, None)
        if value not in (None, "", {}):
            return value
    return None


def _per_million(price: Any) -> str | None:
    """A per-token USD price (OpenRouter style, a string) as USD per million tokens."""
    try:
        value = float(price) * 1_000_000
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def _sentence(text: str, limit: int = 140) -> str:
    first = text.strip().split("\n")[0]
    cut = first.find(". ")
    if 0 < cut < limit:
        return first[: cut + 1]
    return first if len(first) <= limit else first[: limit - 1].rstrip() + "…"


class ModelRegistryResources:
    service = SERVICE
    # The registry is in memory: search filters it directly.
    capabilities = ResourceCapabilities(browse=True, search=True)

    def __init__(self, registry: Any) -> None:
        self._registry = registry

    # --- sync helpers, run in a worker thread ---------------------------------------

    def _catalog(self) -> dict[str, list[Any]]:
        catalog: dict[str, list[Any]] = {}
        for canonical_id, model in self._registry.list_registered_models():
            catalog.setdefault(str(canonical_id), []).append(model)
        return dict(sorted(catalog.items()))

    def _defaults(self, canonical_id: str) -> list[str]:
        defaults = []
        if self._registry.default_chat_model_id == canonical_id:
            defaults.append("chat")
        if self._registry.default_embedding_model_id == canonical_id:
            defaults.append("embedding")
        return defaults

    def _entry(self, canonical_id: str, models: list[Any]) -> ResourceEntry:
        attributes = {
            "kind": ", ".join(sorted({_kind(m) for m in models})),
            "providers": ", ".join(sorted({str(m.provider) for m in models})),
        }
        defaults = self._defaults(canonical_id)
        if defaults:
            attributes["default"] = ", ".join(defaults)
        name = _first(models, "name")
        if name:
            attributes["display_name"] = str(name)
        context = max((getattr(m, "context_window", None) or 0 for m in models), default=0)
        if context:
            attributes["context_window"] = str(context)
        dimensions = _first(models, "dimensions")
        if dimensions:
            attributes["dimensions"] = str(dimensions)
        top = _first(models, "top_provider") or {}
        if isinstance(top, dict) and top.get("max_completion_tokens"):
            attributes["max_output_tokens"] = str(top["max_completion_tokens"])
        pricing = _first(models, "pricing") or {}
        if isinstance(pricing, dict):
            for key, attribute in (("prompt", "input_price"), ("completion", "output_price")):
                price = _per_million(pricing.get(key))
                if price:
                    attributes[attribute] = price
        description = _first(models, "description")
        if description:
            attributes["summary"] = _sentence(str(description))
        return ResourceEntry(
            quote(canonical_id, safe=""), canonical_id, "item", ACTIONS, attributes=attributes
        )

    def _models(self, resource_id: str) -> tuple[str, list[Any]]:
        canonical_id = unquote(resource_id)
        models = self._catalog().get(canonical_id)
        if not models:
            raise ResourceNotFound(SERVICE, resource_id)
        return canonical_id, models

    def _list(
        self, parent: str, cursor: str | None, limit: int, query: str | None = None
    ) -> ResourcePage:
        if parent:
            if unquote(parent) in self._catalog():
                raise InvalidResource(SERVICE, f"{parent!r} is a model, not a folder")
            raise ResourceNotFound(SERVICE, parent)
        needle = (query or "").lower()
        entries = [
            self._entry(cid, models)
            for cid, models in self._catalog().items()
            if not needle
            or needle in cid.lower()
            or any(needle in str(getattr(m, "name", "") or "").lower() for m in models)
        ]
        return paginate("", entries, cursor, limit)

    def _stat(self, resource_id: str) -> ResourceEntry:
        return self._entry(*self._models(resource_id))

    def _sheet(self, resource_id: str) -> tuple[ResourceEntry, dict[str, Any]]:
        canonical_id, models = self._models(resource_id)
        body = {
            "canonical_id": canonical_id,
            "default_for": self._defaults(canonical_id),
            "models": [
                {
                    "provider": str(m.provider),
                    "model_id": m.model_id,
                    "kind": _kind(m),
                    "name": getattr(m, "name", None),
                    "owner": getattr(m, "owner", None),
                    "description": getattr(m, "description", None),
                    "context_window": getattr(m, "context_window", None),
                    "dimensions": getattr(m, "dimensions", None),
                    "pricing": getattr(m, "pricing", None),
                    "top_provider": getattr(m, "top_provider", None),
                    "architecture": getattr(m, "architecture", None),
                    "supported_parameters": getattr(m, "supported_parameters", None),
                }
                for m in models
            ],
        }
        return self._entry(canonical_id, models), body

    def _document(self, resource_id: str) -> tuple[ResourceEntry, bytes]:
        entry, body = self._sheet(resource_id)
        return entry, json.dumps(body, indent=2, ensure_ascii=False, default=str).encode()

    def _read(self, resource_id: str) -> ResourceDetail:
        entry, body = self._sheet(resource_id)
        data = json.dumps(body, indent=2, ensure_ascii=False, default=str).encode()
        # The same sheet, as JSON values (dates and other objects as strings).
        view = {"type": "json", "value": json.loads(data)}
        return ResourceDetail(entry, text_preview(data), view=view)

    def _download(self, resource_id: str, max_bytes: int) -> bytes:
        _, data = self._document(resource_id)
        if len(data) > max_bytes:
            raise ResourceTooLarge(SERVICE, resource_id, len(data), max_bytes)
        return data

    # --- ServiceResources --------------------------------------------------------------

    async def list(
        self, parent: str = "", *, cursor: str | None = None, limit: int = 100, **options: Any
    ) -> ResourcePage:
        return await asyncio.to_thread(self._list, parent, cursor, limit, options.get("query"))

    async def stat(self, resource_id: str) -> ResourceEntry:
        return await asyncio.to_thread(self._stat, resource_id)

    async def read(self, resource_id: str, *, reveal: bool = False) -> ResourceDetail:
        return await asyncio.to_thread(self._read, resource_id)

    async def download(self, resource_id: str, *, max_bytes: int) -> bytes:
        return await asyncio.to_thread(self._download, resource_id, max_bytes)

    async def write(self, resource_id: str, content: bytes) -> ResourceEntry:
        raise UnsupportedOperation(SERVICE, "write: models are registered by modules at load")

    async def delete(self, resource_id: str) -> None:
        raise UnsupportedOperation(SERVICE, "delete: models are registered by modules at load")
