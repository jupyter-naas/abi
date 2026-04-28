"""Agents FastAPI primary adapter."""

from __future__ import annotations

import hashlib
import threading
import urllib.parse
import urllib.request
from dataclasses import replace
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.services.agents import (
    AgentCreateInput,
    AgentRecord,
    AgentService,
    AgentUpdateInput,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext, TokenData
from naas_abi.apps.nexus.apps.api.app.services.registry import (
    ServiceRegistry,
    get_service_registry,
)
from naas_abi_core import logger
from naas_abi_core.services.agent.Agent import Agent
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import CacheNotFoundError
from pydantic import BaseModel

router = APIRouter(dependencies=[Depends(get_current_user_required)])

# ---------------------------------------------------------------------------
# Logo download cache
#
# Downloaded logos are stored under the existing public/logos/agents/ folder
# which is already served at /logos by _mount_static_assets (main.py).
# The FS cache records the URL → local path mapping so each remote URL is
# fetched at most once across server restarts.
# ---------------------------------------------------------------------------

_logo_cache = CacheFactory.CacheFS_find_storage(subpath="nexus/agents/logos")

# parents: primary → adapters → agents(svc) → services → app → api
_AGENTS_LOGOS_DIR = Path(__file__).parents[5] / "public" / "logos" / "agents"
_PUBLIC_DIR = Path(__file__).parents[5] / "public"
_PUBLIC_LOGOS_DIR = _PUBLIC_DIR / "logos"

_ALLOWED_LOGO_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico"})


def _logo_extension_from_url(url: str) -> str:
    """Return a lowercase file extension inferred from the URL, defaulting to .png."""
    try:
        path = urllib.parse.urlparse(url).path
        ext = Path(path).suffix.lower()
        if ext in _ALLOWED_LOGO_EXTENSIONS:
            return ext
    except Exception:
        pass
    return ".png"


def _resolve_public_asset(logo_url: str) -> bytes | None:
    """Read logos already referenced from the app public directory."""
    normalized = logo_url.strip().lstrip("/")

    # Supported forms:
    # - /logos/foo.svg
    # - logos/foo.svg
    # - /public/logos/foo.svg
    # - public/logos/foo.svg
    if normalized.startswith("public/"):
        candidate = Path(normalized[7:])
    else:
        candidate = Path(normalized)

    if candidate.parts and candidate.parts[0] == "logos":
        resolved = _PUBLIC_DIR / candidate
    else:
        resolved = _PUBLIC_LOGOS_DIR / candidate

    try:
        if resolved.exists() and resolved.is_file():
            return resolved.read_bytes()
    except Exception as exc:
        logger.debug("Could not read public logo asset %s: %s", logo_url, exc)
    return None


def _resolve_package_asset(logo_url: str) -> bytes | None:
    """Read *logo_url* as a package-relative filesystem path.

    Paths like ``naas_abi_marketplace/applications/openrouter/assets/foo.svg``
    are resolved against the root of the installed Python package tree so that
    assets bundled inside any installed (or editable-installed) package can be
    served as static files.

    Returns raw bytes on success, ``None`` if the file cannot be found.
    """
    try:
        # Derive the top-level package name (first path component)
        top_pkg = logo_url.split("/")[0]
        top_mod = __import__(top_pkg)
        # parent of __init__.py → package dir; parent of that → install root
        pkg_root = Path(top_mod.__file__).parent.parent  # type: ignore[arg-type]
        resolved = pkg_root / logo_url
        if resolved.exists():
            return resolved.read_bytes()
    except Exception as exc:
        logger.debug("Could not resolve package asset %s: %s", logo_url, exc)
    return None


def _resolve_local_filesystem_asset(logo_url: str) -> bytes | None:
    """Read a logo from a direct local filesystem path."""
    try:
        path = Path(logo_url)
        if path.exists() and path.is_file():
            return path.read_bytes()
    except Exception as exc:
        logger.debug("Could not resolve local filesystem asset %s: %s", logo_url, exc)
    return None


def _ensure_logo_cache_dir() -> None:
    """Ensure FS cache directory exists before cache writes."""
    try:
        cache_dir = getattr(getattr(_logo_cache.cold, "adapter", None), "cache_dir", None)
        if isinstance(cache_dir, str) and cache_dir:
            Path(cache_dir).mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        logger.debug("Could not ensure logo cache directory: %s", exc)


def _get_cached_logo_path(cache_key: str) -> str | None:
    """Best-effort cache read that never raises."""
    try:
        _ensure_logo_cache_dir()
        if not _logo_cache.exists(cache_key):
            return None
        cached = _logo_cache.get(cache_key)
        return cached if isinstance(cached, str) else None
    except (CacheNotFoundError, Exception) as exc:
        logger.debug("Logo cache read miss for key %s: %s", cache_key, exc)
        return None


def _set_cached_logo_path(cache_key: str, local_url: str) -> None:
    """Best-effort cache write; failures must not break API responses."""
    try:
        _ensure_logo_cache_dir()
        _logo_cache.set_text(cache_key, local_url)
    except Exception as exc:
        logger.warning("Failed to cache logo path for key %s: %s", cache_key, exc)


def _fetch_logo_to_public(logo_url: str) -> str | None:
    """Copy or download *logo_url* into the public logos folder and return the
    local static URL path (e.g. ``/logos/agents/<hash>.png``).

    Supported source types:

    * **HTTP/HTTPS URLs** — fetched with ``urllib.request``.
    * **Public logo paths** (e.g. ``/logos/foo.svg`` or
      ``public/logos/foo.svg``) — read from this API app's ``public`` folder.
    * **Package-relative paths** (e.g.
      ``naas_abi_marketplace/applications/openrouter/assets/foo.svg``) —
      read directly from the installed package tree.
    * **Direct local filesystem paths** (absolute or relative) — read directly.

    The FS cache is checked first so each source is processed at most once.
    Returns ``None`` on failure so callers can fall back to the original value.
    """
    if not logo_url:
        return None

    cache_key = f"logo_{logo_url}"

    # Fast path: already processed → return the cached local URL
    cached_logo_path = _get_cached_logo_path(cache_key)
    if cached_logo_path:
        return cached_logo_path

    # Stable filename derived from the source identifier
    url_hash = hashlib.sha256(logo_url.encode()).hexdigest()[:24]
    ext = _logo_extension_from_url(logo_url)
    filename = f"{url_hash}{ext}"
    local_url = f"/logos/agents/{filename}"
    dest_path = _AGENTS_LOGOS_DIR / filename

    # File already on disk from a previous run (cache entry missing) → re-register
    if dest_path.exists():
        _set_cached_logo_path(cache_key, local_url)
        return local_url

    # Obtain raw bytes from remote/public/module/local sources
    is_remote = logo_url.lower().startswith(("http://", "https://"))
    data: bytes | None = None

    if is_remote:
        try:
            req = urllib.request.Request(logo_url, headers={"User-Agent": "Mozilla/5.0 ABI/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
                data = resp.read()
        except Exception as exc:
            logger.warning("Failed to download agent logo %s: %s", logo_url, exc)
    else:
        data = _resolve_public_asset(logo_url)
        if data is None:
            data = _resolve_package_asset(logo_url)
        if data is None:
            data = _resolve_local_filesystem_asset(logo_url)
        if data is None:
            logger.warning("Agent logo asset not found: %s", logo_url)

    if data is None:
        return None

    # Persist to the public static folder
    try:
        _AGENTS_LOGOS_DIR.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(data)
    except Exception as exc:
        logger.warning(f"Failed to save agent logo to {dest_path}: {exc}")
        return None

    # Register in cache so subsequent calls skip the copy/download
    _set_cached_logo_path(cache_key, local_url)
    return local_url


def _normalize_to_public_logo_url(logo_url: str | None) -> str | None:
    """Return a public static logo path (``/logos/...``) or ``None``."""
    if logo_url is None:
        return None

    normalized = logo_url.strip()
    if not normalized:
        return None

    if normalized.startswith("/logos/"):
        return normalized
    if normalized.startswith("logos/"):
        return f"/{normalized}"
    if normalized.startswith("/public/logos/"):
        return normalized.removeprefix("/public")
    if normalized.startswith("public/logos/"):
        return f"/{normalized[7:]}"

    return _fetch_logo_to_public(normalized)


# ---------------------------------------------------------------------------
# Process-level agent class registry cache
#
# Building this registry is expensive: it iterates every engine module and
# triggers dynamic Python imports for all ~160 agent classes.  The classes
# themselves never change at runtime, so we compute the mapping once and
# reuse it for every subsequent request.
# ---------------------------------------------------------------------------
_agent_class_registry: dict[str, type[Agent]] | None = None
_agent_class_registry_lock = threading.Lock()


def _get_agent_class_registry() -> dict[str, type[Agent]]:
    """Return (and lazily build) the process-level agent class registry.

    Thread-safe double-checked locking ensures the expensive discovery runs
    at most once even under concurrent first requests.  Agent classes are
    resolved in parallel via a thread pool to minimise startup latency.
    """
    global _agent_class_registry

    if _agent_class_registry is not None:
        return _agent_class_registry

    with _agent_class_registry_lock:
        if _agent_class_registry is not None:
            return _agent_class_registry

        from concurrent.futures import ThreadPoolExecutor, as_completed

        from naas_abi import ABIModule

        abi_module = ABIModule.get_instance()
        candidate_classes: list[type[Agent]] = list(abi_module.agents)

        for module in abi_module.engine.modules.values():
            for agent_cls in module.agents:
                if agent_cls is None:
                    continue
                candidate_classes.append(agent_cls)

        def _resolve(agent_cls: type[Agent]) -> tuple[str, type[Agent]] | None:
            name = _get_agent_class_name(agent_cls)
            if not name:
                logger.warning(
                    "Skipping agent %s because it has no resolvable name"
                    " (use class attribute 'name' or 'NAME')",
                    agent_cls,
                )
                return None
            class_name = f"{agent_cls.__module__}/{agent_cls.__name__}"
            return class_name, agent_cls

        registry: dict[str, type[Agent]] = {}
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(_resolve, c): c for c in candidate_classes}
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    class_name, agent_cls = result
                    registry[class_name] = agent_cls

        logger.info("Agent class registry built: %d agents indexed", len(registry))
        _agent_class_registry = registry
        return _agent_class_registry


class AgentsFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router


def get_agent_service(
    registry: ServiceRegistry = Depends(get_service_registry),
) -> AgentService:
    return registry.agents


def request_context(current_user: User) -> RequestContext:
    return RequestContext(
        token_data=TokenData(user_id=current_user.id, scopes={"*"}, is_authenticated=True)
    )


def _extract_agent_suggestions(agent_cls: type) -> list[dict[str, str]] | None:
    suggestions = getattr(agent_cls, "suggestions", None)
    if not isinstance(suggestions, list):
        return None

    normalized: list[dict[str, str]] = []
    for item in suggestions:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        value = item.get("value")
        if isinstance(label, str) and isinstance(value, str):
            normalized.append({"label": label, "value": value})
    return normalized


def _get_agent_class_name(agent_cls: type) -> str | None:
    name = getattr(agent_cls, "name", None)
    if isinstance(name, str):
        return name
    if isinstance(name, property):
        name = getattr(agent_cls, "NAME", None)
    return name if isinstance(name, str) else None


def _get_agent_class_description(agent_cls: type) -> str | None:
    desc = getattr(agent_cls, "description", None)
    if isinstance(desc, str):
        return desc
    if isinstance(desc, property):
        desc = getattr(agent_cls, "DESCRIPTION", None)
    return desc if isinstance(desc, str) else None


def _get_agent_system_prompt(agent_cls: type) -> str | None:
    system_prompt = getattr(agent_cls, "system_prompt", None)
    if isinstance(system_prompt, str):
        return system_prompt
    from naas_abi_core.services.agent.Agent import AgentConfiguration

    config = AgentConfiguration()
    return config.get_system_prompt([])


def _extract_agent_intents(agent_cls: type) -> list[dict[str, str]] | None:
    raw = getattr(agent_cls, "intents", None)
    if not isinstance(raw, list) or not raw:
        return None

    output: list[dict[str, str]] = []
    for item in raw:
        if not hasattr(item, "intent_value") or not hasattr(item, "intent_type"):
            continue

        intent_payload: dict[str, str] = {
            "intent_value": getattr(item, "intent_value", ""),
            "intent_type": getattr(item.intent_type, "value", str(item.intent_type)),
            "intent_target": str(getattr(item, "intent_target", "")),
        }
        scope = getattr(item, "intent_scope", None)
        if scope is not None and hasattr(scope, "value"):
            intent_payload["intent_scope"] = scope.value
        else:
            intent_payload["intent_scope"] = str(scope) if scope is not None else ""

        output.append(intent_payload)

    return output if output else None


class AgentLogoUpdateRequest(BaseModel):
    logo_url: str


@router.get("/")
async def list_agents(
    workspace_id: str | None = None,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> list[AgentRecord]:
    if not workspace_id:
        return []

    await require_workspace_access(current_user.id, workspace_id)

    # Retrieve agent records from the database (fast)
    agent_list = await agent_service.list_workspace_agents(
        context=request_context(current_user),
        workspace_id=workspace_id,
    )
    existing_agents_by_class_name = {
        agent.class_name: agent for agent in agent_list if agent.class_name
    }

    # Retrieve the cached class registry — expensive only on the very first call
    # (triggers dynamic Python imports for all agent modules).  Subsequent calls
    # return instantly from the process-level cache.
    class_name_to_agent_class = _get_agent_class_registry()

    # Persist any newly discovered agent classes to the database
    for class_name, agent_cls in class_name_to_agent_class.items():
        if class_name in existing_agents_by_class_name:
            continue

        name = _get_agent_class_name(agent_cls)
        if name is None:
            continue
        description = _get_agent_class_description(agent_cls)
        enabled = name == "Abi"

        logger.debug("Creating agent in nexus backend: %s", name)
        system_prompt = _get_agent_system_prompt(agent_cls)
        created_agent = await agent_service.create_agent(
            context=request_context(current_user),
            data=AgentCreateInput(
                name=name,
                description=description or "",
                workspace_id=workspace_id,
                class_name=class_name,
                provider="abi",
                enabled=enabled,
                system_prompt=system_prompt,
            ),
        )
        agent_list.append(created_agent)
        existing_agents_by_class_name[class_name] = created_agent

    # Enrich DB records with class-level metadata (suggestions, logo, intents)
    enriched_agent_list: list[AgentRecord] = []
    for agent in agent_list:
        suggestions = None
        logo_url = _normalize_to_public_logo_url(agent.logo_url)
        intents = None
        if agent.class_name:
            resolved_cls = class_name_to_agent_class.get(agent.class_name)
            if resolved_cls is not None and isinstance(resolved_cls, type):
                suggestions = _extract_agent_suggestions(resolved_cls)
                if logo_url is None:
                    raw_logo_url = getattr(resolved_cls, "logo_url", None)
                    logo_url = (
                        _normalize_to_public_logo_url(raw_logo_url)
                        if isinstance(raw_logo_url, str)
                        else None
                    )
                intents = _extract_agent_intents(resolved_cls)
        enriched_agent_list.append(
            replace(agent, suggestions=suggestions, logo_url=logo_url, intents=intents)
        )

    return enriched_agent_list


@router.post("/")
async def create_agent(
    agent: AgentCreateInput,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentRecord:
    await require_workspace_access(current_user.id, agent.workspace_id)
    normalized_logo_url = _normalize_to_public_logo_url(agent.logo_url)
    created_agent = await agent_service.create_agent(
        context=request_context(current_user),
        data=replace(agent, logo_url=normalized_logo_url),
    )
    logger.debug("Agent created: %s", created_agent)
    return replace(created_agent, logo_url=_normalize_to_public_logo_url(created_agent.logo_url))


@router.patch("/{agent_id}")
async def update_agent(
    agent_id: str,
    updates: AgentUpdateInput,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentRecord:
    existing_agent = await agent_service.get_agent(
        context=request_context(current_user),
        agent_id=agent_id,
    )
    if not existing_agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await require_workspace_access(current_user.id, existing_agent.workspace_id)

    updated_agent = await agent_service.update_agent(
        context=request_context(current_user),
        agent_id=agent_id,
        updates=AgentUpdateInput(
            name=updates.name,
            description=updates.description,
            system_prompt=updates.system_prompt,
            model_id=updates.model,
            logo_url=_normalize_to_public_logo_url(updates.logo_url),
            enabled=updates.enabled,
        ),
    )
    if updated_agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return replace(updated_agent, logo_url=_normalize_to_public_logo_url(updated_agent.logo_url))


@router.patch("/{agent_id}/logo")
async def update_agent_logo(
    agent_id: str,
    payload: AgentLogoUpdateRequest,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentRecord:
    existing_agent = await agent_service.get_agent(
        context=request_context(current_user),
        agent_id=agent_id,
    )
    if not existing_agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await require_workspace_access(current_user.id, existing_agent.workspace_id)

    logo_url = _normalize_to_public_logo_url(payload.logo_url)
    if not logo_url:
        raise HTTPException(status_code=400, detail="Unable to resolve logo to a public asset")

    updated_agent = await agent_service.update_agent(
        context=request_context(current_user),
        agent_id=agent_id,
        updates=AgentUpdateInput(logo_url=logo_url),
    )
    if updated_agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    return replace(updated_agent, logo_url=_normalize_to_public_logo_url(updated_agent.logo_url))


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> dict[str, str]:
    existing_agent = await agent_service.get_agent(
        context=request_context(current_user),
        agent_id=agent_id,
    )
    if not existing_agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await require_workspace_access(current_user.id, existing_agent.workspace_id)
    await agent_service.delete_agent(
        context=request_context(current_user),
        agent_id=agent_id,
    )
    return {"status": "deleted"}


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user_required),
    agent_service: AgentService = Depends(get_agent_service),
) -> AgentRecord:
    agent = await agent_service.get_agent(
        context=request_context(current_user),
        agent_id=agent_id,
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await require_workspace_access(current_user.id, agent.workspace_id)
    return replace(agent, logo_url=_normalize_to_public_logo_url(agent.logo_url))
