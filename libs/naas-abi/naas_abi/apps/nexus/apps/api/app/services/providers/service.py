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
    resolve_provider_logo_file,
)
from naas_abi.apps.nexus.apps.api.app.services.providers.port import (
    SYNCABLE_MODEL_FIELDS,
    ModelCatalogStorePort,
    StoredModel,
)
from naas_abi.apps.nexus.apps.api.app.services.providers.providers__schema import (
    ProviderInfo,
    ProviderModelInfo,
)

logger = logging.getLogger(__name__)

_LOGOS_DIR = Path(__file__).resolve().parents[3] / "public" / "logos"
_LOGO_EXTENSIONS = (".png", ".jpg", ".jpeg", ".svg", ".webp")


def _provider_display_name(provider: ProviderCatalogEntry) -> str:
    """Prefer the ABIModule ``name``; fall back to a humanized provider id."""
    if provider.name:
        return provider.name
    return provider.provider_id.replace("_", " ").title()


def _public_api_host() -> str | None:
    """Resolve the configured public API host.

    Same source the agent service uses for logo URLs
    (``_public_modules_url``): ``global_config.public_api_host`` on the running
    ABIModule instance. Returns None when the instance isn't initialized (e.g.
    in unit tests), in which case callers fall back to a relative path.
    """
    try:
        from naas_abi import ABIModule

        host = ABIModule.get_instance().configuration.global_config.public_api_host
    except Exception:
        return None
    return host if isinstance(host, str) and host else None


def _provider_logo_url(provider: ProviderCatalogEntry) -> str | None:
    """Resolve a usable logo URL for a provider.

    Remote ``http(s)`` logos are returned verbatim. Local module assets are
    served through the public ``/provider-logos/<id>`` route (config-independent
    and no-auth, so plain ``<img>`` tags load it even when the owning module
    isn't enabled — unlike the load-dependent ``/modules`` mounts). As with
    agent logos, the path is returned as an ABSOLUTE URL built from
    ``public_api_host`` so it resolves regardless of the frontend origin. Falls
    back to the bundled ``/logos`` directory when no asset is declared.
    """
    raw = provider.logo_url
    if raw and raw.startswith(("http://", "https://")):
        return raw

    if resolve_provider_logo_file(provider.provider_id, raw) is not None:
        path: str | None = f"/provider-logos/{provider.provider_id}"
    else:
        path = _logo_path_for(provider.slug or "", provider.provider_id)
    if path is None:
        return None

    host = _public_api_host()
    if host:
        return f"{host.rstrip('/')}/{path.lstrip('/')}"
    return path


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
    entry: ModelCatalogEntry,
    configured: bool,
    stored: StoredModel | None = None,
) -> ProviderModelInfo:
    """Build the HTTP model info, overlaying persisted display values.

    Structural identity (ids, provider, module_path) always comes from the disk
    catalog. Display properties prefer the persisted store row (which carries
    any frontend overrides) and fall back to the on-disk source values.
    """
    name = stored.name if stored is not None else entry.name
    description = stored.description if stored is not None else entry.description
    image = stored.image if stored is not None else entry.image
    context_window = stored.context_window if stored is not None else entry.context_window
    return ProviderModelInfo(
        canonical_id=entry.canonical_id,
        model_id=entry.model_id,
        provider=entry.provider,
        provider_id=entry.provider_id,
        module_path=entry.module_path,
        configured=configured,
        name=name,
        description=description,
        image=image,
        context_window=context_window,
    )


def _to_provider_info(
    provider: ProviderCatalogEntry,
    configured: bool,
    models: list[ProviderModelInfo],
) -> ProviderInfo:
    return ProviderInfo(
        id=provider.provider_id,
        name=_provider_display_name(provider),
        module_path=provider.module_path,
        configured=configured,
        logo_url=_provider_logo_url(provider),
        config_keys=provider.config_keys,
        models=models,
        description=provider.description,
        tags=provider.tags,
        slug=provider.slug,
        privacy_policy_url=provider.privacy_policy_url,
        terms_of_service_url=provider.terms_of_service_url,
        status_page_url=provider.status_page_url,
        headquarters=provider.headquarters,
        datacenters=provider.datacenters,
    )


