from __future__ import annotations

import re
import secrets
from typing import Any
from urllib.parse import quote

from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    AccessDeniedError,
    CodingEnvironmentError,
    ICodingEnvironmentAdapter,
    PHASE_ERROR,
    PHASE_PROVISIONING,
    PHASE_RUNNING,
    PHASE_STOPPED,
    WorkspaceAccess,
    WorkspaceNameConflictError,
    WorkspaceNotFoundError,
    WorkspaceStatus,
    WorkspaceTemplate,
)

# Coder build/workspace status strings -> normalized phase.
_RUNNING = {"running"}
_STOPPED = {"stopped", "deleted"}
_ERROR = {"failed", "canceled"}


class CoderAdapter(ICodingEnvironmentAdapter):
    """Secondary adapter for Coder OSS (~v2.34.x) over its REST API.

    Headless: a backend service holds the deployment admin token and acts on
    behalf of users. The ``session`` is injectable (anything with a
    ``requests``-style ``.request()``), so the adapter is unit-testable
    without a network.

    NOTE: a few details (scoped-token ``scopes``/``allow_list`` shape, the
    app-proxy ``coder_session_token`` redemption query param) are flagged
    UNCERTAIN in the assessment and must be validated against the live
    deployment in the embedding prototype.
    """

    def __init__(
        self,
        *,
        access_url: str,
        wildcard_access_url: str,
        admin_token: str,
        organization: str = "default",
        default_template_id: str | None = None,
        default_token_lifetime_seconds: int = 3600,
        workspace_autostop_ms: int = 3_600_000,
        timeout: int = 30,
        session: Any | None = None,
    ) -> None:
        self._access_url = access_url.rstrip("/")
        self._wildcard_access_url = wildcard_access_url
        self._admin_token = admin_token
        self._organization = organization
        self._default_template_id = default_template_id
        self._token_lifetime_seconds = default_token_lifetime_seconds
        self._workspace_autostop_ms = workspace_autostop_ms
        self._timeout = timeout
        self._session = session if session is not None else _default_session()
        self._org_id: str | None = None

    # -- HTTP plumbing ------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json: dict | None = None,
    ) -> dict:
        url = f"{self._access_url}/api/v2{path}"
        headers = {
            "Coder-Session-Token": token or self._admin_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        response = self._session.request(
            method, url, headers=headers, json=json, timeout=self._timeout
        )
        status = getattr(response, "status_code", 0)
        if status >= 400:
            self._raise_for_status(status, _safe_text(response))
        if not getattr(response, "content", b""):
            return {}
        return response.json()

    @staticmethod
    def _raise_for_status(status: int, detail: str) -> None:
        if status in (401, 403):
            raise AccessDeniedError(detail or "access denied", status=status)
        if status == 404 or (status == 400 and "uuid" in detail.lower()):
            # 404 = no such workspace; 400 "Invalid UUID" = a malformed id (e.g.
            # a stale id left from a previously-configured backend). Both mean
            # the workspace can't be acted on -> not found.
            raise WorkspaceNotFoundError(
                detail or "workspace not found", status=status
            )
        if status == 409:
            raise WorkspaceNameConflictError(
                detail or "name conflict", status=status
            )
        raise CodingEnvironmentError(
            f"Coder API request failed ({status}): {detail}", status=status
        )

    def _organization_id(self) -> str:
        if self._org_id is None:
            org = self._request("GET", f"/organizations/{self._organization}")
            self._org_id = org["id"]
        return self._org_id

    # -- Port implementation ------------------------------------------------

    def ensure_user(self, *, external_id: str, email: str, username: str) -> str:
        # Coder usernames are strict (lowercase alphanumeric + single hyphens,
        # <=32 chars); map the display name / email to a valid one.
        coder_username = (
            _sanitize_coder_username(username)
            or _sanitize_coder_username(email.split("@", 1)[0])
            or "abi-user"
        )
        try:
            user = self._request("GET", f"/users/{coder_username}")
            return self._activate_if_needed(user)
        except CodingEnvironmentError as exc:
            if exc.status != 404:
                raise
        created = self._request(
            "POST",
            "/users",
            json={
                "email": email,
                "username": coder_username,
                # login_type=none: user has no native login; only the backend's
                # admin-minted tokens can act as them. (Deprecated upstream in
                # favour of Premium service accounts — see assessment §5.)
                "login_type": "none",
                "organization_ids": [self._organization_id()],
            },
        )
        return self._activate_if_needed(created)

    def _activate_if_needed(self, user: dict) -> str:
        """Ensure the Coder user is active and return its id.

        API-created ``login_type=none`` users are parked as ``dormant``; a
        dormant user can't own workspaces or have tokens minted ("User is not
        active … contact an admin"). Activate unless already active, and
        tolerate the "already active" race (400) so repeated ensure_user stays
        idempotent.
        """
        user_id = user["id"]
        # Coder user statuses are active | dormant | suspended; only the latter
        # two need reactivating. (Missing status -> nothing to do.)
        if user.get("status") not in ("dormant", "suspended"):
            return user_id
        try:
            self._request("PUT", f"/users/{user_id}/status/activate")
        except CodingEnvironmentError as exc:
            if exc.status != 400:
                raise
        return user_id

    def list_templates(self) -> list[WorkspaceTemplate]:
        org = self._organization_id()
        templates = self._request("GET", f"/organizations/{org}/templates")
        items = templates if isinstance(templates, list) else templates.get("templates", [])
        return [
            WorkspaceTemplate(
                id=t["id"],
                name=t.get("name", ""),
                active_version_id=t.get("active_version_id", ""),
            )
            for t in items
        ]

    def provision(
        self,
        *,
        user_id: str,
        template_id: str,
        name: str,
        params: dict[str, str] | None = None,
    ) -> WorkspaceStatus:
        org = self._organization_id()
        body: dict[str, Any] = {
            "template_id": template_id,
            "name": name,
            "automatic_updates": "never",
        }
        if self._workspace_autostop_ms:
            body["ttl_ms"] = self._workspace_autostop_ms
        if params:
            body["rich_parameter_values"] = [
                {"name": k, "value": v} for k, v in params.items()
            ]
        workspace = self._request(
            "POST",
            f"/organizations/{org}/members/{user_id}/workspaces",
            json=body,
        )
        return self._to_status(workspace)

    def start(self, *, workspace_id: str) -> WorkspaceStatus:
        self._build(workspace_id, "start")
        return self.get_status(workspace_id=workspace_id)

    def stop(self, *, workspace_id: str) -> WorkspaceStatus:
        self._build(workspace_id, "stop")
        return self.get_status(workspace_id=workspace_id)

    def delete(self, *, workspace_id: str) -> None:
        self._build(workspace_id, "delete")

    def _build(self, workspace_id: str, transition: str) -> dict:
        return self._request(
            "POST",
            f"/workspaces/{workspace_id}/builds",
            json={"transition": transition},
        )

    def list_environments(self, *, user_id: str) -> list[WorkspaceStatus]:
        # Coder's workspace filter matches by owner *username*, not id, so
        # resolve the username from the user id first, then list.
        user = self._request("GET", f"/users/{user_id}")
        owner = user.get("username") or user_id
        query = quote(f"owner:{owner}", safe=":")
        result = self._request("GET", f"/workspaces?q={query}")
        items = result.get("workspaces", []) if isinstance(result, dict) else result
        return [self._to_status(w) for w in (items or [])]

    def get_status(self, *, workspace_id: str) -> WorkspaceStatus:
        workspace = self._request("GET", f"/workspaces/{workspace_id}")
        return self._to_status(workspace)

    def get_access(
        self, *, workspace_id: str, user_id: str, app_slug: str
    ) -> WorkspaceAccess:
        token = self._mint_token(user_id=user_id, workspace_id=workspace_id)
        workspace = self._request("GET", f"/workspaces/{workspace_id}")
        owner = workspace.get("owner_name") or user_id
        name = workspace.get("name", "")
        agent = self._first_agent_name(workspace) or "main"
        host = self._app_host()
        base_url = self.build_app_url(
            slug=app_slug,
            agent=agent,
            workspace=name,
            owner=owner,
            wildcard_host=host,
        )
        # The token seeds a first-party app-proxy cookie via the redemption
        # query param; it is NOT a header the iframe could send. (§5a)
        url = f"{base_url}?coder_session_token={token}"
        return WorkspaceAccess(url=url, token=token, expires_at=None)

    # -- helpers ------------------------------------------------------------

    def _mint_token(self, *, user_id: str, workspace_id: str) -> str:
        # Go time.Duration serializes to integer nanoseconds.
        lifetime_ns = self._token_lifetime_seconds * 1_000_000_000
        # Preferred: a token scoped to opening apps. The exact scope/allow_list
        # schema is Coder-version-dependent (verified against v2.34.1: the field
        # is singular `scope`, and the `[{type,id}]` allow_list shape is
        # rejected), so fall back to a basic token if the scoped form is refused.
        # Unique per mint: get_access is called repeatedly (page load / resume)
        # and Coder rejects a duplicate token name.
        token_name = f"abi-{workspace_id}-{secrets.token_hex(4)}"
        scoped_body = {
            "token_name": token_name,
            "lifetime": lifetime_ns,
            "scope": "application_connect",
        }
        minimal_body = {
            "token_name": token_name,
            "lifetime": lifetime_ns,
        }
        for body in (scoped_body, minimal_body):
            try:
                result = self._request(
                    "POST", f"/users/{user_id}/keys/tokens", json=body
                )
                return result["key"]
            except CodingEnvironmentError as exc:
                if exc.status == 400 and body is scoped_body:
                    continue  # scoped form not accepted; retry with a basic token
                raise
        raise CodingEnvironmentError("failed to mint token")

    def _app_host(self) -> str:
        host = self._request("GET", "/applications/host")
        # API returns {"host": "*.coder.example.com"}; fall back to config.
        raw = host.get("host") or self._wildcard_access_url
        # Coder appends the access-URL port (the internal HTTP port, e.g. :7080)
        # to the wildcard it echoes. Apps are reached through the TLS edge on the
        # standard https port, so strip that internal port — otherwise the iframe
        # loads https://…:7080 (plaintext) and the TLS handshake fails
        # (SSL_ERROR_RX_RECORD_TOO_LONG).
        return re.sub(r":\d+$", "", raw)

    @staticmethod
    def _first_agent_name(workspace: dict) -> str | None:
        for resource in (
            workspace.get("latest_build", {}).get("resources", []) or []
        ):
            for agent in resource.get("agents", []) or []:
                if agent.get("name"):
                    return agent["name"]
        return None

    @staticmethod
    def build_app_url(
        *, slug: str, agent: str, workspace: str, owner: str, wildcard_host: str
    ) -> str:
        """Assemble the subdomain app URL (§4c).

        ``wildcard_host`` is the ``*.coder.example.com`` form returned by
        ``GET /applications/host``.
        """
        base = wildcard_host[2:] if wildcard_host.startswith("*.") else wildcard_host
        subdomain = f"{slug}--{agent}--{workspace}--{owner}".lower()
        return f"https://{subdomain}.{base}/"

    @classmethod
    def _to_status(cls, workspace: dict) -> WorkspaceStatus:
        phase = cls._normalize_phase(workspace)
        return WorkspaceStatus(
            id=workspace.get("id", ""),
            name=workspace.get("name", ""),
            phase=phase,
            agent_ready=(phase == PHASE_RUNNING and cls._agent_connected(workspace)),
        )

    @staticmethod
    def _normalize_phase(workspace: dict) -> str:
        build = workspace.get("latest_build", {}) or {}
        job_status = (build.get("job", {}) or {}).get("status")
        ws_status = build.get("status")
        if job_status in _ERROR or ws_status in _ERROR:
            return PHASE_ERROR
        if ws_status in _RUNNING:
            return PHASE_RUNNING
        if ws_status in _STOPPED:
            return PHASE_STOPPED
        return PHASE_PROVISIONING

    @staticmethod
    def _agent_connected(workspace: dict) -> bool:
        for resource in (
            workspace.get("latest_build", {}).get("resources", []) or []
        ):
            for agent in resource.get("agents", []) or []:
                if agent.get("status") == "connected":
                    return True
        return False


def _default_session() -> Any:
    import requests

    return requests.Session()


def _safe_text(response: Any) -> str:
    text = getattr(response, "text", "") or ""
    return text.strip()


def _sanitize_coder_username(raw: str) -> str:
    """Map an arbitrary display name / email local-part to a valid Coder
    username (``^[a-z0-9]+(-[a-z0-9]+)*$``, max 32 chars)."""
    slug = re.sub(r"[^a-z0-9]+", "-", raw.strip().lower()).strip("-")
    return slug[:32].strip("-")
