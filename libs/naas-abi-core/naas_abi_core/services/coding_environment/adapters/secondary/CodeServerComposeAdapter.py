from __future__ import annotations

from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    ICodingEnvironmentAdapter,
    PHASE_RUNNING,
    WorkspaceAccess,
    WorkspaceStatus,
    WorkspaceTemplate,
)


class CodeServerComposeAdapter(ICodingEnvironmentAdapter):
    """A single, always-on code-server declared as a docker-compose service.

    No Coder, no Terraform, no docker.sock — the container's lifecycle is owned
    by docker-compose, and this adapter just exposes it through the
    ``ICodingEnvironmentAdapter`` port so the domain service, UIs, and agents
    are identical regardless of backend.

    Tradeoff vs. ``CoderAdapter``: this is ONE shared editor, not per-user
    isolated, dynamically-provisioned workspaces. Ideal for the bundled stack
    and the "simpler UI" use case; use ``CoderAdapter`` when you need per-user
    isolation / autostop at scale.

    ``url`` is the public, embeddable code-server URL (e.g.
    ``https://code-server.example.com/``). ``workspace_id`` is a fixed synthetic
    id since there is exactly one environment.
    """

    WORKSPACE_ID = "code-server"

    def __init__(self, *, url: str) -> None:
        self._url = url.rstrip("/") + "/"

    def ensure_user(self, *, external_id: str, email: str, username: str) -> str:
        # No per-user identity in the shared-container model; echo the caller's id.
        return external_id

    def list_templates(self) -> list[WorkspaceTemplate]:
        return [
            WorkspaceTemplate(
                id=self.WORKSPACE_ID, name="code-server", active_version_id="static"
            )
        ]

    def _running(self, name: str | None = None) -> WorkspaceStatus:
        return WorkspaceStatus(
            id=self.WORKSPACE_ID,
            name=name or self.WORKSPACE_ID,
            phase=PHASE_RUNNING,
            agent_ready=True,
        )

    def provision(
        self,
        *,
        user_id: str,
        template_id: str,
        name: str,
        params: dict[str, str] | None = None,
    ) -> WorkspaceStatus:
        # The container is always up; provisioning is a no-op that reports ready.
        return self._running(name)

    def list_environments(self, *, user_id: str) -> list[WorkspaceStatus]:
        # Exactly one always-on shared editor.
        return [self._running()]

    def start(self, *, workspace_id: str) -> WorkspaceStatus:
        return self._running()

    def stop(self, *, workspace_id: str) -> WorkspaceStatus:
        # Lifecycle is compose-managed; we cannot stop a shared container.
        return self._running()

    def delete(self, *, workspace_id: str) -> None:
        # Lifecycle is compose-managed; nothing to delete.
        return None

    def get_status(self, *, workspace_id: str) -> WorkspaceStatus:
        return self._running()

    def get_access(
        self, *, workspace_id: str, user_id: str, app_slug: str
    ) -> WorkspaceAccess:
        # Same registrable domain as the frontend => code-server's own session
        # cookie is first-party in the iframe; no token to pass through.
        return WorkspaceAccess(url=self._url, token=None, expires_at=None)
