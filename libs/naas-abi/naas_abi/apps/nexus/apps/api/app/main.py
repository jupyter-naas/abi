"""
NEXUS API - Main Application Entry Point
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from naas_abi.apps.nexus.apps.api.app.api.router import api_router
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.database import init_db
from naas_abi.apps.nexus.apps.api.app.core.frame_headers import embed_csp, is_embeddable
from naas_abi.apps.nexus.apps.api.app.core.logging import configure_logging
from naas_abi.apps.nexus.apps.api.app.core.user_content import harden_active_content
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_ingestion_worker import (
    start_chat_ingestion_consumer,
)
from naas_abi.apps.nexus.apps.api.app.services.exceptions import (
    register_service_exception_handlers,
)
from naas_abi.apps.nexus.apps.api.app.services.idp.paths import is_idp_path
from naas_abi.apps.nexus.apps.api.app.services.ollama import (
    DEFAULT_MODEL,
    ensure_ollama_ready,
    get_ollama_status,
)
from naas_abi.apps.nexus.apps.api.app.services.websocket import init_websocket
from starlette.middleware.base import BaseHTTPMiddleware


async def _prefetch_modules_catalog() -> None:
    """Warm up the marketplace module catalog in a thread-pool worker.

    The catalog scans naas_abi_marketplace via filesystem I/O which is
    synchronous.  Running it via run_in_executor keeps the event loop free.
    """
    _log = logging.getLogger(__name__)
    try:
        from naas_abi.apps.nexus.apps.api.app.services.modules.service import (
            _build_catalog,
        )

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _build_catalog)
        _log.info("✓ Marketplace catalog pre-populated at startup")
    except Exception:
        _log.exception("Background modules catalog pre-fetch failed (non-fatal)")


async def _sync_model_catalog() -> None:
    """Reconcile the on-disk AI model catalog into the Postgres store.

    Picks up new models and source-side property changes (e.g. a new
    description) on every boot. Properties a user edited in the frontend are
    preserved and a warning is logged when the source diverges from them.
    """
    _log = logging.getLogger(__name__)
    try:
        from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
        from naas_abi.apps.nexus.apps.api.app.services.providers.adapters.secondary.providers__secondary_adapter__postgres import (  # noqa: E501
            ModelCatalogSecondaryAdapterPostgres,
        )
        from naas_abi.apps.nexus.apps.api.app.services.providers.service import (
            ProviderService,
        )

        async with AsyncSessionLocal() as session:
            service = ProviderService(store=ModelCatalogSecondaryAdapterPostgres(session))
            warnings = await service.sync_models()
        _log.info(
            "✓ Model catalog synced at startup (%d override divergence warning(s))",
            len(warnings),
        )
        # Settings pages opened while this ran may have cached the old catalog.
        await asyncio.to_thread(_invalidate_settings_cache)
    except Exception:
        _log.exception("Background model catalog sync failed (non-fatal)")


def _invalidate_settings_cache() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.settings_cache.middleware import (
        invalidate_on_startup,
    )

    invalidate_on_startup()


async def _sync_identity_graph() -> None:
    """Rebuild graph/nexus-identity from Postgres and the running configuration:
    users and persons, organizations, workspaces, memberships and access roles,
    features and policies, and their setup processes. Event payloads only hold
    ids; this graph resolves them to people.
    """
    _log = logging.getLogger(__name__)
    try:
        from naas_abi import ABIModule
        from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
        from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings
        from naas_abi.apps.nexus.apps.api.app.services.identity_graph.adapters.secondary.identity_graph__secondary_adapter__postgres import (  # noqa: E501
            IdentitySourceSecondaryAdapterPostgres,
        )
        from naas_abi.apps.nexus.apps.api.app.services.identity_graph.adapters.secondary.identity_graph__secondary_adapter__settings import (  # noqa: E501
            PlatformConfigurationSourceSettings,
        )
        from naas_abi.apps.nexus.apps.api.app.services.identity_graph.adapters.secondary.identity_graph__secondary_adapter__triplestore import (  # noqa: E501
            IdentityGraphStoreSecondaryAdapterTripleStore,
        )
        from naas_abi.apps.nexus.apps.api.app.services.identity_graph.service import (
            IdentityGraphService,
        )

        async with AsyncSessionLocal() as session:
            service = IdentityGraphService(
                source=IdentitySourceSecondaryAdapterPostgres(session),
                store=IdentityGraphStoreSecondaryAdapterTripleStore(
                    lambda: ABIModule.get_instance().engine.services.triple_store
                ),
                platform=PlatformConfigurationSourceSettings(
                    settings_getter=live_settings,
                    module_config_getter=lambda: ABIModule.get_instance().configuration,
                ),
            )
            # Boot races Fuseki writes from schema load and seeds. A single
            # CLEAR/DROP can lose the dataset lock; retry rather than skip.
            delays = (0.0, 2.0, 8.0)
            result = None
            for attempt, delay in enumerate(delays):
                if delay:
                    await asyncio.sleep(delay)
                try:
                    result = await service.sync()
                    break
                except Exception:
                    if attempt == len(delays) - 1:
                        raise
                    _log.warning(
                        "Identity graph sync failed (attempt %d/%d); retrying",
                        attempt + 1,
                        len(delays),
                        exc_info=True,
                    )
        assert result is not None
        _log.info(
            "✓ Identity graph synced (%d users, %d organizations, %d workspaces, %d memberships, %d triples)",
            result.users,
            result.organizations,
            result.workspaces,
            result.memberships,
            result.triples,
        )
    except Exception:
        _log.exception("Background identity graph sync failed (non-fatal)")


_identity_graph_sync_task: asyncio.Task | None = None


def _schedule_identity_graph_sync(_published: int = 0, delay_seconds: float = 2.0) -> None:
    """Rebuild the identity graph shortly after identity events, coalescing bursts
    (a config seed or a bulk invite commits many changes in a row)."""
    global _identity_graph_sync_task
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    if _identity_graph_sync_task is not None and not _identity_graph_sync_task.done():
        return

    async def _later() -> None:
        from naas_abi_core.engine.call_context import as_service_account

        await asyncio.sleep(delay_seconds)
        # Housekeeping, whoever's commit scheduled it: Nexus's own account.
        with as_service_account("api"):
            await _sync_identity_graph()

    _identity_graph_sync_task = loop.create_task(_later())


def _install_drive_writers() -> None:
    """Keep .manifest.json and the default folders in every workspace drive and My Drive."""
    _log = logging.getLogger(__name__)
    try:
        from naas_abi import ABIModule
        from naas_abi.apps.nexus.apps.api.app.services.files.drives.my_drive import MyDriveWriter
        from naas_abi.apps.nexus.apps.api.app.services.files.drives.workspace_drive import (
            WorkspaceDriveWriter,
        )

        def get_storage():  # noqa: ANN202 - the engine's ObjectStorageService
            return ABIModule.get_instance().engine.services.object_storage

        WorkspaceDriveWriter(get_storage=get_storage).install()
        MyDriveWriter(get_storage=get_storage).install()
        _log.info("✓ Drive writers installed")
    except Exception:
        _log.exception("Unable to install the drive writers")


async def _backfill_drives() -> None:
    """Write missing workspace and My Drive defaults, and the platform drive's staff folders."""
    _log = logging.getLogger(__name__)
    try:
        from naas_abi import ABIModule
        from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
        from naas_abi.apps.nexus.apps.api.app.services.files.drives.my_drive import (
            backfill_my_drives,
        )
        from naas_abi.apps.nexus.apps.api.app.services.files.drives.platform_drive import (
            backfill_platform_drive,
        )
        from naas_abi.apps.nexus.apps.api.app.services.files.drives.workspace_drive import (
            backfill_workspace_drives,
        )

        storage = ABIModule.get_instance().engine.services.object_storage
        async with AsyncSessionLocal() as session:
            workspaces = await backfill_workspace_drives(session, storage)
            users = await backfill_my_drives(session, storage)
        platform = await backfill_platform_drive(storage)
        if any(workspaces.values()) or any(users.values()) or any(platform.values()):
            _log.info(
                "✓ Drives backfilled: workspaces %s, my drives %s, platform %s",
                workspaces,
                users,
                platform,
            )
    except Exception:
        _log.exception("Drive backfill failed")


