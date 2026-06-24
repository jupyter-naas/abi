from __future__ import annotations

from typing import Any

import pytest

from naas_abi_core.services.coding_environment.adapters.secondary.CoderAdapter import (
    CoderAdapter,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    AccessDeniedError,
    PHASE_RUNNING,
    WorkspaceNameConflictError,
    WorkspaceNotFoundError,
)
from naas_abi_core.services.coding_environment.tests.coding_environment__secondary_adapter__generic_test import (
    GenericCodingEnvironmentSecondaryAdapterTest,
)


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: Any = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.content = b"{}" if payload is not None else b""

    def json(self) -> Any:
        return self._payload


class FakeSession:
    """Routes (method, url-substring) -> FakeResponse; records all calls."""

    def __init__(self, routes: list[tuple[str, str, FakeResponse]]):
        self.routes = list(routes)
        self.calls: list[dict] = []

    def request(self, method, url, headers=None, json=None, timeout=None):
        self.calls.append(
            {"method": method, "url": url, "headers": headers, "json": json}
        )
        for m, substring, response in self.routes:
            if m == method and substring in url:
                return response
        return FakeResponse(404, {"message": "not found"}, "not found")

    def find(self, method: str, substring: str) -> dict | None:
        for call in self.calls:
            if call["method"] == method and substring in call["url"]:
                return call
        return None


def _adapter(session: FakeSession) -> CoderAdapter:
    return CoderAdapter(
        access_url="https://coder.example.com",
        wildcard_access_url="*.coder.example.com",
        admin_token="admin-token",
        session=session,
    )


_RUNNING_WORKSPACE = {
    "id": "ws-1",
    "name": "dev",
    "owner_name": "alice",
    "latest_build": {
        "status": "running",
        "job": {"status": "succeeded"},
        "resources": [{"agents": [{"name": "main", "status": "connected"}]}],
    },
}


