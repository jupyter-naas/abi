from __future__ import annotations

import logging
from pathlib import Path

from naas_abi.apps.nexus.apps.api.app.services.providers.model_catalog import (
    ModelCatalogEntry,
    ProviderCatalogEntry,
    find_catalog_model,
    list_catalog_models,
    list_catalog_providers,
    list_models_for_catalog_provider,
)
from naas_abi.apps.nexus.apps.api.app.services.providers.providers__schema import (
    ProviderInfo,
    ProviderModelInfo,
)

logger = logging.getLogger(__name__)

_PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    "bedrock": "AWS Bedrock",
    "chatgpt": "OpenAI",
    "claude": "Anthropic",
    "deepseek": "DeepSeek",
    "gemini": "Google AI",
    "gemma": "Gemma",
    "grok": "xAI (Grok)",
    "llama": "Meta Llama",
    "mistral": "Mistral AI",
    "openrouter": "OpenRouter",
    "perplexity": "Perplexity",
    "qwen": "Qwen",
    "zettafox": "Zettafox",
}

_LOGOS_DIR = Path(__file__).resolve().parents[3] / "public" / "logos"
_LOGO_EXTENSIONS = (".png", ".jpg", ".jpeg", ".svg", ".webp")


def _provider_display_name(provider_id: str) -> str:
    return _PROVIDER_DISPLAY_NAMES.get(provider_id, provider_id.replace("_", " ").title())


def _logo_path_for(*candidates: str) -> str | None:
    if not _LOGOS_DIR.is_dir():
        return None
    for candidate in candidates:
        if not candidate:
            continue
        for ext in _LOGO_EXTENSIONS:
            path = _LOGOS_DIR / f"{candidate}{ext}"
            if path.exists():
                return f"/logos/{path.name}"
    return None


def _loaded_provider_module_paths() -> set[str]:
    """Return the python module paths of every loaded marketplace AI module.

    A module is considered "configured" iff it appears in the engine's loaded
    modules registry — i.e. it was enabled in ``config.yaml`` and its
    ``Configuration`` validated (required secrets present, etc.).
    """
    try:
        from naas_abi import ABIModule
    except Exception:
        return set()

    try:
        engine = ABIModule.get_instance().engine
    except Exception:
        return set()

    loaded: set[str] = set()
    for module in engine.modules.values():
        module_path = getattr(module, "module_path", None) or module.__class__.__module__
        # module_path on BaseModule is the top-level package; module class lives
        # under the provider module path. Grab both to be safe.
        loaded.add(module.__class__.__module__)
        if isinstance(module_path, str):
            loaded.add(module_path)
    return loaded


def _is_provider_configured(provider: ProviderCatalogEntry, loaded: set[str]) -> bool:
    return provider.module_path in loaded


def _to_model_info(
    entry: ModelCatalogEntry, configured: bool
) -> ProviderModelInfo:
    return ProviderModelInfo(
        canonical_id=entry.canonical_id,
        model_id=entry.model_id,
        provider=entry.provider,
        provider_id=entry.provider_id,
        module_path=entry.module_path,
        configured=configured,
        name=entry.name,
        description=entry.description,
        image=entry.image,
        context_window=entry.context_window,
    )


def _to_provider_info(
    provider: ProviderCatalogEntry,
    configured: bool,
    models: list[ProviderModelInfo],
) -> ProviderInfo:
    return ProviderInfo(
        id=provider.provider_id,
        name=_provider_display_name(provider.provider_id),
        module_path=provider.module_path,
        configured=configured,
        logo_url=_logo_path_for(provider.provider_id),
        config_keys=provider.config_keys,
        models=models,
    )


class ProviderService:
    """Reads marketplace AI providers + their models from on-disk catalog.

    The catalog is independent of engine state: every ``naas_abi_marketplace.ai.*``
    module shows up regardless of whether it's enabled. Each model is then
    tagged ``configured=True`` iff its owning module is loaded in the engine.
    """

    def __init__(self) -> None:
        pass

    async def list_available_providers(self) -> list[ProviderInfo]:
        loaded = _loaded_provider_module_paths()
        out: list[ProviderInfo] = []
        for provider in list_catalog_providers():
            configured = _is_provider_configured(provider, loaded)
            models = [
                _to_model_info(entry, configured)
                for entry in list_models_for_catalog_provider(provider.provider_id)
            ]
            out.append(_to_provider_info(provider, configured, models))
        return out

    async def list_models(self) -> list[ProviderModelInfo]:
        loaded = _loaded_provider_module_paths()
        configured_by_provider = {
            p.provider_id: _is_provider_configured(p, loaded)
            for p in list_catalog_providers()
        }
        return [
            _to_model_info(entry, configured_by_provider.get(entry.provider_id, False))
            for entry in list_catalog_models()
        ]

    async def get_model(self, canonical_or_model_id: str) -> ProviderModelInfo | None:
        entry = find_catalog_model(canonical_or_model_id)
        if entry is None:
            return None
        loaded = _loaded_provider_module_paths()
        configured = False
        for provider in list_catalog_providers():
            if provider.provider_id == entry.provider_id:
                configured = _is_provider_configured(provider, loaded)
                break
        return _to_model_info(entry, configured)
