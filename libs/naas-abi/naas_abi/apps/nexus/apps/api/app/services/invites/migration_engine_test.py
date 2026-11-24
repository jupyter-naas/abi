"""The move of pending invitations on the engine's real IAM and Nexus's tables
(SQLite), with the identity provider in memory: after it, each invitation is an
invited user holding the roles its pending grants held, the grants are gone, the
move is recorded, and running it again changes nothing."""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.models import (
    InvitationModel,
    OrganizationModel,
    ProvisionedIdentityModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container, workspace_container
from naas_abi.apps.nexus.apps.api.app.services.invites import runtime
from naas_abi.apps.nexus.apps.api.app.services.invites.migration import MIGRATION_NAME
from naas_abi.apps.nexus.apps.api.app.services.people.service import UNBOUND_PREFIX
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.identity.IdentityPorts import ProviderUnavailableError
from sqlalchemy import select, text

NOW = datetime(2026, 11, 19, 12, 0)
WS1 = workspace_container("org-1", "ws-1")
ORG1 = org_container("org-1")


class Identity:
    """The engine's identity service: a built-in provider and a Zitadel."""

    def __init__(self) -> None:
        self.accounts = {
            ("builtin", "bob@example.com"): "sub-bob",
            ("corp", "eve@corp.test"): "sub-eve",
        }
        self.down = False

    def list_providers(self):
        return [
            SimpleNamespace(name="builtin", issuer="https://idp.test", provisioning="builtin"),
            SimpleNamespace(name="corp", issuer="https://corp.test", provisioning="zitadel"),
        ]

    def find_provisioned_user(self, provider, email):
        if self.down:
            raise ProviderUnavailableError("the built-in provider is not up yet")
        subject = self.accounts.get((provider, email))
        return SimpleNamespace(subject=subject, created=False) if subject else None


@pytest_asyncio.fixture
async def world(team, nexus_db):
    async with nexus_db() as db:
        db.add(UserModel(id="owner", email="owner@example.com", name="Owner"))
        db.add(OrganizationModel(id="org-1", name="Acme", slug="acme", owner_id="owner"))
        await db.flush()
        db.add(
            WorkspaceModel(
                id="ws-1",
                name="Research",
                slug="research",
                owner_id="owner",
                organization_id="org-1",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        await db.commit()
    return SimpleNamespace(
        iam=team.iam, db=nexus_db, engine=nexus_db.kw["bind"], identity=Identity()
    )


async def _invite(world, invitation_id, email, provider, grants, *, status="pending", **fields):
    """An invitation as the old invite made it: its pending grants in IAM, its row."""
    with as_service_account("api"):
        ids = [
            world.iam.create_pending_grant(provider, email, policy, scope).id
            for policy, scope in grants
        ]
    async with world.db() as db:
        db.add(
            InvitationModel(
                id=invitation_id,
                email=email,
                provider=provider,
                organization_id="org-1",
                grant_ids=json.dumps(ids),
                status=status,
                created_at=NOW,
                updated_at=NOW,
                **fields,
            )
        )
        await db.commit()
    return ids


async def _migrate(world, **kwargs):
    return await runtime.migrate_pending_invitations(
        world.db, world.engine, identity=lambda: world.identity, iam=lambda: world.iam, **kwargs
    )


def _pending(world, email):
    with as_service_account("api"):
        return world.iam.list_pending_grants(email=email)


@pytest.mark.asyncio
async def test_pending_invitations_become_invited_users_with_the_same_access(world):
    await _invite(
        world,
        "inv-bob",
        "bob@example.com",
        "builtin",
        [("builtin.member", WS1)],
        workspace_id="ws-1",
        workspace_role="member",
        profile=json.dumps({"job_title": "Analyst"}),
    )
    await _invite(
        world, "inv-ada", "ada@example.com", "builtin", [("builtin.admin", ORG1)], org_role="admin"
    )
    await _invite(
        world,
        "inv-eve",
        "eve@corp.test",
        "corp",
        [("builtin.viewer", WS1)],
        workspace_id="ws-1",
        workspace_role="viewer",
    )
    await _invite(world, "inv-old", "old@example.com", "builtin", [], status="revoked")

    report = await _migrate(world)

    assert report is not None and report.finished
    assert (report.migrated, report.bound, report.unbound) == (3, 1, 2)
    async with world.db() as db:
        users = {u.email: u for u in (await db.execute(select(UserModel))).scalars()}
        invitations = {i.id: i for i in (await db.execute(select(InvitationModel))).scalars()}
    # Bob's account at the built-in provider is found: his row is its IAM user.
    bob = users["bob@example.com"]
    assert bob.status == "invited" and bob.id == bob.principal_id
    assert (bob.idp_issuer, bob.idp_subject) == ("https://idp.test", "sub-bob")
    assert await MEMBERSHIPS.roles_of(bob.id) == {WS1: "member"}
    # Ada has no account yet; Eve's Zitadel account was not made by Nexus: both wait
    # for their first verified sign-in, their roles already theirs.
    ada, eve = users["ada@example.com"], users["eve@corp.test"]
    for person, provider in ((ada, "builtin"), (eve, "corp")):
        assert person.id.startswith(UNBOUND_PREFIX) and person.principal_id is None
        assert (person.status, person.idp_provider) == ("invited", provider)
    assert (await MEMBERSHIPS.roles_of(ada.id))[ORG1] == "admin"
    assert await MEMBERSHIPS.roles_of(eve.id) == {WS1: "viewer"}
    # The org directory lists them (S2 derives it from IAM).
    directory = {e.user_id for e in await MEMBERSHIPS.org_directory("org-1")}
    assert {bob.id, ada.id, eve.id} <= directory
    # The grants are gone, the invitations moved, the revoked one untouched.
    for email in ("bob@example.com", "ada@example.com", "eve@corp.test"):
        assert _pending(world, email) == []
    assert {k: i.status for k, i in invitations.items()} == {
        "inv-bob": "migrated",
        "inv-ada": "migrated",
        "inv-eve": "migrated",
        "inv-old": "revoked",
    }
    assert invitations["inv-bob"].accepted_user_id == bob.id
    async with world.db() as db:
        recorded = (
            await db.execute(
                text("SELECT name FROM iam_migrations WHERE name = :n"), {"n": MIGRATION_NAME}
            )
        ).all()
        profile = (
            await db.execute(
                text(
                    "SELECT job_title FROM organization_members "
                    "WHERE organization_id = 'org-1' AND user_id = :u"
                ),
                {"u": bob.id},
            )
        ).scalar_one()
    assert recorded and profile == "Analyst"

    # Recorded: a start skips it; forced (the CLI), it finds nothing to do.
    assert await _migrate(world) is None
    again = await _migrate(world, force=True)
    assert again is not None and (again.migrated, again.bound, again.unbound, again.linked) == (
        0,
        0,
        0,
        0,
    )
    async with world.db() as db:
        assert len((await db.execute(select(UserModel))).all()) == len(users)


@pytest.mark.asyncio
async def test_an_account_nexus_made_at_zitadel_is_bound(world):
    async with world.db() as db:
        db.add(
            ProvisionedIdentityModel(
                provider="corp", subject="sub-eve", email="eve@corp.test", created_at=NOW
            )
        )
        await db.commit()
    await _invite(world, "inv-eve", "eve@corp.test", "corp", [("builtin.member", WS1)])

    report = await _migrate(world)

    assert report is not None and report.bound == 1
    async with world.db() as db:
        eve = (await db.execute(select(UserModel))).scalars().all()[-1]
    assert eve.principal_id == eve.id and eve.idp_subject == "sub-eve"


@pytest.mark.asyncio
async def test_a_provider_that_is_not_up_is_not_recorded_and_moves_later(world):
    world.identity.down = True
    await _invite(world, "inv-bob", "bob@example.com", "builtin", [("builtin.member", WS1)])

    report = await _migrate(world)

    assert report is not None and report.deferred == 1 and not report.finished
    assert len(_pending(world, "bob@example.com")) == 1

    world.identity.down = False
    report = await _migrate(world)
    assert report is not None and report.migrated == 1 and report.finished
    assert _pending(world, "bob@example.com") == []


@pytest.mark.asyncio
async def test_the_start_retries_a_provider_that_comes_up(world, monkeypatch):
    monkeypatch.setattr(runtime, "MIGRATION_RETRY_SECONDS", 0.0)
    world.identity.down = True
    await _invite(world, "inv-bob", "bob@example.com", "builtin", [("builtin.member", WS1)])
    calls = 0
    find = world.identity.find_provisioned_user

    def comes_up(provider, email):
        nonlocal calls
        calls += 1
        if calls == 3:
            world.identity.down = False
        return find(provider, email)

    world.identity.find_provisioned_user = comes_up

    report = await runtime.migrate_when_ready(
        world.db, world.engine, identity=lambda: world.identity, iam=lambda: world.iam
    )

    assert report is not None and report.migrated == 1 and calls == 3