def _install_identity_event_capture() -> None:
    """Publish a nexus identity-and-access event for every committed change to
    users, organizations, workspaces, memberships and workspace configuration."""
    _log = logging.getLogger(__name__)
    try:
        from urllib.parse import urlsplit

        from naas_abi import ABIModule
        from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings
        from naas_abi.apps.nexus.apps.api.app.services.identity_events.capture import (
            IdentityEventCapture,
        )
        from naas_abi.apps.nexus.apps.api.app.services.identity_graph.iris import (
            deployment_site_iri,
        )

        engine = ABIModule.get_instance().engine
        if not engine.services.events_available():
            _log.warning("EventService not configured; identity events disabled")
            return
        event_service = engine.services.events
        host = urlsplit(getattr(live_settings(), "frontend_url", "") or "").hostname or "unknown"

        IdentityEventCapture(
            # Late-bound: the admin relay wraps publish() after this runs.
            publish=lambda event: event_service.publish(event),
            site_iri=str(deployment_site_iri(host)),
            on_published=_schedule_identity_graph_sync,
        ).install()
        _log.info("✓ Identity event capture installed")
    except Exception:
        _log.exception("Unable to install identity event capture (non-fatal)")


async def _prefetch_agent_class_registry() -> None:
    """Warm up the agent class registry in a thread-pool worker.

    The registry build triggers dynamic imports of all ~160 agent modules, which
    is synchronous and CPU/IO-bound.  Running it via run_in_executor keeps the
    event loop free during startup while ensuring the cache is hot before the
    first GET /agents/ request arrives.
    """
    _log = logging.getLogger(__name__)
    try:
        from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.agents__primary_adapter__FastAPI import (
            _get_agent_class_registry,
        )

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _get_agent_class_registry)
        _log.info("✓ Agent class registry pre-populated at startup")
    except Exception:
        _log.exception("Background agent registry pre-fetch failed (non-fatal)")


