"""Wire AppProjectsService to the engine services and Nexus settings.

Shared by the HTTP adapter and the Apps agent tools (which run in the same
process, so they call the service directly instead of a sidecar).
"""

from __future__ import annotations

from typing import Any

from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.secondary.github import (
    GitHubAppRepoPublisher,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.secondary.module_apps import (
    ModuleAppSourceDisk,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.secondary.object_storage import (
    AppDraftStoreObjectStorage,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.secondary.source_control import (
    AppProjectRepositoryGit,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.port import (
    AppProjectError,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.service import (
    AppProjectsService,
)


class AppProjectsUnavailableError(AppProjectError):
    """Git storage (Forgejo) or the object store is not configured."""


# Repos already ensured in this process: one Forgejo round trip, not one per request.
_ENSURED_REPOS: set[tuple[int, str]] = set()


def _engine_services() -> Any:
    from naas_abi import ABIModule

    return ABIModule.get_instance().engine.services


def _module_source() -> ModuleAppSourceDisk:
    from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.primary.apps__primary_adapter__FastAPI import (
        loaded_modules,
        module_app_dir,
    )

    return ModuleAppSourceDisk(app_dir=module_app_dir, modules=loaded_modules)


def _publisher() -> GitHubAppRepoPublisher:
    return GitHubAppRepoPublisher(
        repo=settings.apps_submit_repo,
        token=settings.apps_submit_token,
        base_branch=settings.apps_submit_base_branch,
        api_base=settings.apps_submit_api_base,
        web_base=settings.apps_submit_web_base,
        open_pull_request=settings.apps_submit_open_pull_request,
    )


def build_app_projects_service(
    *, source_control: Any = None, object_storage: Any = None
) -> AppProjectsService:
    services = None
    if source_control is None or object_storage is None:
        try:
            services = _engine_services()
        except Exception as exc:  # noqa: BLE001
            raise AppProjectsUnavailableError("The ABI engine is not loaded.") from exc
    try:
        sc = source_control or services.source_control
        storage = object_storage or services.object_storage
    except Exception as exc:  # noqa: BLE001
        raise AppProjectsUnavailableError(
            "App projects need git storage (Forgejo) and an object store."
        ) from exc
    repo_id = settings.coding_repo_id or "abi/monorepo"
    owner, _, name = repo_id.partition("/")
    if (id(sc), repo_id) not in _ENSURED_REPOS:
        try:
            sc.ensure_repo(owner=owner, name=name)
        except Exception as exc:  # noqa: BLE001
            raise AppProjectsUnavailableError("Git storage (Forgejo) is not reachable.") from exc
        _ENSURED_REPOS.add((id(sc), repo_id))
    return AppProjectsService(
        repository=AppProjectRepositoryGit(sc, repo_id),
        drafts=AppDraftStoreObjectStorage(storage),
        module_source=_module_source(),
        publisher=_publisher(),
    )
