from __future__ import annotations

import time
from collections.abc import Callable

from naas_abi_core.engine.call_context import (
    ANONYMOUS_PRINCIPAL,
    call_subject,
    vouched_by_first_party,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    PHASE_ERROR,
    PHASE_RUNNING,
    PHASE_STOPPED,
    AccessDeniedError,
    ICodingEnvironmentAdapter,
    ProvisionFailedError,
    ProvisionTimeoutError,
    WorkspaceAccess,
    WorkspaceNameConflictError,
    WorkspaceNotFoundError,
    WorkspaceStatus,
    WorkspaceTemplate,
)
from naas_abi_core.services.coding_environment.iam_catalog import CATALOG
from naas_abi_core.services.coding_environment.ontologies.modules.CodingEnvironmentEventOntology import (
    WorkspaceAccessGranted,
    WorkspaceDeleted,
    WorkspaceProvisioned,
    WorkspaceProvisionFailed,
    WorkspaceStarted,
    WorkspaceStopped,
)
from naas_abi_core.services.iam.guard import ServiceGuard
from naas_abi_core.services.ServiceBase import ServiceBase

# The owner segment of an environment whose owner this service does not know:
# only grants on every environment (``environment/*``) reach it.
UNKNOWN_OWNER = "-"


def _missing(workspace_id: str):
    return lambda: WorkspaceNotFoundError(f"Workspace {workspace_id} not found")