async def _move_secrets_to_the_secrets_key(app: FastAPI) -> None:
    """Move what the old ``secret_key`` encrypted under the secrets key:
    workspace secrets and the provider tokens of sessions. Idempotent, and cheap
    once nothing is left under an old key."""
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.core.secret_key import legacy_secret_keys
    from naas_abi.apps.nexus.apps.api.app.services.secrets.migration import (
        move_to_secrets_key,
    )

    log = logging.getLogger(__name__)
    old_keys = getattr(app.state, "legacy_secret_keys", None)
    if old_keys is None:
        # No engine store to ask: the configured key and the published defaults.
        old_keys = legacy_secret_keys(settings.secret_key, _NoStore())
    async with AsyncSessionLocal() as db:
        moved = await move_to_secrets_key(db, old_keys)
        await db.commit()
    if moved.secrets or moved.session_tokens:
        log.warning(
            "Re-encrypted %d workspace secret(s) and %d session token(s) under the secrets "
            "key (NEXUS_SECRETS_KEY): the old SECRET_KEY encrypts nothing and signs nothing now.",
            moved.secrets,
            moved.session_tokens,
        )
    if moved.unreadable:
        log.warning(
            "%d stored secret(s) or session token(s) are encrypted under a key that is "
            "not known. If you had set SECRET_KEY, set it again to the old value: they move "
            "at the next start.",
            moved.unreadable,
        )


class _NoStore:
    def get(self, key: str, default: object = None) -> object:
        return default

    def set(self, key: str, value: str) -> None:  # pragma: no cover - never written
        raise RuntimeError("no secret store")


async def _prepare_iam() -> None:
    """Register the ``nexus`` catalog; once, move the workspace feature
    overrides, the role features and the sets into policies, then rewrite IAM's
    names to container paths (organizations and workspaces become containers);
    move the role data Nexus kept itself into IAM and give org owners and admins
    their role below their organization. Without an IAM service every Nexus
    decision is a refusal, so the failure is logged loudly and boot goes on.
    Until the sets are moved and the names rewritten, module scopes and features
    are refused (``authz.upgrading``)."""
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal, async_engine
    from naas_abi.apps.nexus.apps.api.app.services.iam import (
        bootstrap,
        container_names,
        policy_tree,
    )
    from naas_abi.apps.nexus.apps.api.app.services.iam import listers as iam_listers
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS

    log = logging.getLogger(__name__)
    MEMBERSHIPS.known_user = bootstrap.nexus_user_exists
    # Refused until the moves below say the sets are policies and the names
    # container paths: never wider.
    policy_tree.set_pending(True)
    container_names.set_pending(True)
    try:
        async with AsyncSessionLocal() as db:
            await bootstrap.register_catalog()
            # What the policy builder lists of naas_abi's types and the modules'
            # items; a type left out is offered as wildcards.
            try:
                await iam_listers.register()
            except Exception:  # noqa: BLE001 - listing never stops the API
                log.exception("naas_abi's listers are not registered")
            # The moves of the grammar before container paths: they read and write
            # it, so they run before the names are rewritten (IAM takes it from
            # them, as the engine or the API acting for nobody). They read the
            # roles IAM holds: while Nexus keeps memberships IAM does not, nothing
            # moves, nothing is recorded, and every module scope and feature stays
            # refused (logged).
            # One API process moves at a time: the others wait, then find the
            # moves recorded (PostgreSQL; on SQLite one process starts).
            async with container_names.moves_lock(async_engine):
                if not await container_names.before_names(
                    db, lambda: _move_before_container_paths(db, log)
                ):
                    return
                # IAM's names become container paths, once, organizations and
                # workspaces registered as containers (after the moves above).
                await container_names.migrate_names(db)
                report = await bootstrap.migrate_role_data(db)
                if report.applied:
                    log.info("Role data moved into IAM: %s", report)
                # Org owners and admins reach every workspace of their organization.
                made = await MEMBERSHIPS.sync_org_wide_roles()
                if made:
                    log.info("Organization-wide roles given to %d owner(s) and admin(s)", made)
                # Nothing left to move: say so to a start that skipped the moves.
                await policy_tree.migrate_sets(db)
    except Exception:
        log.exception("Nexus could not set up its authorization in IAM: every request is refused")


_upgrade_watch_task: asyncio.Task[None] | None = None
# How often a process that still refuses module scopes and features re-reads
# whether another API process has recorded the moves.
UPGRADE_WATCH_SECONDS = 60.0


def _watch_upgrade() -> None:
    """While this process waits for a move (``authz.upgrading``), re-read
    ``iam_migrations`` every ``UPGRADE_WATCH_SECONDS``: a replica whose start did
    not make the moves stops refusing once another one has recorded them."""
    global _upgrade_watch_task
    from naas_abi.apps.nexus.apps.api.app.services.iam import authz

    if not authz.upgrading() or (_upgrade_watch_task and not _upgrade_watch_task.done()):
        return

    async def watch() -> None:
        from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
        from naas_abi.apps.nexus.apps.api.app.services.iam import container_names

        log = logging.getLogger(__name__)
        while authz.upgrading():
            await asyncio.sleep(UPGRADE_WATCH_SECONDS)
            try:
                async with AsyncSessionLocal() as db:
                    if not await container_names.refresh_pending(db):
                        log.info("The moves are recorded: module scopes and features are decided")
            except Exception:  # noqa: BLE001 - read again at the next tick
                log.warning("Could not read whether the moves are recorded", exc_info=True)

    _upgrade_watch_task = asyncio.get_running_loop().create_task(watch())


