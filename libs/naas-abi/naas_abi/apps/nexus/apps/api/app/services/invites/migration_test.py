"""The move of pending invitations into invited people, with fakes: who each
invitation becomes (bound, unbound, linked), that its grants are attached and
withdrawn, that a provider that does not answer keeps them pending, and that a
second run changes nothing."""

from __future__ import annotations

from datetime import datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services.invites.migration import (
    InvitationMigration,
    MigrationGateway,
    MigrationProvider,
    ProviderUnavailable,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.port import Invitation
from naas_abi.apps.nexus.apps.api.app.services.invites.service_test import Store
from naas_abi.apps.nexus.apps.api.app.services.people.port import PlatformUser, UserStatus
from naas_abi.apps.nexus.apps.api.app.services.people.service import UNBOUND_PREFIX
from naas_abi.apps.nexus.apps.api.app.services.people.service_test import Store as PeopleStore

NOW = datetime(2026, 11, 19, 12, 0, 0)
WS = "abi:nexus:organization/org-1/nexus:workspace/ws-1"
ORG = "abi:nexus:organization/org-1"
BUILTIN = MigrationProvider("builtin", "https://idp.test", "builtin")
CORP = MigrationProvider("corp", "https://corp.test", "zitadel")
LDAP = MigrationProvider("ldap", "https://ldap.test", "none")


class Rows(PeopleStore):
    """The people's rows, and the identity each new one was bound to."""

    def __init__(self) -> None:
        super().__init__()
        self.bindings: dict[str, tuple[str | None, str | None]] = {}

    async def add(self, user, *, now):
        row = await super().add(user, now=now)
        if user.principal_id:
            self.bindings[user.id] = (user.issuer, user.subject)
        return row

    async def add_existing_row(self, user_id: str, email: str) -> PlatformUser:
        self.rows[user_id] = PlatformUser(user_id, email, "Alice", UserStatus.ACTIVE, "builtin")
        return self.rows[user_id]


class Engine(MigrationGateway):
    def __init__(self) -> None:
        self.known = {p.name: p for p in (BUILTIN, CORP, LDAP)}
        # (provider, email) -> subject of an account at the provider.
        self.accounts: dict[tuple[str, str], str] = {}
        self.down: set[str] = set()
        self.retired: set[str] = set()
        self.grants: dict[str, tuple[str, str | None]] = {}
        # (user id, policy, scope) attached.
        self.given: list[tuple[str, str, str | None]] = []
        self.withdrawn: list[str] = []

    async def providers(self):
        return dict(self.known)

    async def find(self, provider, email):
        if provider.name in self.down:
            raise ProviderUnavailable(f"{provider.name} is down")
        if provider.provisioning == "none":
            return None
        return self.accounts.get((provider.name, email))

    async def ensure_principal(self, provider, subject, *, email):
        principal = f"usr_{subject}"
        return None if principal in self.retired else principal

    async def pending(self, grant_ids):
        return {g: self.grants[g] for g in grant_ids if g in self.grants}

    async def give(self, user_id, policy_id, scope):
        if (user_id, policy_id, scope) not in self.given:
            self.given.append((user_id, policy_id, scope))

    async def withdraw(self, grant_ids):
        for grant_id in grant_ids:
            self.grants.pop(grant_id, None)
            self.withdrawn.append(grant_id)


def _invitation(
    invitation_id: str,
    email: str,
    *,
    provider: str = "builtin",
    grants: dict[str, tuple[str, str | None]],
    engine: Engine,
    workspace: str | None = "ws-1",
    status: str = "pending",
    profile: dict[str, str] | None = None,
) -> Invitation:
    engine.grants.update(grants)
    return Invitation(
        id=invitation_id,
        email=email,
        provider=provider,
        organization_id="org-1",
        org_role=None,
        workspace_id=workspace,
        workspace_role="member",
        invited_by="admin",
        grant_ids=tuple(grants),
        status=status,  # type: ignore[arg-type]
        created_at=NOW,
        profile=profile or {},
    )


@pytest.fixture
def world():
    store, rows, engine = Store(), Rows(), Engine()

    def migration() -> InvitationMigration:
        return InvitationMigration(store, rows, engine, clock=lambda: NOW)

    def add(*invitations: Invitation) -> None:
        for invitation in invitations:
            store.rows[invitation.id] = invitation

    return store, rows, engine, migration, add


@pytest.mark.asyncio
async def test_a_builtin_invitation_becomes_a_bound_invited_user_with_its_grants(world):
    store, rows, engine, migration, add = world
    engine.accounts[("builtin", "bob@example.com")] = "sub-bob"
    add(
        _invitation(
            "inv-1",
            "bob@example.com",
            grants={"pgr-1": ("builtin.member", WS), "pgr-2": ("pol_features", WS)},
            engine=engine,
            profile={"job_title": "Analyst", "ignored": "x"},
        )
    )

    report = await migration().run()

    user = rows.rows["usr_sub-bob"]
    assert (user.email, user.status, user.provider) == (
        "bob@example.com",
        UserStatus.INVITED,
        "builtin",
    )
    assert rows.bindings["usr_sub-bob"] == ("https://idp.test", "sub-bob")
    # The policy before the role, as a claim attached them; both withdrawn.
    assert engine.given == [
        ("usr_sub-bob", "pol_features", WS),
        ("usr_sub-bob", "builtin.member", WS),
    ]
    assert engine.grants == {} and sorted(engine.withdrawn) == ["pgr-1", "pgr-2"]
    assert store.rows["inv-1"].status == "migrated"
    assert store.rows["inv-1"].accepted_user_id == "usr_sub-bob"
    assert rows.profiles == {("org-1", "usr_sub-bob"): {"job_title": "Analyst"}}
    assert (report.migrated, report.bound, report.finished) == (1, 1, True)


@pytest.mark.asyncio
async def test_running_it_twice_changes_nothing(world):
    store, rows, engine, migration, add = world
    engine.accounts[("builtin", "bob@example.com")] = "sub-bob"
    add(
        _invitation(
            "inv-1", "bob@example.com", grants={"pgr-1": ("builtin.member", WS)}, engine=engine
        )
    )
    await migration().run()
    before = (dict(rows.rows), list(engine.given), dict(store.rows))

    report = await migration().run()

    assert (dict(rows.rows), list(engine.given), dict(store.rows)) == before
    assert (report.migrated, report.bound, report.unbound, report.linked) == (0, 0, 0, 0)
    assert report.finished


@pytest.mark.asyncio
async def test_an_account_someone_made_at_the_provider_waits_for_a_verified_sign_in(world):
    """Zitadel's account was not made by Nexus: whoever made it may not own the
    address. The row stays unbound, as the pending grant waited, and names the
    provider whose verified sign-in binds it."""
    store, rows, engine, migration, add = world
    engine.accounts[("corp", "eve@corp.test")] = "sub-eve"
    add(
        _invitation(
            "inv-1",
            "eve@corp.test",
            provider="corp",
            grants={"pgr-1": ("builtin.admin", WS)},
            engine=engine,
        )
    )

    report = await migration().run()

    (user_id,) = rows.rows
    assert user_id.startswith(UNBOUND_PREFIX)
    assert rows.rows[user_id].provider == "corp" and user_id not in rows.bindings
    assert engine.given == [(user_id, "builtin.admin", WS)]
    assert report.unbound == 1


@pytest.mark.asyncio
async def test_an_account_nexus_made_at_the_provider_is_bound(world):
    store, rows, engine, migration, add = world
    engine.accounts[("corp", "eve@corp.test")] = "sub-eve"
    store.provisioned.add(("corp", "sub-eve"))
    add(
        _invitation(
            "inv-1",
            "eve@corp.test",
            provider="corp",
            grants={"pgr-1": ("builtin.member", WS)},
            engine=engine,
        )
    )

    report = await migration().run()

    assert "usr_sub-eve" in rows.rows and report.bound == 1


@pytest.mark.asyncio
async def test_a_provider_that_manages_its_people_gives_an_unbound_row(world):
    store, rows, engine, migration, add = world
    add(
        _invitation(
            "inv-1",
            "ann@ldap.test",
            provider="ldap",
            grants={"pgr-1": ("builtin.viewer", WS)},
            engine=engine,
        )
    )

    report = await migration().run()

    (user,) = rows.rows.values()
    assert user.id.startswith(UNBOUND_PREFIX) and user.provider == "ldap"
    assert user.status == UserStatus.INVITED
    assert store.rows["inv-1"].status == "migrated" and report.unbound == 1


@pytest.mark.asyncio
async def test_an_email_with_a_row_is_linked_never_duplicated(world):
    store, rows, engine, migration, add = world
    existing = await rows.add_existing_row("usr-alice", "alice@example.com")
    add(
        _invitation(
            "inv-1", "Alice@Example.com", grants={"pgr-1": ("builtin.member", WS)}, engine=engine
        )
    )

    report = await migration().run()

    assert list(rows.rows) == [existing.id]
    assert engine.given == [("usr-alice", "builtin.member", WS)]
    assert report.linked == 1 and store.rows["inv-1"].status == "migrated"


@pytest.mark.asyncio
async def test_invitations_of_one_person_move_together_with_their_shared_grant(world):
    store, rows, engine, migration, add = world
    engine.accounts[("builtin", "bob@example.com")] = "sub-bob"
    shared = {"pgr-org": ("builtin.member", ORG)}
    add(
        _invitation(
            "inv-1",
            "bob@example.com",
            grants={**shared, "pgr-1": ("builtin.member", WS)},
            engine=engine,
        ),
        _invitation(
            "inv-2",
            "bob@example.com",
            grants={**shared, "pgr-2": ("builtin.viewer", "ws-2-scope")},
            engine=engine,
            workspace="ws-2",
        ),
    )

    report = await migration().run()

    assert len(rows.rows) == 1 and report.migrated == 2
    assert sorted(engine.withdrawn) == ["pgr-1", "pgr-2", "pgr-org"]
    assert [g for g in engine.given if g[2] == ORG] == [("usr_sub-bob", "builtin.member", ORG)]


@pytest.mark.asyncio
async def test_a_provider_that_does_not_answer_keeps_its_invitations_pending(world):
    store, rows, engine, migration, add = world
    engine.down.add("builtin")
    add(
        _invitation(
            "inv-1", "bob@example.com", grants={"pgr-1": ("builtin.member", WS)}, engine=engine
        )
    )

    report = await migration().run()

    assert store.rows["inv-1"].status == "pending" and engine.grants and not rows.rows
    assert (report.deferred, report.finished) == (1, False)

    engine.down.clear()
    engine.accounts[("builtin", "bob@example.com")] = "sub-bob"
    report = await migration().run()
    assert store.rows["inv-1"].status == "migrated" and report.finished


@pytest.mark.asyncio
async def test_no_identity_service_defers_every_invitation(world):
    store, rows, engine, migration, add = world

    async def unloaded():
        raise ProviderUnavailable("The engine's identity service is not loaded")

    engine.providers = unloaded  # type: ignore[method-assign]
    add(
        _invitation(
            "inv-1", "bob@example.com", grants={"pgr-1": ("builtin.member", WS)}, engine=engine
        ),
        _invitation(
            "inv-2",
            "eve@corp.test",
            provider="corp",
            grants={"pgr-2": ("builtin.viewer", WS)},
            engine=engine,
        ),
    )

    report = await migration().run()

    assert (report.deferred, report.finished, report.migrated) == (2, False, 0)
    assert {i.status for i in store.rows.values()} == {"pending"} and not rows.rows
    assert engine.grants and not engine.withdrawn


@pytest.mark.asyncio
async def test_what_cannot_move_is_reported_and_left_alone(world):
    store, rows, engine, migration, add = world
    engine.accounts[("builtin", "gone@example.com")] = "sub-gone"
    engine.retired.add("usr_sub-gone")
    add(
        _invitation(
            "inv-1",
            "x@old.test",
            provider="removed",
            grants={"pgr-1": ("builtin.member", WS)},
            engine=engine,
        ),
        _invitation(
            "inv-2", "gone@example.com", grants={"pgr-2": ("builtin.member", WS)}, engine=engine
        ),
    )

    report = await migration().run()

    assert {i.status for i in store.rows.values()} == {"pending"}
    assert len(report.skipped) == 2 and not rows.rows and engine.grants
    # Nothing a later run would do differently: recorded as done.
    assert report.finished


@pytest.mark.asyncio
async def test_revoked_and_accepted_invitations_are_left_alone(world):
    store, rows, engine, migration, add = world
    add(
        _invitation("inv-1", "a@example.com", grants={}, engine=engine, status="revoked"),
        _invitation("inv-2", "b@example.com", grants={}, engine=engine, status="accepted"),
    )

    report = await migration().run()

    assert [i.status for i in store.rows.values()] == ["revoked", "accepted"]
    assert not rows.rows and report.migrated == 0


@pytest.mark.asyncio
async def test_one_failure_never_stops_the_others(world):
    store, rows, engine, migration, add = world
    engine.accounts[("builtin", "bob@example.com")] = "sub-bob"
    engine.accounts[("builtin", "cid@example.com")] = "sub-cid"
    add(
        _invitation(
            "inv-1", "bob@example.com", grants={"pgr-1": ("builtin.member", WS)}, engine=engine
        ),
        _invitation(
            "inv-2", "cid@example.com", grants={"pgr-2": ("builtin.member", WS)}, engine=engine
        ),
    )
    give = engine.give

    async def failing(user_id, policy_id, scope):
        if user_id == "usr_sub-bob":
            raise RuntimeError("IAM refused")
        await give(user_id, policy_id, scope)

    engine.give = failing  # type: ignore[method-assign]

    report = await migration().run()

    assert store.rows["inv-1"].status == "pending" and store.rows["inv-2"].status == "migrated"
    assert len(report.failed) == 1 and not report.finished