def _source_values(entry: ModelCatalogEntry) -> dict[str, str | int | None]:
    """The display values the Python source declares for a model."""
    return {
        "name": entry.name,
        "description": entry.description,
        "image": entry.image,
        "context_window": entry.context_window,
    }


def _stored_from_entry(entry: ModelCatalogEntry) -> StoredModel:
    """A fresh store row for a model first seen on disk (no overrides yet)."""
    src = _source_values(entry)
    return StoredModel(
        canonical_id=entry.canonical_id,
        model_id=entry.model_id,
        provider=entry.provider,
        provider_id=entry.provider_id,
        module_path=entry.module_path,
        name=src["name"],
        description=src["description"],
        image=src["image"],
        context_window=src["context_window"],
        source_name=src["name"],
        source_description=src["description"],
        source_image=src["image"],
        source_context_window=src["context_window"],
        overridden_fields=[],
    )


class ProviderService:
    """Reads marketplace AI providers + their models from the on-disk catalog,
    overlaid with persisted, editable display properties.

    The catalog is independent of engine state: every ``naas_abi_marketplace.ai.*``
    module shows up regardless of whether it's enabled. Each model is then
    tagged ``configured=True`` iff its owning module is loaded in the engine.

    When a ``store`` is provided, model display properties (name, description,
    image, context_window) are served from it. ``sync_models`` reconciles the
    on-disk source into the store: a property that changed in code is pushed to
    the store unless a user already edited it in the frontend, in which case the
    frontend value is kept and a warning is logged.
    """

    def __init__(self, store: ModelCatalogStorePort | None = None) -> None:
        self.store = store

    async def _stored_map(self) -> dict[str, StoredModel]:
        """All persisted rows keyed by canonical id; empty if no/failed store."""
        if self.store is None:
            return {}
        try:
            return {row.canonical_id: row for row in await self.store.list_all()}
        except Exception:
            logger.exception("Failed to read model catalog store; serving disk values")
            return {}

    def _reconcile(
        self, entry: ModelCatalogEntry, prev: StoredModel | None
    ) -> tuple[StoredModel, list[str]]:
        """Compute the store row for ``entry`` given its previous row.

        Returns the row to persist plus any human-readable warnings about
        source-vs-frontend divergence (properties changed in code but kept
        because they were overridden in the frontend).
        """
        src = _source_values(entry)
        if prev is None:
            return _stored_from_entry(entry), []

        overridden = set(prev.overridden_fields)
        effective: dict[str, str | int | None] = {
            "name": prev.name,
            "description": prev.description,
            "image": prev.image,
            "context_window": prev.context_window,
        }
        prev_source: dict[str, str | int | None] = {
            "name": prev.source_name,
            "description": prev.source_description,
            "image": prev.source_image,
            "context_window": prev.source_context_window,
        }
        warnings: list[str] = []
        for f in SYNCABLE_MODEL_FIELDS:
            py_val = src[f]
            if f in overridden:
                # Frontend owns this property: never overwrite. Warn once per
                # source change, then advance the recorded source so the same
                # change doesn't warn on every load.
                if py_val != prev_source[f]:
                    warnings.append(
                        f"Model {entry.canonical_id!r} property {f!r} changed in the "
                        f"Python source ({prev_source[f]!r} -> {py_val!r}) but is "
                        f"overridden in the frontend to {effective[f]!r}; keeping the "
                        f"frontend value. Edit the source override away to re-sync."
                    )
                # effective[f] stays as the frontend value
            else:
                effective[f] = py_val

        record = StoredModel(
            canonical_id=entry.canonical_id,
            model_id=entry.model_id,
            provider=entry.provider,
            provider_id=entry.provider_id,
            module_path=entry.module_path,
            name=effective["name"],
            description=effective["description"],
            image=effective["image"],
            context_window=effective["context_window"],
            source_name=src["name"],
            source_description=src["description"],
            source_image=src["image"],
            source_context_window=src["context_window"],
            overridden_fields=sorted(overridden),
        )
        return record, warnings

    async def sync_models(self) -> list[str]:
        """Reconcile the on-disk catalog into the store.

        Idempotent; safe to run on every startup. Returns (and logs) warnings
        for properties whose Python source changed while a frontend override is
        in effect. No-op when no store is configured.
        """
        if self.store is None:
            return []
        existing = await self._stored_map()
        warnings: list[str] = []
        for entry in list_catalog_models():
            record, entry_warnings = self._reconcile(entry, existing.get(entry.canonical_id))
            warnings.extend(entry_warnings)
            try:
                await self.store.upsert(record)
            except Exception:
                logger.exception(
                    "Failed to persist model %s during catalog sync", entry.canonical_id
                )
        for message in warnings:
            logger.warning(message)
        return warnings

    async def list_available_providers(self) -> list[ProviderInfo]:
        loaded = _loaded_provider_module_paths()
        stored = await self._stored_map()
        out: list[ProviderInfo] = []
        for provider in list_catalog_providers():
            configured = _is_provider_configured(provider, loaded)
            models = [
                _to_model_info(entry, configured, stored.get(entry.canonical_id))
                for entry in list_models_for_catalog_provider(provider.provider_id)
            ]
            out.append(_to_provider_info(provider, configured, models))
        return out

    async def list_models(self) -> list[ProviderModelInfo]:
        loaded = _loaded_provider_module_paths()
        stored = await self._stored_map()
        configured_by_provider = {
            p.provider_id: _is_provider_configured(p, loaded) for p in list_catalog_providers()
        }
        return [
            _to_model_info(
                entry,
                configured_by_provider.get(entry.provider_id, False),
                stored.get(entry.canonical_id),
            )
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
        stored = None
        if self.store is not None:
            try:
                stored = await self.store.get(entry.canonical_id)
            except Exception:
                logger.exception(
                    "Failed to read stored model %s; serving disk values",
                    entry.canonical_id,
                )
        return _to_model_info(entry, configured, stored)

    async def update_model(
        self, canonical_or_model_id: str, updates: dict[str, str | int | None]
    ) -> ProviderModelInfo | None:
        """Persist frontend edits to a model's display properties.

        Edited properties are recorded as overrides so a later Python source
        change won't clobber them (it logs a warning instead — see
        ``sync_models``). Returns the updated model, or None if it is unknown.
        """
        if self.store is None:
            raise RuntimeError("Model catalog store is not configured")

        entry = find_catalog_model(canonical_or_model_id)
        if entry is None:
            return None

        clean = {k: v for k, v in updates.items() if k in SYNCABLE_MODEL_FIELDS}

        current = await self.store.get(entry.canonical_id)
        if current is None:
            # First touch: seed the row from disk before applying the override.
            current = await self.store.upsert(_stored_from_entry(entry))

        overridden = set(current.overridden_fields)
        effective: dict[str, str | int | None] = {
            "name": current.name,
            "description": current.description,
            "image": current.image,
            "context_window": current.context_window,
        }
        for key, value in clean.items():
            effective[key] = value
            overridden.add(key)

        record = StoredModel(
            canonical_id=current.canonical_id,
            model_id=entry.model_id,
            provider=entry.provider,
            provider_id=entry.provider_id,
            module_path=entry.module_path,
            name=effective["name"],
            description=effective["description"],
            image=effective["image"],
            context_window=effective["context_window"],
            source_name=current.source_name,
            source_description=current.source_description,
            source_image=current.source_image,
            source_context_window=current.source_context_window,
            overridden_fields=sorted(overridden),
        )
        saved = await self.store.upsert(record)

        loaded = _loaded_provider_module_paths()
        configured = False
        for provider in list_catalog_providers():
            if provider.provider_id == entry.provider_id:
                configured = _is_provider_configured(provider, loaded)
                break
        return _to_model_info(entry, configured, saved)