async def _move_before_container_paths(db: Any, log: logging.Logger) -> None:
    """The start-up moves written for the grammar before container paths: the
    per-workspace feature overrides, the role features and the sets. Each is
    recorded once done; a failure is retried at the next start and never keeps
    the rest of authorization from being set up."""
    from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings
    from naas_abi.apps.nexus.apps.api.app.services.iam import (
        feature_overrides,
        policy_tree,
        role_features,
    )

    try:
        await feature_overrides.migrate_feature_overrides(db, live_settings().feature_flags)
    except Exception:
        await db.rollback()
        log.exception("The workspace feature overrides were not moved")
    # No role brings a feature: what each role had in each workspace becomes that
    # workspace's policy, once, for who holds the role there.
    try:
        await role_features.migrate_role_features(db, live_settings().feature_flags)
    except Exception:
        await db.rollback()
        log.exception("The role features were not moved into workspace policies")
    # The sets and the workspace toggles become a tree of policies, once, nobody
    # gaining or losing access (after the moves above).
    await policy_tree.migrate_sets(db)


async def _hint_unlinked_users() -> None:
    """Accounts of the old login that no identity provider signs in yet: they are
    linked at the first sign-in through the built-in provider, once the provider
    knows them (``abi user migrate``). Said once at start, beyond the people the
    configuration lists (those are made at the provider by the seeds)."""
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.secondary.postgres import (
        OidcSessionSecondaryAdapterPostgres,
    )

    try:
        async with AsyncSessionLocal() as db:
            unlinked = await OidcSessionSecondaryAdapterPostgres(db).list_legacy_users()
    except Exception:  # noqa: BLE001 - a hint, never a reason not to start
        return
    configured = {str(u.email).strip().lower() for u in settings.users}
    waiting = [u for u in unlinked if u.email.lower() not in configured]
    if waiting:
        logging.getLogger(__name__).warning(
            "%d account(s) of the old login are not linked to an identity provider yet. "
            "Run `abi user migrate` (then `--apply`): each person signs in with the code "
            "the built-in provider mails them, and keeps their roles and data.",
            len(waiting),
        )


async def _place_workspace_resources() -> None:
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.services.iam import placements

    try:
        async with AsyncSessionLocal() as db:
            await placements.place_existing(db)
    except Exception:
        logging.getLogger(__name__).exception("Nexus could not place its workspaces' resources")


