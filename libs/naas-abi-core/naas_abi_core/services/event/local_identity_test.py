from __future__ import annotations

import hashlib
import subprocess

from naas_abi_core.services.event import local_identity
from naas_abi_core.services.event.context import (
    event_actor_user_id,
    event_triggered_via,
)
from naas_abi_core.services.event.local_identity import (
    bind_local_identity,
    email_actor_id,
)


def test_email_actor_id_is_a_normalized_hash_never_the_email() -> None:
    actor = email_actor_id("  Florent@Naas.ai ")

    assert actor == "email-sha256:" + hashlib.sha256(b"florent@naas.ai").hexdigest()
    assert "naas.ai" not in actor


def test_binding_uses_the_git_author_and_marks_the_cli(monkeypatch) -> None:
    monkeypatch.setattr(local_identity, "git_user_email", lambda: "dev@example.com")

    with bind_local_identity():
        assert event_actor_user_id.get() == email_actor_id("dev@example.com")
        assert event_triggered_via.get() == "cli"

    assert event_actor_user_id.get() is None
    assert event_triggered_via.get() is None


def test_binding_never_overrides_an_identity_already_set(monkeypatch) -> None:
    monkeypatch.setattr(local_identity, "git_user_email", lambda: "dev@example.com")
    token = event_actor_user_id.set("usr-1")
    try:
        with bind_local_identity():
            assert event_actor_user_id.get() == "usr-1"
    finally:
        event_actor_user_id.reset(token)


def test_without_a_git_author_there_is_no_actor(monkeypatch) -> None:
    monkeypatch.setattr(local_identity, "git_user_email", lambda: None)

    with bind_local_identity():
        assert event_actor_user_id.get() is None
        assert event_triggered_via.get() == "cli"


def test_git_user_email_tolerates_missing_git(monkeypatch) -> None:
    def no_git(*_args, **_kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", no_git)

    assert local_identity.git_user_email() is None
