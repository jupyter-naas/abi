from __future__ import annotations

import tempfile

import pytest
from naas_abi_core.services.gatekeeper.GatekeeperFactory import GatekeeperFactory
from naas_abi_core.services.gatekeeper.GatekeeperPort import (
    GatekeeperResource,
    GatekeeperSubject,
    parse_missing_grant_reason,
)


@pytest.fixture
def gatekeeper():
    with tempfile.TemporaryDirectory() as tmp:
        service = GatekeeperFactory.GatekeeperServiceSqlite(data_dir=tmp)
        yield service
        service.shutdown()


def test_sensitive_github_tool_denied_without_grant(gatekeeper) -> None:
    subject = GatekeeperSubject(
        user_id="user-1",
        workspace_id="ws-1",
        chat_id="chat-1",
    )
    decision = gatekeeper.evaluate_tool_call(
        subject,
        "github_list_repository_secrets",
        {"repo_name": "org/private-repo"},
    )
    assert decision.allowed is False
    assert "missing_grant" in decision.reason


def test_sensitive_github_tool_allowed_with_grant(gatekeeper) -> None:
    chat_id = "chat-2"
    gatekeeper.grant_resource(
        chat_id,
        GatekeeperResource(type="github.repo", id="org/private-repo"),
        frozenset({"read_secrets"}),
    )
    subject = GatekeeperSubject(
        user_id="user-1",
        workspace_id="ws-1",
        chat_id=chat_id,
    )
    decision = gatekeeper.evaluate_tool_call(
        subject,
        "github_list_repository_secrets",
        {"repo_name": "org/private-repo"},
    )
    assert decision.allowed is True


def test_non_sensitive_github_tool_allowed_without_grant(gatekeeper) -> None:
    subject = GatekeeperSubject(
        user_id="user-1",
        workspace_id="ws-1",
        chat_id="chat-3",
    )
    decision = gatekeeper.evaluate_tool_call(
        subject,
        "github_get_issue",
        {"repo_name": "org/repo", "issue_number": 1},
    )
    assert decision.allowed is True


def test_observation_recorded_after_tool_use(gatekeeper) -> None:
    subject = GatekeeperSubject(
        user_id="user-1",
        workspace_id="ws-1",
        chat_id="chat-4",
    )
    gatekeeper.grant_resource(
        "chat-4",
        GatekeeperResource(type="github.repo", id="org/repo"),
        frozenset({"read_secrets"}),
    )
    gatekeeper.record_tool_observation(
        subject,
        "github_get_repository_secret",
        {"repo_name": "org/repo", "secret_name": "API_KEY"},
    )
    observations = gatekeeper.list_observations("chat-4")
    assert len(observations) == 1
    assert observations[0].sensitivity == "sensitive"
    assert observations[0].tool_name == "github_get_repository_secret"


def test_export_denied_for_viewer_without_grants(gatekeeper) -> None:
    chat_id = "chat-5"
    observer = GatekeeperSubject(user_id="owner", workspace_id="ws-1", chat_id=chat_id)
    gatekeeper.grant_resource(
        chat_id,
        GatekeeperResource(type="github.repo", id="org/secret-repo"),
        frozenset({"read_secrets"}),
    )
    gatekeeper.record_tool_observation(
        observer,
        "github_list_repository_secrets",
        {"repo_name": "org/secret-repo"},
    )

    viewer = GatekeeperSubject(
        user_id="other-user", workspace_id="ws-1", chat_id=chat_id
    )
    decision = gatekeeper.evaluate_conversation_export(viewer, chat_id)
    assert decision.allowed is False
    assert "viewer_lacks_access" in decision.reason


def test_list_grants_after_grant(gatekeeper) -> None:
    chat_id = "chat-grants"
    gatekeeper.grant_resource(
        chat_id,
        GatekeeperResource(type="github.repo", id="org/repo"),
        frozenset({"read_secrets"}),
    )
    grants = gatekeeper.list_grants(chat_id)
    assert len(grants) == 1
    assert grants[0].resource_id == "org/repo"


def test_parse_missing_grant_reason() -> None:
    parsed = parse_missing_grant_reason("missing_grant:github.repo:org/x:read_secrets")
    assert parsed == ("github.repo", "org/x", "read_secrets")
    assert parse_missing_grant_reason("other") is None


def test_export_allowed_for_observer_with_auto_export_grant(gatekeeper) -> None:
    chat_id = "chat-6"
    observer = GatekeeperSubject(user_id="owner", workspace_id="ws-1", chat_id=chat_id)
    gatekeeper.grant_resource(
        chat_id,
        GatekeeperResource(type="github.repo", id="org/secret-repo"),
        frozenset({"read_secrets"}),
    )
    gatekeeper.record_tool_observation(
        observer,
        "github_list_repository_secrets",
        {"repo_name": "org/secret-repo"},
    )

    decision = gatekeeper.evaluate_conversation_export(observer, chat_id)
    assert decision.allowed is True