async def _startup(app: FastAPI) -> None:
    """Application startup handler."""
    configure_logging()

    from naas_abi.apps.nexus.apps.api.app.services.registry_bootstrap import (
        initialize_nexus_service_registry,
    )

    initialize_nexus_service_registry()

    # Validate critical security settings

    # Initialize database (run migrations) with retry logic
    try:
        await init_db()
        print("✓ Database ready")
    except ConnectionError as e:
        print(f"✗ Database initialization failed: {e}")
        print("  API will not start without database connection.")
        raise

    await _move_secrets_to_the_secrets_key(app)

    # Nexus's authorization lives in IAM: its action catalog and feature policies,
    # and (once) the memberships and superadmin flags it kept itself before.
    await _prepare_iam()
    _watch_upgrade()
    await _hint_unlinked_users()

    # Apply config-driven user/org/workspace seeds from config.yaml.
    from naas_abi.apps.nexus.apps.api.app.core.org_seed import apply_configuration_seeds

    # Before seeds: users, workspaces and memberships the configuration creates
    # or changes are logged as identity events, triggered via "configuration".
    _install_identity_event_capture()
    # Also before seeds, so users and workspaces the configuration creates get their drives set up.
    _install_drive_writers()
    from naas_abi_core.engine.call_context import as_service_account
    from naas_abi_core.services.event.context import event_triggered_via

    # Housekeeping for no user: Nexus's own service account.
    with as_service_account("api"):
        via = event_triggered_via.set("configuration")
        try:
            await apply_configuration_seeds()
        finally:
            event_triggered_via.reset(via)

    # After seeds, so every workspace of the configuration exists: the kernel
    # resources Nexus keeps for each are placed in it, which is what lets its
    # members' roles reach them.
    await _place_workspace_resources()

    # Maps feeds, layers and basemaps declared by modules (artifacts/maps/{layers/**,basemaps/*}/manifest.json),
    # then config Maps ids (workspaces[].maps) that nothing provides. Both only
    # log errors, never fail the start.
    from naas_abi.apps.nexus.apps.api.app.services.maps.adapters.primary.workspace_defaults import (  # noqa: E501
        report_unknown_workspace_map_ids,
    )
    from naas_abi.apps.nexus.apps.api.app.services.maps.manifests import (
        register_module_manifests,
    )

    try:
        from naas_abi import ABIModule

        abi_module = ABIModule.get_instance()
        modules = [
            abi_module,
            *(m for m in abi_module.engine.modules.values() if m is not abi_module),
        ]
    except Exception:  # noqa: BLE001 - standalone Nexus: no ABI engine, no module manifests
        modules = []
    register_module_manifests(app, modules)
    report_unknown_workspace_map_ids(app)

    # An ABI restart clears the settings pages' 24h API cache (after seeds, which
    # may have changed users, workspaces and organizations).
    await asyncio.to_thread(_invalidate_settings_cache)

    # Tasks copy the context they are created in: Nexus's own housekeeping.
    with as_service_account("api"):
        # After seeds, so seeded users/workspaces are in the graph on first boot.
        asyncio.create_task(_sync_identity_graph())
        # After seeds too: users and workspaces created before the drive writers get theirs.
        asyncio.create_task(_backfill_drives())

    try:
        start_chat_ingestion_consumer(app)
    except Exception:
        logging.getLogger(__name__).exception("Unable to start chat ingestion consumer")

    # Relay platform LogProcess events to the Socket.IO admin_events room
    # for the superadmin live event stream UI.
    try:
        from naas_abi.apps.nexus.apps.api.app.services.websocket.admin_events import (
            start_admin_event_relay,
        )

        start_admin_event_relay()
    except Exception:
        logging.getLogger(__name__).exception("Unable to start admin event relay")

    # Pre-populate the agent class registry in the background so the first
    # GET /agents/ request returns instantly from cache instead of waiting
    # for all agent modules to be imported.  create_task returns immediately.
    asyncio.create_task(_prefetch_agent_class_registry())

    # Pre-populate the marketplace catalog so first GET /modules/ is instant.
    asyncio.create_task(_prefetch_modules_catalog())

    # Reconcile the AI model catalog into Postgres (new models + source changes),
    # preserving any frontend property overrides.
    asyncio.create_task(_sync_model_catalog())

    # # Auto-start Ollama and pull the project's default chat model
    # print("Checking Ollama status...")
    # # Gate autostart behind config flag to avoid process management in prod
    # required_model = DEFAULT_MODEL
    # if settings.enable_ollama_autostart:
    #     ollama_result = await ensure_ollama_ready(required_model=required_model)
    # else:
    #     # Do not attempt to start; only report current status
    #     from naas_abi.apps.nexus.apps.api.app.services.ollama import (
    #         get_installed_models,
    #         is_ollama_running,
    #     )
    #     running = await is_ollama_running()
    #     models = await get_installed_models() if running else []
    #     ollama_result = {
    #         "ollama_installed": running or bool(models),
    #         "ollama_running": running,
    #         "ollama_started_by_nexus": False,
    #         "model_available": any(required_model in m for m in models),
    #         "model_pulled": False,
    #         "models": models,
    #         "error": None,
    #     }
    # app.state.ollama_status = ollama_result
    # if ollama_result["ollama_running"]:
    #     started_msg = " (started by NEXUS)" if ollama_result.get("ollama_started_by_nexus") else ""
    #     print(f"Ollama: running{started_msg} - models: {ollama_result['models']}")
    # elif ollama_result["ollama_installed"]:
    #     print(
    #         "Ollama: installed but not running - "
    #         f"{ollama_result.get('error', 'not started')} "
    #         f"(autostart={'on' if settings.enable_ollama_autostart else 'off'})"
    #     )
    # else:
    #     print("Ollama: not installed - install from https://ollama.ai for local AI")


async def _shutdown(app: FastAPI) -> None:
    """Application shutdown handler."""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    await _startup(app)
    yield
    await _shutdown(app)


# FastAPI's own interactive docs (development only) are HTML with scripts.
_DOCS_PATHS = frozenset({"/docs", "/redoc", "/docs/oauth2-redirect"})


def _with_own_policy(own: str | None, global_policy: str) -> str:
    own = (own or "").strip().rstrip(";").strip()
    return f"{own}; {global_policy}" if own else global_policy


# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        # Skip security headers for WebSocket upgrade requests
        if request.url.path.startswith("/ws/") or request.headers.get("upgrade") == "websocket":
            return await call_next(request)

        response: Response = await call_next(request)

        # Not switchable: user bytes of an active type (SVG, HTML, script) never
        # run on this origin, which holds the session cookie. Sandboxed apps
        # (embeddable paths) and the dev docs carry policies of their own.
        # The built-in IdP's login pages are the one active content this origin
        # serves as itself: they are sandboxed by their own policy (no script),
        # which the net would turn into a download.
        trusted = is_idp_path(request.url.path)
        if (
            not trusted
            and not is_embeddable(request.url.path)
            and request.url.path not in _DOCS_PATHS
        ):
            harden_active_content(response.headers)

        if settings.enable_security_headers:
            # Prevent MIME type sniffing
            response.headers["X-Content-Type-Options"] = "nosniff"

            # Prevent clickjacking — allow /app-html/ and /app-preview/ assets
            # to be embedded in iframes.
            embeddable = is_embeddable(request.url.path)
            if embeddable:
                ancestors = ["'self'"]
                frontend = str(getattr(settings, "frontend_url", "") or "").rstrip("/")
                if frontend:
                    ancestors.append(frontend)
                for origin in getattr(request.app.state, "abi_cors_origins", ()):
                    origin = str(origin).rstrip("/")
                    if origin and origin not in ancestors:
                        ancestors.append(origin)
                # Allow the embedding page even when it is not listed in config
                # (e.g. http://localhost:3042 during local dev). Never for a
                # remote module's app: only Nexus may frame it.
                presented = (
                    ()
                    if request.url.path.startswith("/app-remote/")
                    else (request.headers.get("origin"), request.headers.get("referer"))
                )
                for header in presented:
                    if not header:
                        continue
                    try:
                        from urllib.parse import urlparse

                        parsed = urlparse(header)
                        # "Origin: null" (a sandboxed page) names no origin.
                        ref_origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
                        if parsed.netloc and ref_origin not in ancestors:
                            ancestors.append(ref_origin)
                    except Exception:
                        pass
                response.headers["Content-Security-Policy"] = embed_csp(
                    response.headers.get("Content-Security-Policy"), ancestors
                )
            else:
                response.headers["X-Frame-Options"] = "DENY"

            # Referrer policy, unless the route set a stricter one (remote apps).
            response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

            # Permissions policy (restrict features)
            response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

            # HSTS (only in production)
            if settings.environment == "production":
                response.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains"
                )

            # CSP (if configured) — skip bundled and preview app HTML; embed CSP set above.
            if not embeddable and not trusted:
                # The route's own policy (a sandbox) stays in front of the global one.
                own_policy = response.headers.get("Content-Security-Policy")
                if settings.content_security_policy:
                    response.headers["Content-Security-Policy"] = _with_own_policy(
                        own_policy, settings.content_security_policy
                    )
                elif settings.environment == "production":
                    # Strict default CSP for production (no 'unsafe-*').
                    # Generate a per-response nonce in case any HTML is ever served via this app.
                    import secrets

                    nonce = secrets.token_urlsafe(16)
                    csp = (
                        "default-src 'self'; "
                        "base-uri 'self'; "
                        "frame-ancestors 'none'; "
                        "object-src 'none'; "
                        f"script-src 'self' 'nonce-{nonce}'; "
                        "style-src 'self'; "
                        "img-src 'self' data: https:; "
                        "font-src 'self' data:; "
                        "connect-src 'self' https:; "
                        "upgrade-insecure-requests"
                    )
                    response.headers["Content-Security-Policy"] = _with_own_policy(own_policy, csp)
                    # Expose nonce for any upstream that may render templates (informational only)
                    response.headers["X-CSP-Nonce"] = nonce

        return response


async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "nexus-api"}


async def ollama_status():
    """Get current Ollama status - models, running state, etc."""
    return await get_ollama_status()


async def ollama_pull_model(model: str = DEFAULT_MODEL):
    """Trigger a model pull. Returns immediately, pull runs in background."""
    import asyncio

    from naas_abi.apps.nexus.apps.api.app.services.ollama import is_ollama_running, pull_model

    if not await is_ollama_running():
        return {"success": False, "error": "Ollama is not running"}

    # Start pull in background
    asyncio.create_task(pull_model(model))
    return {"success": True, "message": f"Pulling {model} in background..."}


async def ollama_ensure_ready(model: str = DEFAULT_MODEL):
    """Ensure Ollama is running and the requested model is available.

    Returns a lightweight status with a `ready` flag consumed by the frontend
    to decide whether to retry the pending chat request automatically.
    """
    result = await ensure_ollama_ready(required_model=model)
    ready = bool(
        result.get("ollama_running")
        and (result.get("model_available") or result.get("model_pulled"))
    )
    return {"ready": ready, "status": result}


