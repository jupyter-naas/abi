"""Integrations backend for ABI Desktop.

One integration so far: a local Ollama server, talked to directly over HTTP
(no ``naas_abi`` / ``naas_abi_core`` imports — see AGENTS.md). Three pieces:

- :func:`probe_ollama` — availability + normalized model list from the
  Ollama REST API (``GET /api/tags``).
- :func:`sync_opencode_config` — merge the installed models into the
  workspace ``opencode.json`` as an OpenAI-compatible provider block, so the
  models surface in opencode's ``/config/providers`` and therefore in the
  app's model pickers. The merge is additive: unrelated keys, other
  providers, custom provider options, and hand-added models all survive.
- :func:`create_integrations_router` — FastAPI router exposing
  ``GET /api/integrations`` and ``PUT /api/integrations/ollama``.

Adding another integration: write a ``probe_*`` helper for its API, add its
payload to ``list_integrations`` (the response is already a list), persist
its settings under a new flat key, and add a card in ``web/app.js``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, field_validator

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"

# Flat settings key, consistent with the existing DesktopStore settings shape.
OLLAMA_SETTING_KEY = "ollama_base_url"

# Provider block shape per https://opencode.ai/docs/providers/ (Ollama
# section): opencode loads @ai-sdk/openai-compatible against the /v1
# endpoint and only exposes models explicitly listed in the config.
OPENCODE_PROVIDER_NPM = "@ai-sdk/openai-compatible"

OLLAMA_HINT = "Install and start Ollama to use local models — https://ollama.com"


class OpencodeConfigError(Exception):
    """The workspace opencode.json exists but cannot be merged safely."""


async def probe_ollama(
    base_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
    timeout: float = 3.0,
) -> dict[str, Any]:
    """Probe an Ollama server and list installed models.

    Never raises — an unreachable server reports ``connected: False`` with
    the error message. ``transport`` overrides the httpx transport
    (``httpx.MockTransport`` in tests) so no test touches the network.
    """
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
    except Exception as e:
        return {"connected": False, "models": [], "error": str(e)}

    models: list[dict[str, Any]] = []
    for raw in payload.get("models") or []:
        if not isinstance(raw, dict):
            continue
        name = raw.get("name") or raw.get("model")
        if not name:
            continue
        details = raw.get("details") or {}
        if not isinstance(details, dict):
            details = {}
        models.append(
            {
                "name": str(name),
                "size": raw.get("size"),
                "parameter_size": details.get("parameter_size"),
                "quantization_level": details.get("quantization_level"),
                "modified_at": raw.get("modified_at"),
            }
        )
    return {"connected": True, "models": models, "error": None}


def sync_opencode_config(
    workspace_dir: Path,
    base_url: str,
    models: list[dict[str, Any]],
) -> bool:
    """Merge an ``ollama`` provider block into ``<workspace>/opencode.json``.

    Never clobbers: unrelated top-level keys, other providers, extra provider
    options, per-model custom settings, and hand-added models are preserved.
    Only ``npm`` and ``options.baseURL`` are forced (the provider does not
    work without them); installed models are added with ``setdefault``.

    Returns True when the file was written. Raises
    :class:`OpencodeConfigError` (leaving the file untouched) when the
    existing config cannot be parsed.
    """
    if not models:
        return False

    config_path = Path(workspace_dir) / "opencode.json"
    config: dict[str, Any] = {}
    if config_path.exists():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
        except ValueError as e:
            raise OpencodeConfigError(
                f"opencode.json is not valid JSON, not touching it: {e}"
            ) from e
        if not isinstance(loaded, dict):
            raise OpencodeConfigError("opencode.json must contain a JSON object")
        config = loaded
    original = json.dumps(config, sort_keys=True)

    providers = config.setdefault("provider", {})
    if not isinstance(providers, dict):
        raise OpencodeConfigError('opencode.json "provider" must be an object')
    ollama = providers.setdefault("ollama", {})
    if not isinstance(ollama, dict):
        raise OpencodeConfigError('opencode.json "provider.ollama" must be an object')

    ollama.setdefault("name", "Ollama (local)")
    ollama["npm"] = OPENCODE_PROVIDER_NPM
    options = ollama.setdefault("options", {})
    if not isinstance(options, dict):
        raise OpencodeConfigError(
            'opencode.json "provider.ollama.options" must be an object'
        )
    options["baseURL"] = f"{base_url.rstrip('/')}/v1"

    model_map = ollama.setdefault("models", {})
    if not isinstance(model_map, dict):
        raise OpencodeConfigError(
            'opencode.json "provider.ollama.models" must be an object'
        )
    for model in models:
        model_map.setdefault(str(model["name"]), {"name": str(model["name"])})

    if json.dumps(config, sort_keys=True) == original:
        return False
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return True


class OllamaUpdate(BaseModel):
    base_url: str

    @field_validator("base_url")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("base_url must not be blank")
        return value


def create_integrations_router(
    store: Any,
    transport: httpx.AsyncBaseTransport | None = None,
    on_config_change: Callable[[], None] | None = None,
) -> APIRouter:
    """Router for ``/api/integrations``.

    ``store`` is the app's :class:`DesktopStore` (settings persistence).
    ``on_config_change`` fires after ``opencode.json`` actually changed —
    the server uses it to bounce opencode so it reloads providers.
    """
    router = APIRouter()

    def _base_url() -> str:
        settings = store.get_settings()
        return str(settings.get(OLLAMA_SETTING_KEY) or DEFAULT_OLLAMA_BASE_URL).rstrip(
            "/"
        )

    async def _ollama_payload() -> dict[str, Any]:
        base_url = _base_url()
        probe = await probe_ollama(base_url, transport=transport)
        error = probe["error"]
        if probe["connected"] and probe["models"]:
            workspace = Path(store.get_settings()["workspace_root"])
            try:
                changed = sync_opencode_config(workspace, base_url, probe["models"])
            except OpencodeConfigError as e:
                error = str(e)
            else:
                if changed and on_config_change is not None:
                    on_config_change()
        return {
            "id": "ollama",
            "name": "Ollama",
            "base_url": base_url,
            "connected": probe["connected"],
            "models": probe["models"],
            "error": error,
            "hint": None if probe["connected"] else OLLAMA_HINT,
        }

    @router.get("/api/integrations")
    async def list_integrations() -> dict[str, Any]:
        return {"integrations": [await _ollama_payload()]}

    @router.put("/api/integrations/ollama")
    async def update_ollama(body: OllamaUpdate) -> dict[str, Any]:
        store.update_settings({OLLAMA_SETTING_KEY: body.base_url.rstrip("/")})
        return await _ollama_payload()

    return router
