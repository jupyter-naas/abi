from __future__ import annotations

from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    ICodingEnvironmentAdapter,
    PHASE_PROVISIONING,
    PHASE_RUNNING,
    PHASE_STOPPED,
    WorkspaceAccess,
    WorkspaceNameConflictError,
    WorkspaceNotFoundError,
    WorkspaceStatus,
    WorkspaceTemplate,
)


class InMemoryAdapter(ICodingEnvironmentAdapter):
    """In-process fake orchestrator.

    Fully functional for unit-testing the domain and for driving the
    prototype frontend without a live Coder. ``polls_until_ready`` simulates
    a workspace that takes a few ``get_status`` polls to become ready, so the
    domain's ``wait_until_ready`` state machine can be exercised.
    """

    def __init__(self, *, polls_until_ready: int = 0) -> None:
        self._users: dict[str, str] = {}  # username -> user id
        self._workspaces: dict[str, dict] = {}  # workspace id -> record
        self._counter = 0
        self._polls_until_ready = polls_until_ready

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter}"

    def ensure_user(self, *, external_id: str, email: str, username: str) -> str:
        if username not in self._users:
            self._users[username] = self._next_id("user")
        return self._users[username]

    def list_templates(self) -> list[WorkspaceTemplate]:
        return [
            WorkspaceTemplate(
                id="tmpl-default", name="default", active_version_id="ver-1"
            )
        ]

    def provision(
        self,
        *,
        user_id: str,
        template_id: str,
        name: str,
        params: dict[str, str] | None = None,
    ) -> WorkspaceStatus:
        for record in self._workspaces.values():
            if record["user_id"] == user_id and record["name"] == name:
                raise WorkspaceNameConflictError(
                    f"workspace '{name}' already exists for user {user_id}"
                )
        workspace_id = self._next_id("ws")
        ready = self._polls_until_ready <= 0
        self._workspaces[workspace_id] = {
            "name": name,
            "user_id": user_id,
            "template_id": template_id,
            "phase": PHASE_RUNNING if ready else PHASE_PROVISIONING,
            "agent_ready": ready,
            "polls_left": self._polls_until_ready,
        }
        return self._status(workspace_id)

    def _record(self, workspace_id: str) -> dict:
        if workspace_id not in self._workspaces:
            raise WorkspaceNotFoundError(workspace_id)
        return self._workspaces[workspace_id]

    def _status(self, workspace_id: str) -> WorkspaceStatus:
        record = self._record(workspace_id)
        return WorkspaceStatus(
            id=workspace_id,
            name=record["name"],
            phase=record["phase"],
            agent_ready=record["agent_ready"],
        )

    def get_status(self, *, workspace_id: str) -> WorkspaceStatus:
        record = self._record(workspace_id)
        if record["phase"] == PHASE_PROVISIONING:
            if record["polls_left"] > 0:
                record["polls_left"] -= 1
            if record["polls_left"] <= 0:
                record["phase"] = PHASE_RUNNING
                record["agent_ready"] = True
        return self._status(workspace_id)

    def start(self, *, workspace_id: str) -> WorkspaceStatus:
        record = self._record(workspace_id)
        record["phase"] = PHASE_RUNNING
        record["agent_ready"] = True
        return self._status(workspace_id)

    def stop(self, *, workspace_id: str) -> WorkspaceStatus:
        record = self._record(workspace_id)
        record["phase"] = PHASE_STOPPED
        record["agent_ready"] = False
        return self._status(workspace_id)

    def delete(self, *, workspace_id: str) -> None:
        self._record(workspace_id)
        self._workspaces.pop(workspace_id, None)

    def get_access(
        self, *, workspace_id: str, user_id: str, app_slug: str
    ) -> WorkspaceAccess:
        record = self._record(workspace_id)
        token = self._next_id("token")
        url = (
            f"https://{app_slug}--main--{record['name']}--{user_id}"
            f".coder.local/?coder_session_token={token}"
        )
        return WorkspaceAccess(url=url, token=token, expires_at=None)