def _register_startup_handlers(app: FastAPI) -> None:
    async def on_startup() -> None:
        await _startup(app)

    async def on_shutdown() -> None:
        await _shutdown(app)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def _configure_middleware(app: FastAPI) -> None:
    cors_origins = list(getattr(app.state, "abi_cors_origins", [settings.frontend_url]))
    logger = logging.getLogger(__name__)
    cors_kwargs = {
        "allow_origins": cors_origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        # X-CSRF-Token: a cookie session's requests that change state (services/oidc).
        "allow_headers": [
            "Authorization",
            "Content-Type",
            "Accept",
            "X-Requested-With",
            "X-Nexus-Cache",
            "X-CSRF-Token",
        ],
        "expose_headers": ["Content-Length", "Content-Range", "X-Nexus-Cache"],
    }
    # In local development the web dev server can bind any free port (the allocator bumps
    # to the next port when one is still in TIME_WAIT after a restart), so accept any
    # localhost origin to avoid CORS breakage on every restart. Never enabled outside local/dev.
    if settings.nexus_env == "local" or settings.environment == "development":
        cors_kwargs["allow_origin_regex"] = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
    logger.info(
        f"[CORS] Configured origins: {cors_origins} (regex: {cors_kwargs.get('allow_origin_regex')})"
    )
    # Settings pages' 24h API cache. Added before CORS so it sits inside it: cached
    # answers still go out through CORS and get its headers.
    from naas_abi.apps.nexus.apps.api.app.services.settings_cache.middleware import (
        SettingsCacheMiddleware,
    )

    app.add_middleware(SettingsCacheMiddleware)
    app.add_middleware(CORSMiddleware, **cors_kwargs)
    app.add_middleware(SecurityHeadersMiddleware)

    # Per-actor HTTP activity log. Reads ActivityLogService from
    # app.state.activity_log_service (wired by the engine); if absent,
    # the middleware is a no-op.
    from naas_abi.apps.nexus.apps.api.app.services.activity_log.HttpActivityLogMiddleware import (
        HttpActivityLogMiddleware,
    )

    app.add_middleware(HttpActivityLogMiddleware)

    # Who and which workspace each request acts for, stamped on every event.
    from naas_abi.apps.nexus.apps.api.app.services.identity_events.middleware import (
        RequestIdentityMiddleware,
    )

    app.add_middleware(RequestIdentityMiddleware)

    # Remote app pages preflight from an opaque origin, which the CORS
    # middleware refuses: answered outside it.
    from naas_abi.apps.nexus.apps.api.app.services.apps.remote.http_routes import (
        RemoteAppPreflight,
        redact_grants_in_access_log,
    )

    app.add_middleware(RemoteAppPreflight)
    # A remote app's path holds its grant: never print it in the access log.
    redact_grants_in_access_log()

    # Outermost: one span per request, around everything else (no-op unless the
    # engine config enables telemetry).
    from naas_abi.apps.nexus.apps.api.app.core.tracing import TracingMiddleware

    app.add_middleware(TracingMiddleware)


async def serve_app_html(path: str) -> FileResponse:
    """Serve a browser asset from any loaded module's apps directory.

    Resolution uses the pre-built asset-path map from the apps catalog scan
    so no module lookup is needed at request time.
    """
    from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.primary.apps__primary_adapter__FastAPI import (
        _scan_apps_html_paths,
    )

    html_map = _scan_apps_html_paths()
    file_path = html_map.get(path)
    if not file_path:
        raise HTTPException(status_code=404, detail=f"App HTML not found: {path}")

    if not Path(file_path).is_file():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(file_path)


async def serve_provider_logo(provider_id: str) -> FileResponse:
    """Serve a marketplace AI provider's logo from disk.

    Public (no auth) so plain ``<img>`` tags can load it, and
    config-independent so logos render for providers that aren't enabled —
    matching the provider catalog, which lists every module regardless of state.
    """
    from naas_abi.apps.nexus.apps.api.app.services.providers.model_catalog import (
        resolve_provider_logo_for_id,
    )

    file_path = resolve_provider_logo_for_id(provider_id)
    if file_path is None:
        raise HTTPException(status_code=404, detail=f"No logo for provider {provider_id!r}")
    return FileResponse(file_path)


