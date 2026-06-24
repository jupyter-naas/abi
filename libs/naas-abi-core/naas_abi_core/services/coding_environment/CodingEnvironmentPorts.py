from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Normalized, backend-agnostic DTOs
# ---------------------------------------------------------------------------
# These deliberately collapse the backing orchestrator's enums into a small,
# stable vocabulary so a future adapter (Gitpod, devcontainer, k8s, ...) can
# satisfy the same port without leaking Coder concepts into the domain.

# Normalized lifecycle phases.
PHASE_PROVISIONING = "provisioning"
PHASE_RUNNING = "running"
PHASE_STOPPED = "stopped"
PHASE_ERROR = "error"


@dataclass(frozen=True)
class WorkspaceTemplate:
    id: str
    name: str
    active_version_id: str


@dataclass(frozen=True)
class WorkspaceStatus:
    id: str
    name: str
    phase: str  # one of PHASE_*
    agent_ready: bool = False


@dataclass(frozen=True)
class WorkspaceAccess:
    """Everything the frontend needs to embed the editor.

    ``url`` is the public, embeddable app URL (subdomain form). When the
    backing orchestrator authenticates apps via a session-token redemption
    handshake, ``url`` already carries the redemption query parameter and
    ``token`` is the raw scoped token (so the caller can rebuild the URL if
    needed). ``token`` MUST never be the deployment admin token.
    """

    url: str
    token: str | None = None
    expires_at: str | None = None


# ---------------------------------------------------------------------------
# Normalized error taxonomy (part of the port contract)
# ---------------------------------------------------------------------------
# A swappable port needs a normalized *error* contract, not just normalized
# phases. Every adapter maps its backend's failures onto these.


class CodingEnvironmentError(Exception):
    def __init__(self, message: str = "", *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class ProvisionFailedError(CodingEnvironmentError):
    """The build/provision job failed or was canceled."""


class ProvisionTimeoutError(CodingEnvironmentError):
    """Provisioning exceeded the allotted timeout budget."""


class AgentNeverConnectedError(CodingEnvironmentError):
    """The build succeeded but the workspace agent never reported ready."""


class TemplateNotFoundError(CodingEnvironmentError):
    """The requested template does not exist."""


class WorkspaceNotFoundError(CodingEnvironmentError):
    """The requested workspace does not exist."""


class WorkspaceNameConflictError(CodingEnvironmentError):
    """A workspace with that name already exists for the user."""


class QuotaExceededError(CodingEnvironmentError):
    """The user/organization workspace quota is exhausted."""


class AccessDeniedError(CodingEnvironmentError):
    """RBAC / scope denial (401/403)."""


class ICodingEnvironmentAdapter(ABC):
    """Secondary (driven) port for a coding-environment orchestrator."""

    @abstractmethod
    def ensure_user(self, *, external_id: str, email: str, username: str) -> str:
        """Idempotently ensure an orchestrator user exists; return its id."""
        raise NotImplementedError()

    @abstractmethod
    def list_templates(self) -> list[WorkspaceTemplate]:
        raise NotImplementedError()

    @abstractmethod
    def provision(
        self,
        *,
        user_id: str,
        template_id: str,
        name: str,
        params: dict[str, str] | None = None,
    ) -> WorkspaceStatus:
        """Create a workspace from a template and kick off its first build."""
        raise NotImplementedError()

    @abstractmethod
    def start(self, *, workspace_id: str) -> WorkspaceStatus:
        raise NotImplementedError()

    @abstractmethod
    def stop(self, *, workspace_id: str) -> WorkspaceStatus:
        raise NotImplementedError()

    @abstractmethod
    def delete(self, *, workspace_id: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    def list_environments(self, *, user_id: str) -> list[WorkspaceStatus]:
        """List the workspaces owned by ``user_id`` (newest-first if known)."""
        raise NotImplementedError()

    @abstractmethod
    def get_status(self, *, workspace_id: str) -> WorkspaceStatus:
        raise NotImplementedError()

    @abstractmethod
    def get_logs(self, *, workspace_id: str) -> list[str]:
        """Recent provisioning + startup log lines, for showing live progress
        while a workspace is being prepared."""
        raise NotImplementedError()

    @abstractmethod
    def get_access(
        self, *, workspace_id: str, user_id: str, app_slug: str
    ) -> WorkspaceAccess:
        """Mint scoped access for ``user_id`` and return an embeddable URL."""
        raise NotImplementedError()