class TestCoderAdapter(GenericCodingEnvironmentSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return CoderAdapter


def test_provision_posts_expected_body_and_normalizes_status() -> None:
    session = FakeSession(
        [
            ("GET", "/organizations/default", FakeResponse(200, {"id": "org-1"})),
            (
                "POST",
                "/members/user-1/workspaces",
                FakeResponse(201, _RUNNING_WORKSPACE),
            ),
        ]
    )
    adapter = _adapter(session)

    status = adapter.provision(
        user_id="user-1", template_id="tmpl-1", name="dev", params={"size": "L"}
    )

    assert status.id == "ws-1"
    assert status.phase == PHASE_RUNNING
    assert status.agent_ready is True

    call = session.find("POST", "/workspaces")
    assert call is not None
    body = call["json"]
    assert body["template_id"] == "tmpl-1"
    assert body["name"] == "dev"
    assert body["automatic_updates"] == "never"
    assert body["ttl_ms"] == 3_600_000
    assert body["rich_parameter_values"] == [{"name": "size", "value": "L"}]
    # admin token must be used on the control-plane call
    assert call["headers"]["Coder-Session-Token"] == "admin-token"


def test_name_conflict_maps_to_typed_error() -> None:
    session = FakeSession(
        [
            ("GET", "/organizations/default", FakeResponse(200, {"id": "org-1"})),
            (
                "POST",
                "/members/user-1/workspaces",
                FakeResponse(409, {"message": "exists"}, "exists"),
            ),
        ]
    )
    adapter = _adapter(session)
    with pytest.raises(WorkspaceNameConflictError):
        adapter.provision(user_id="user-1", template_id="t", name="dev")


def test_access_denied_maps_to_typed_error() -> None:
    session = FakeSession(
        [("GET", "/organizations/default", FakeResponse(403, {}, "forbidden"))]
    )
    adapter = _adapter(session)
    with pytest.raises(AccessDeniedError):
        adapter.list_templates()


def test_ensure_user_creates_when_missing() -> None:
    session = FakeSession(
        [
            ("GET", "/users/alice", FakeResponse(404, {"message": "nf"}, "nf")),
            ("GET", "/organizations/default", FakeResponse(200, {"id": "org-1"})),
            ("POST", "/users", FakeResponse(201, {"id": "user-9"})),
        ]
    )
    adapter = _adapter(session)

    user_id = adapter.ensure_user(
        external_id="ext", email="alice@example.com", username="alice"
    )
    assert user_id == "user-9"

    call = session.find("POST", "/users")
    assert call is not None
    assert call["json"]["login_type"] == "none"
    assert call["json"]["organization_ids"] == ["org-1"]


def test_ensure_user_sanitizes_username() -> None:
    session = FakeSession(
        [
            ("GET", "/users/local-admin", FakeResponse(404, {}, "nf")),
            ("GET", "/organizations/default", FakeResponse(200, {"id": "org-1"})),
            ("POST", "/users", FakeResponse(201, {"id": "user-7"})),
        ]
    )
    adapter = _adapter(session)
    uid = adapter.ensure_user(
        external_id="ext", email="admin@example.com", username="Local Admin"
    )
    assert uid == "user-7"
    call = session.find("POST", "/users")
    assert call is not None
    assert call["json"]["username"] == "local-admin"


def test_get_status_maps_404_and_invalid_uuid_to_not_found() -> None:
    s404 = FakeSession([("GET", "/workspaces/abc", FakeResponse(404, {}, "nope"))])
    with pytest.raises(WorkspaceNotFoundError):
        _adapter(s404).get_status(workspace_id="abc")

    s400 = FakeSession(
        [("GET", "/workspaces/code-server", FakeResponse(400, {}, 'Invalid UUID "code-server"'))]
    )
    with pytest.raises(WorkspaceNotFoundError):
        _adapter(s400).get_status(workspace_id="code-server")


def test_ensure_user_returns_existing() -> None:
    session = FakeSession(
        [("GET", "/users/alice", FakeResponse(200, {"id": "user-1"}))]
    )
    adapter = _adapter(session)
    assert (
        adapter.ensure_user(external_id="x", email="a@b.c", username="alice")
        == "user-1"
    )


def test_ensure_user_activates_dormant_on_create() -> None:
    session = FakeSession(
        [
            ("GET", "/users/alice", FakeResponse(404, {}, "nf")),
            ("GET", "/organizations/default", FakeResponse(200, {"id": "org-1"})),
            ("POST", "/users", FakeResponse(201, {"id": "user-9", "status": "dormant"})),
            (
                "PUT",
                "/users/user-9/status/activate",
                FakeResponse(200, {"id": "user-9", "status": "active"}),
            ),
        ]
    )
    adapter = _adapter(session)
    uid = adapter.ensure_user(external_id="x", email="a@b.c", username="alice")
    assert uid == "user-9"
    assert session.find("PUT", "/users/user-9/status/activate") is not None


def test_ensure_user_activates_existing_dormant() -> None:
    session = FakeSession(
        [
            ("GET", "/users/alice", FakeResponse(200, {"id": "user-1", "status": "dormant"})),
            ("PUT", "/users/user-1/status/activate", FakeResponse(200, {})),
        ]
    )
    adapter = _adapter(session)
    assert adapter.ensure_user(external_id="x", email="a@b.c", username="alice") == "user-1"
    assert session.find("PUT", "/status/activate") is not None


def test_ensure_user_skips_activate_when_active() -> None:
    session = FakeSession(
        [("GET", "/users/alice", FakeResponse(200, {"id": "user-1", "status": "active"}))]
    )
    adapter = _adapter(session)
    assert adapter.ensure_user(external_id="x", email="a@b.c", username="alice") == "user-1"
    assert session.find("PUT", "/status/activate") is None


def test_get_access_builds_redemption_url() -> None:
    session = FakeSession(
        [
            (
                "POST",
                "/users/user-1/keys/tokens",
                FakeResponse(201, {"key": "tok-abc"}),
            ),
            ("GET", "/workspaces/ws-1", FakeResponse(200, _RUNNING_WORKSPACE)),
            (
                "GET",
                "/applications/host",
                FakeResponse(200, {"host": "*.coder.example.com"}),
            ),
        ]
    )
    adapter = _adapter(session)

    access = adapter.get_access(
        workspace_id="ws-1", user_id="user-1", app_slug="code-server"
    )

    assert access.token == "tok-abc"
    assert access.url == (
        "https://code-server--main--dev--alice.coder.example.com/"
        "?coder_session_token=tok-abc"
    )
    # token minting requests the application_connect scope, lifetime in ns
    mint = session.find("POST", "/keys/tokens")
    assert mint is not None
    assert mint["json"]["scope"] == "application_connect"
    assert mint["json"]["lifetime"] == 3600 * 1_000_000_000


def test_get_access_strips_internal_app_host_port() -> None:
    # Coder echoes the wildcard with the internal access-URL port appended; the
    # browser-facing app URL must drop it and ride the TLS edge on 443.
    session = FakeSession(
        [
            ("POST", "/users/user-1/keys/tokens", FakeResponse(201, {"key": "tok"})),
            ("GET", "/workspaces/ws-1", FakeResponse(200, _RUNNING_WORKSPACE)),
            (
                "GET",
                "/applications/host",
                FakeResponse(200, {"host": "*.coder.nexus.localhost:7080"}),
            ),
        ]
    )
    access = _adapter(session).get_access(
        workspace_id="ws-1", user_id="user-1", app_slug="code-server"
    )
    assert ":7080" not in access.url
    assert access.url.startswith(
        "https://code-server--main--dev--alice.coder.nexus.localhost/"
    )


def test_build_app_url_lowercases_and_uses_delimiters() -> None:
    url = CoderAdapter.build_app_url(
        slug="code-server",
        agent="main",
        workspace="Dev",
        owner="Alice",
        wildcard_host="*.coder.example.com",
    )
    assert url == "https://code-server--main--dev--alice.coder.example.com/"
