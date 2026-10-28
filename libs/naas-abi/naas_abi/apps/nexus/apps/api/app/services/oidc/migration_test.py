"""The users of the old built-in login are made to exist at the provider."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from naas_abi.apps.nexus.apps.api.app.services.oidc.migration import migrate_users
from naas_abi.apps.nexus.apps.api.app.services.oidc.port import OidcUser


def legacy(user_id: str, email: str, name: str = "N") -> OidcUser:
    return OidcUser(
        id=user_id, email=email, name=name, principal_id=None, idp_issuer=None, idp_subject=None
    )


@dataclass
class Provisioned:
    created: bool
    disabled: bool = False


class Provider:
    def __init__(self, existing=()):
        self.people = dict.fromkeys(existing, False)
        self.calls: list[tuple[str, str]] = []

    def provision(self, email, name):
        self.calls.append((email, name))
        if email.startswith("bad"):
            raise ValueError("the provider refuses this address")
        created = email not in self.people
        self.people[email] = True
        return Provisioned(created)

    def find(self, email):
        return Provisioned(False) if email in self.people else None


USERS = [
    legacy("u1", "Ada@Example.com", "Ada"),
    legacy("u2", "bob@example.com", "Bob"),
    legacy("u3", "bad@example.com"),
    legacy("u4", "u4@unverified.internal"),
    legacy("u5", "carl@corp.test"),
]


def test_a_dry_run_provisions_nobody():
    provider = Provider(existing=["bob@example.com"])
    rows = migrate_users(USERS, provision=provider.provision, find=provider.find, apply=False)
    assert provider.calls == []
    assert [(r.user_id, r.outcome) for r in rows] == [
        ("u1", "would_create"),
        ("u2", "exists"),
        ("u3", "would_create"),
        ("u4", "skipped"),
        ("u5", "skipped"),
    ]


def test_apply_creates_what_is_missing_and_reports_the_rest():
    provider = Provider(existing=["bob@example.com"])
    rows = migrate_users(USERS, provision=provider.provision, find=provider.find, apply=True)
    outcomes = {r.user_id: r for r in rows}
    assert outcomes["u1"].outcome == "created" and outcomes["u1"].email == "ada@example.com"
    assert outcomes["u2"].outcome == "exists"
    assert outcomes["u3"].outcome == "failed" and "refuses" in (outcomes["u3"].detail or "")
    assert outcomes["u4"].outcome == outcomes["u5"].outcome == "skipped"
    # Names travel; a failure of one never stops the others.
    assert ("ada@example.com", "Ada") in provider.calls and (
        "bob@example.com",
        "Bob",
    ) in provider.calls


def test_running_again_creates_nobody_twice():
    provider = Provider()
    migrate_users(USERS[:2], provision=provider.provision, find=provider.find, apply=True)
    again = migrate_users(USERS[:2], provision=provider.provision, find=provider.find, apply=True)
    assert [r.outcome for r in again] == ["exists", "exists"]


def test_a_provider_that_cannot_provision_stops_the_run():
    def never(email, name):
        raise NotImplementedError("managed in the identity provider")

    with pytest.raises(NotImplementedError):
        migrate_users(USERS, provision=never, find=lambda e: None, apply=True)