class CodingEnvironmentService(ServiceBase):
    """Domain service for orchestrating per-user coding environments.

    Business logic knows nothing about Coder; it depends only on the port.
    The operation is always the source of truth — event publishing is
    fail-safe and must never break a (long, expensive) provision.

    Every operation is authorized (``coding_environment:*``) once the
    service is wired with IAM. An environment is personal:
    ``environment/<owner principal id>/<environment id>``, placed in the call's
    target workspace when it is provisioned. The principal an operation
    concerns is the call's user, or the actor when the call is on behalf of no
    one; ``user_id`` arguments are ignored then. The owner of an environment
    comes from the orchestrator's records: the environments it lists for the
    principal's orchestrator user.
    """

    def __init__(self, adapter: ICodingEnvironmentAdapter):
        super().__init__()
        self._adapter = adapter
        self._guard = ServiceGuard.of(CATALOG, self)
        # Environment ownership is read from the
        # orchestrator for the calling principal and cached per process, and
        # the Coder adapter keeps its principal bindings per process too. After
        # a restart, or on another replica, an environment is found again once
        # its owner's orchestrator user is ensured (Nexus ensures it before each
        # per-user operation); until then it answers as not found. Persisting
        # the bindings is not done yet.
        self._owners: dict[str, str] = {}  # environment id -> owner principal

    @property
    def adapter(self) -> ICodingEnvironmentAdapter:
        """The wrapped secondary adapter -- public so callers (e.g.
        ``EngineNATSLoader``) can check what kind of adapter this service is
        backed by, mirroring ``ObjectStorageService.adapter``."""
        return self._adapter

    def __publish_event(self, event: object) -> None:
        if not self.services_wired:
            return
        if not self.services.events_available():
            return
        # The orchestration call is the source of truth; emit never raises.
        self.services.events.emit(event)

    # -- who ------------------------------------------------------------------------

    @staticmethod
    def _principal() -> str:
        """Whom a personal operation concerns (``call_subject``); an anonymous
        call concerns the anonymous principal, which IAM allows nothing."""
        return call_subject() or ANONYMOUS_PRINCIPAL.id

    def _orchestrator_user(self, principal: str) -> str:
        found = self._adapter.find_user(external_id=principal)
        if found is None:
            raise AccessDeniedError(
                "The caller has no orchestrator user yet: call ensure_user first"
            )
        return found

    def _owner(self, workspace_id: str) -> str:
        """The principal owning an environment, from the orchestrator's records."""
        owner = self._owners.get(workspace_id)
        if owner is not None:
            return owner
        principal = self._principal()
        user = self._adapter.find_user(external_id=principal)
        if user is not None:
            for env in self._adapter.list_environments(user_id=user):
                self._owners[env.id] = principal
        return self._owners.get(workspace_id, UNKNOWN_OWNER)

    def _check(self, action: str, workspace_id: str) -> None:
        if not self._guard.enforcing:
            return
        self._guard.require(
            action,
            "environment",
            [self._owner(workspace_id), workspace_id],
            not_found=_missing(workspace_id),
        )

    # -- operations ---------------------------------------------------------------

    def ensure_user(
        self, *, email: str, username: str, external_id: str | None = None
    ) -> str:
        """Ensure the orchestrator user of the call's principal; ``external_id``
        is ignored once the service checks."""
        if not self._guard.enforcing:
            return self._adapter.ensure_user(
                external_id=external_id or self._principal(),
                email=email,
                username=username,
            )
        principal = self._principal()
        self._guard.require("EnsureUser", "coder_user", principal)
        return self._adapter.ensure_user(
            external_id=principal,
            email=email,
            username=username,
            # Only a first party's word about its user's email can claim an
            # existing orchestrator user.
            vouched_email=vouched_by_first_party(),
        )

    def list_templates(self) -> list[WorkspaceTemplate]:
        return self._guard.filter(
            "ListTemplates",
            "template",
            self._adapter.list_templates(),
            lambda template: template.id,
        )

    def provision(
        self,
        *,
        template_id: str,
        name: str,
        params: dict[str, str] | None = None,
        user_id: str | None = None,
    ) -> WorkspaceStatus:
        """Provision an environment for the call's principal, placed in the
        call's target workspace. ``user_id`` is ignored once the service checks."""
        owner = user_id or ""
        if self._guard.enforcing:
            principal = self._principal()
            # Checked on the name as placed; the real id comes from the backend.
            self._guard.create(
                "Provision",
                "environment",
                [principal, "-"],
                not_found=_missing(name),
            )
            owner, user_id = principal, self._orchestrator_user(principal)
        try:
            status = self._adapter.provision(
                user_id=user_id or "",
                template_id=template_id,
                name=name,
                params=params,
            )
        except WorkspaceNameConflictError:
            # Idempotent ensure: adopt the existing workspace by name instead of
            # failing callers that re-open a deck / reopen an IDE session.
            status = self._adopt_existing(user_id=user_id or "", name=name)
        except Exception as exc:
            # workspace_id is unknown on failure; record the requested name.
            self.__publish_event(
                WorkspaceProvisionFailed(
                    user=owner, workspace_id=name, message=str(exc)
                )
            )
            raise
        if self._guard.enforcing:
            if status.id not in self._owners:
                self._owners[status.id] = owner
                self._guard.place_new("environment", [owner, status.id])
        self.__publish_event(
            WorkspaceProvisioned(
                user=owner,
                workspace_id=status.id,
                workspace_name=status.name,
                template_id=template_id,
                phase=status.phase,
            )
        )
        return status

    def _adopt_existing(self, *, user_id: str, name: str) -> WorkspaceStatus:
        envs = self._adapter.list_environments(user_id=user_id)
        existing = next((env for env in envs if env.name == name), None)
        if existing is None:
            raise WorkspaceNameConflictError(
                f"Workspace '{name}' already exists but could not be listed"
            )
        if existing.phase in (PHASE_STOPPED, "stopping"):
            return self.start(workspace_id=existing.id)
        return self.get_status(workspace_id=existing.id)

    def start(
        self, *, workspace_id: str, params: dict[str, str] | None = None
    ) -> WorkspaceStatus:
        self._check("Start", workspace_id)
        status = self._adapter.start(workspace_id=workspace_id, params=params)
        self.__publish_event(
            WorkspaceStarted(workspace_id=workspace_id, phase=status.phase)
        )
        return status

    def stop(self, *, workspace_id: str) -> WorkspaceStatus:
        self._check("Stop", workspace_id)
        status = self._adapter.stop(workspace_id=workspace_id)
        self.__publish_event(
            WorkspaceStopped(workspace_id=workspace_id, phase=status.phase)
        )
        return status

    def delete(self, *, workspace_id: str) -> None:
        self._check("Delete", workspace_id)
        owner = self._owners.get(workspace_id)
        self._adapter.delete(workspace_id=workspace_id)
        if owner is not None:
            self._guard.forget("environment", [owner, workspace_id])
            del self._owners[workspace_id]
        self.__publish_event(WorkspaceDeleted(workspace_id=workspace_id))

    def list_environments(self, *, user_id: str | None = None) -> list[WorkspaceStatus]:
        """The call's principal's environments it may list. ``user_id`` is
        ignored once the service checks."""
        if not self._guard.enforcing:
            return self._adapter.list_environments(user_id=user_id or "")
        principal = self._principal()
        user = self._adapter.find_user(external_id=principal)
        if user is None:
            return []
        envs = self._adapter.list_environments(user_id=user)
        for env in envs:
            self._owners[env.id] = principal
        return self._guard.filter(
            "ListEnvironments",
            "environment",
            envs,
            lambda env: [principal, env.id],
        )

    def list_all_environments(self) -> list[WorkspaceStatus]:
        return self._guard.filter(
            "ListAllEnvironments",
            "environment",
            self._adapter.list_all_environments(),
            lambda env: [self._owners.get(env.id, UNKNOWN_OWNER), env.id],
        )

    def get_status(self, *, workspace_id: str) -> WorkspaceStatus:
        self._check("GetStatus", workspace_id)
        return self._adapter.get_status(workspace_id=workspace_id)

    def get_logs(self, *, workspace_id: str) -> list[str]:
        self._check("GetLogs", workspace_id)
        return self._adapter.get_logs(workspace_id=workspace_id)

    def get_access(
        self, *, workspace_id: str, app_slug: str, user_id: str | None = None
    ) -> WorkspaceAccess:
        """Access for the call's principal; ``user_id`` is ignored once the
        service checks."""
        owner = user_id or ""
        if self._guard.enforcing:
            self._check("GetAccess", workspace_id)
            owner = self._principal()
            user_id = self._orchestrator_user(owner)
        access = self._adapter.get_access(
            workspace_id=workspace_id, user_id=user_id or "", app_slug=app_slug
        )
        self.__publish_event(
            WorkspaceAccessGranted(
                user=owner,
                workspace_id=workspace_id,
                app_slug=app_slug,
                token_expires_at=access.expires_at,
            )
        )
        return access

    def get_workspace_ui_url(self, *, workspace_id: str) -> str | None:
        """Coder dashboard URL when the adapter supports it; else None."""
        fn = getattr(self._adapter, "get_workspace_ui_url", None)
        if not callable(fn):
            return None
        try:
            self._check("GetStatus", workspace_id)
            return fn(workspace_id=workspace_id)
        except Exception:  # noqa: BLE001 - optional enrichment; never fail callers
            return None

    def get_runtime_binding(self, *, workspace_id: str) -> tuple[str, str] | None:
        """Return (sidecar_base, sidecar_secret) when the adapter exposes a runtime."""
        fn = getattr(self._adapter, "get_runtime_binding", None)
        if not callable(fn):
            return None
        try:
            # A sidecar secret: a credential, as GetAccess returns.
            self._check("GetAccess", workspace_id)
            return fn(workspace_id=workspace_id)
        except Exception:  # noqa: BLE001
            return None

    def get_harness_binding(self, *, workspace_id: str) -> str | None:
        """Return OpenCode (or other harness) base URL when configured."""
        fn = getattr(self._adapter, "get_harness_binding", None)
        if not callable(fn):
            return None
        try:
            self._check("GetAccess", workspace_id)
            return fn(workspace_id=workspace_id)
        except Exception:  # noqa: BLE001
            return None

    def wait_until_ready(
        self,
        *,
        workspace_id: str,
        timeout_seconds: float = 300.0,
        poll_interval_seconds: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> WorkspaceStatus:
        """Poll the workspace until its agent is ready (the §4b state machine).

        ``sleep`` and ``monotonic`` are injectable so the poll loop is fully
        deterministic under test.
        """
        self._check("GetStatus", workspace_id)
        deadline = monotonic() + timeout_seconds
        while True:
            status = self._adapter.get_status(workspace_id=workspace_id)
            if status.phase == PHASE_RUNNING and status.agent_ready:
                return status
            if status.phase == PHASE_ERROR:
                raise ProvisionFailedError(
                    f"Workspace {workspace_id} entered error state"
                )
            if monotonic() >= deadline:
                raise ProvisionTimeoutError(
                    f"Workspace {workspace_id} not ready within "
                    f"{timeout_seconds}s (phase={status.phase}, "
                    f"agent_ready={status.agent_ready})"
                )
            sleep(poll_interval_seconds)