def _register_routes(app: FastAPI) -> None:
    # Include API router
    app.include_router(api_router, prefix="/api")
    # Graph map layers: always mounted (empty until a module registers one), so
    # the web's request is a list, not a 404. Needs the ABI engine.
    try:
        from naas_abi.apps.nexus.apps.api.app.services.maps.adapters.primary.fastapi import (
            install_maps_layers,
        )

        install_maps_layers(app)
    except ValueError:
        logging.getLogger(__name__).info("Maps graph layers: no ABI engine, not mounted")

    app.add_api_route("/health", health_check, methods=["GET"])
    from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
        get_current_user_required,
        require_superadmin,
    )
    from naas_abi_core.apps.api.abi_api_key_auth import require_abi_api_token

    # Status reveals the internal Ollama URL and models: signed-in users only.
    # Pulling models and starting the server act on the host: superadmins only.
    app.add_api_route(
        "/api/ollama/status",
        ollama_status,
        methods=["GET"],
        dependencies=[Depends(get_current_user_required)],
    )
    app.add_api_route(
        "/api/ollama/pull",
        ollama_pull_model,
        methods=["POST"],
        dependencies=[Depends(require_superadmin)],
    )
    app.add_api_route(
        "/api/ollama/ensure-ready",
        ollama_ensure_ready,
        methods=["POST"],
        dependencies=[Depends(require_superadmin)],
    )
    # The core API's middleware already guards /app-html/; checking here too keeps
    # the route closed when Nexus is served without that middleware.
    # Apps of remote modules, forwarded over NATS. The catalog URL redirects
    # to a grant URL, before the /app-html/ catch-all below; the grant is the
    # only credential of /app-remote/.
    from naas_abi.apps.nexus.apps.api.app.services.apps.remote.http_routes import (
        METHODS as REMOTE_APP_METHODS,
    )
    from naas_abi.apps.nexus.apps.api.app.services.apps.remote.http_routes import (
        open_remote_app,
        redirect_remote_app_root,
        serve_remote_app,
    )

    # Every method: a user's request is redirected with a 307, which keeps it,
    # and an ABI_API_KEY caller's is answered directly.
    app.add_api_route(
        "/app-html/remote/{module_id}/{app}/{path:path}",
        open_remote_app,
        methods=REMOTE_APP_METHODS,
        dependencies=[Depends(require_abi_api_token)],
        include_in_schema=False,
    )
    app.add_api_route(
        "/app-html/remote/{module_id}/{app}",
        open_remote_app,
        methods=REMOTE_APP_METHODS,
        dependencies=[Depends(require_abi_api_token)],
        include_in_schema=False,
    )
    app.add_api_route(
        "/app-remote/{grant}/{module_id}/{app}/{path:path}",
        serve_remote_app,
        methods=REMOTE_APP_METHODS,
        include_in_schema=False,
    )
    app.add_api_route(
        "/app-remote/{grant}/{module_id}/{app}",
        redirect_remote_app_root,
        methods=["GET", "HEAD"],
        include_in_schema=False,
    )
    # The built-in identity provider, at its issuer URL: public (a login page
    # has nobody to authenticate yet), forwarded over NATS to the one module
    # bound to it (services/idp).
    from naas_abi.apps.nexus.apps.api.app.services.idp.http_routes import (
        METHODS as IDP_METHODS,
    )
    from naas_abi.apps.nexus.apps.api.app.services.idp.http_routes import serve_idp

    app.add_api_route(
        "/idp/{path:path}",
        serve_idp,
        methods=IDP_METHODS,
        include_in_schema=False,
    )
    app.add_api_route(
        "/app-html/{path:path}",
        serve_app_html,
        methods=["GET"],
        dependencies=[Depends(require_abi_api_token)],
    )
    from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.primary.app_projects__primary_adapter__FastAPI import (
        redirect_app_preview_root,
        serve_app_preview,
    )

    app.add_api_route("/app-preview/{token}/{path:path}", serve_app_preview, methods=["GET"])
    app.add_api_route("/app-preview/{token}", redirect_app_preview_root, methods=["GET"])
    app.add_api_route("/provider-logos/{provider_id}", serve_provider_logo, methods=["GET"])


def _first_existing_file(relative: str, *roots: Path) -> Path | None:
    """Return the first existing file under ``roots`` for a relative path."""
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        return None
    for root in roots:
        if not root.is_dir():
            continue
        candidate = (root / rel).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            continue
        if candidate.is_file():
            return candidate
    return None


def _mount_static_assets(app: FastAPI) -> None:
    # Serve static assets (logos, avatars). ``storage/logos`` in the project
    # root overlays the engine package defaults.
    abi_logos_path = Path(__file__).parent.parent / "public" / "logos"
    project_logos_path = Path.cwd() / "storage" / "logos"

    @app.get("/logos/{path:path}")
    async def serve_logo(path: str) -> FileResponse:
        found = _first_existing_file(path, project_logos_path, abi_logos_path)
        if found is None:
            raise HTTPException(status_code=404, detail="Logo not found")
        return FileResponse(found)

    avatars_path = Path(__file__).parent.parent / "public" / "avatars"
    if avatars_path.exists():
        app.mount("/avatars", StaticFiles(directory=str(avatars_path)), name="avatars")

    # Serve organization logos
    org_logos_path = Path(__file__).parent.parent / "public" / "organizations"
    if org_logos_path.exists():
        app.mount(
            "/organizations", StaticFiles(directory=str(org_logos_path)), name="organizations"
        )

    # Serve uploaded workspace logos
    uploads_path = Path(__file__).parent.parent / "uploads"
    uploads_path.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")


def create_app(app: FastAPI | None = None):
    """Create or patch a FastAPI app with NEXUS configuration."""
    if app is None:
        app = FastAPI(
            title="NEXUS API",
            description="The coordination platform API by naas.ai, powered by ABI",
            version="0.0.1",
            docs_url="/docs" if settings.debug or settings.environment == "development" else None,
            redoc_url="/redoc" if settings.debug or settings.environment == "development" else None,
            lifespan=lifespan,
        )
        attach_startup_handlers = False
    else:
        attach_startup_handlers = True

    existing_asgi = getattr(app.state, "_nexus_asgi_app", None)
    if existing_asgi is not None:
        return existing_asgi

    if not getattr(app.state, "_nexus_api_patched", False):
        if attach_startup_handlers:
            _register_startup_handlers(app)
        register_service_exception_handlers(app)
        _configure_middleware(app)
        _register_routes(app)
        _mount_static_assets(app)
        from naas_abi.apps.nexus.apps.api.app.services.apps.app_html_access import (
            register_nexus_app_html_jwt_auth,
        )

        register_nexus_app_html_jwt_auth()
        app.state._nexus_api_patched = True

    # Wrap app with WebSocket support (must be LAST, after all middleware)
    asgi_app = init_websocket(app)
    app.state._nexus_asgi_app = asgi_app
    return asgi_app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9879, reload_dirs=["src", "libs"], reload=True)  # nosec B104 - dev entrypoint only (__main__), not reachable in production
