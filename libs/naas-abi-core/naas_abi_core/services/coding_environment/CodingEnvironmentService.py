from __future__ import annotations

import time
from collections.abc import Callable

from naas_abi_core import logger
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    PHASE_ERROR,
    PHASE_RUNNING,
    PHASE_STOPPED,
    ICodingEnvironmentAdapter,
    ProvisionFailedError,
    ProvisionTimeoutError,
    WorkspaceAccess,
    WorkspaceNameConflictError,
    WorkspaceStatus,
    WorkspaceTemplate,
)
from naas_abi_core.services.coding_environment.ontologies.modules.CodingEnvironmentEventOntology import (
    WorkspaceAccessGranted,
    WorkspaceDeleted,
    WorkspaceProvisioned,
    WorkspaceProvisionFailed,
    WorkspaceStarted,
    WorkspaceStopped,
)
from naas_abi_core.services.ServiceBase import ServiceBase


class CodingEnvironmentService(ServiceBase):
    """Domain service for orchestrating per-user coding environments.

    Business logic knows nothing about Coder; it depends only on the port.
    The operation is always the source of truth — event publishing is
    fail-safe and must never break a (long, expensive) provision.
    """

    def __init__(self, adapter: ICodingEnvironmentAdapter):
        super().__init__()
        self._adapter = adapter

    def __publish_event(self, event: object) -> None:
        if not self.services_wired:
            return
        if not self.services.events_available():
            return
        try:
            self.services.events.publish(event)
        except Exception as exc:  # noqa: BLE001
            # The orchestration call is the source of truth; event logging
            # must never break it.
            logger.warning(
                f"CodingEnvironmentService: failed to publish event: {exc}"
            )

    def ensure_user(self, *, external_id: str, email: str, username: str) -> str:
        return self._adapter.ensure_user(
            external_id=external_id, email=email, username=username
        )

    def list_templates(self) -> list[WorkspaceTemplate]:
        return self._adapter.list_templates()

    def provision(
        self,
        *,
        user_id: str,
        template_id: str,
        name: str,
        params: dict[str, str] | None = None,
    ) -> WorkspaceStatus:
        try:
            status = self._adapter.provision(
                user_id=user_id,
                template_id=template_id,
                name=name,
                params=params,
            )
        except WorkspaceNameConflictError:
            # Idempotent ensure: adopt the existing workspace by name instead of
            # failing callers that re-open a deck / reopen an IDE session.
            status = self._adopt_existing(user_id=user_id, name=name)
        except Exception as exc:
            # workspace_id is unknown on failure; record the requested name.
            self.__publish_event(
                WorkspaceProvisionFailed(
                    user=user_id, workspace_id=name, message=str(exc)
                )
            )
            raise
        self.__publish_event(
            WorkspaceProvisioned(
                user=user_id,
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
        status = self._adapter.start(workspace_id=workspace_id, params=params)
        self.__publish_event(
            WorkspaceStarted(workspace_id=workspace_id, phase=status.phase)
        )
        return status

    def stop(self, *, workspace_id: str) -> WorkspaceStatus:
        status = self._adapter.stop(workspace_id=workspace_id)
        self.__publish_event(
            WorkspaceStopped(workspace_id=workspace_id, phase=status.phase)
        )
        return status

    def delete(self, *, workspace_id: str) -> None:
        self._adapter.delete(workspace_id=workspace_id)
        self.__publish_event(WorkspaceDeleted(workspace_id=workspace_id))

    def list_environments(self, *, user_id: str) -> list[WorkspaceStatus]:
        return self._adapter.list_environments(user_id=user_id)

    def get_status(self, *, workspace_id: str) -> WorkspaceStatus:
        return self._adapter.get_status(workspace_id=workspace_id)

    def get_logs(self, *, workspace_id: str) -> list[str]:
        return self._adapter.get_logs(workspace_id=workspace_id)

    def get_access(
        self, *, workspace_id: str, user_id: str, app_slug: str
    ) -> WorkspaceAccess:
        access = self._adapter.get_access(
            workspace_id=workspace_id, user_id=user_id, app_slug=app_slug
        )
        self.__publish_event(
            WorkspaceAccessGranted(
                user=user_id,
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
            return fn(workspace_id=workspace_id)
        except Exception:  # noqa: BLE001 - optional enrichment; never fail callers
            return None

    def get_runtime_binding(self, *, workspace_id: str) -> tuple[str, str] | None:
        """Return (sidecar_base, sidecar_secret) when the adapter exposes a runtime."""
        fn = getattr(self._adapter, "get_runtime_binding", None)
        if not callable(fn):
            return None
        try:
            return fn(workspace_id=workspace_id)
        except Exception:  # noqa: BLE001
            return None

    def get_harness_binding(self, *, workspace_id: str) -> str | None:
        """Return OpenCode (or other harness) base URL when configured."""
        fn = getattr(self._adapter, "get_harness_binding", None)
        if not callable(fn):
            return None
        try:
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
