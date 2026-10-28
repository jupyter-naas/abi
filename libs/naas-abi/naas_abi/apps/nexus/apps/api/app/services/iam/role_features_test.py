"""The move of the features roles brought into policies, on a database at the
previous state: IAM holding the ``builtin.features.*`` the previous version
generated and attached beside each role (and invitations pending), Nexus holding
the organizations' overlay table. Every user's ``UseFeature`` decisions are the
same at every step (boot, an interrupted move, the move, a workspace made after
it, a pending invitation claimed after it), whatever the configuration says by
then; and no role brings a feature."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import (
    KNOWN_FEATURE_KEYS,
    enabled_feature_catalog,
)
from naas_abi.apps.nexus.apps.api.app.models import (
    InvitationModel,
    OrganizationModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import role_features
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import Memberships
from naas_abi.apps.nexus.apps.api.app.services.iam.names import NO_ORG, nexus_resource
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.IAMPorts import Attachment, Policy
from naas_abi_core.services.iam.policy import PolicyDocument, Statement
from sqlalchemy import inspect, text

NOW = datetime(2026, 1, 1)
EVERY = [key for key in KNOWN_FEATURE_KEYS if key not in ("code", "tasks")]
# What the previous version was configured with: its stored policies come from it.
FLAGS = FeatureFlagsConfig(
    enabled_features=EVERY,
    role_baseline={
        "owner": EVERY,
        "admin": [k for k in EVERY if k != "settings"],
        "member": ["chat", "files", "maps", "tasks"],  # tasks is not enabled: dropped
        "viewer": ["chat"],
    },
    organization_overrides={"org-2": {"viewer": ["chat", "files"], "member": []}},
)
# The overlay of org-1 stored in ``organization_role_features``.
OVERLAY = {"member": ["chat", "graph"], "admin": ["chat"]}
WORKSPACES = {"ws-a": "org-1", "ws-b": "org-1", "ws-c": "org-2", "ws-d": None}
# Made after the move: an org-wide holder's features reach it, as before.
LATER = {"ws-later": "org-1", "ws-later-2": "org-2"}
USERS = (
    "alice",  # owner of org-1: org-wide
    "bob",  # member of ws-a
    "carol",  # viewer of ws-a, admin of ws-b
    "dave",  # member of ws-c
    "erin",  # owner of ws-d, a workspace with no organization
    "frank",  # viewer of ws-a, in the group "team", member of ws-b
    "gina",  # admin of org-2: org-wide
    "henry",  # a member of org-1 only: org-level roles brought no feature
    "ivan",  # nobody
    "root",  # the platform admin
)
BOB_TOO = "zoe@example.com"  # invited as a member of ws-a, pending
OWNER_TOO = "olga@example.com"  # invited as an owner of org-1, pending


def _old_plan(flags: FeatureFlagsConfig, overlays: dict) -> dict[str, list[str]]:
    """What the previous version's ``feature_plan`` gave IAM to store."""
    enabled = set(enabled_feature_catalog(flags))
    base = role_features.resolve_role_baseline(flags)
    plan = {
        role: sorted(k for k in base.get(role, []) if k in enabled)
        for role in role_features.ROLE_NAMES
    }
    for org in sorted(set(flags.organization_overrides) | set(overlays)):
        resolved = role_features.resolve_role_baseline(
            flags, organization_id=org, organization_override=overlays.get(org)
        )
        for role in role_features.ROLE_NAMES:
            found = sorted(k for k in resolved.get(role, []) if k in enabled)
            if found != plan[role]:
                plan[f"{org}.{role}"] = found
    return plan


def _old_policy(key: str, features: list[str]) -> Policy:
    statements = (
        (
            Statement(
                "Allow",
                ("nexus:UseFeature",),
                tuple(f"${{scope}}:nexus:feature/{name}" for name in features),
                sid="UseFeatures",
            ),
        )
        if features
        else ()
    )
    return Policy(
        id=f"builtin.features.{key}",
        name=f"Features of {key}",
        document=PolicyDocument(statements=statements),
        managed=True,
    )


def _store_previous_state(nexus: NexusIam, plan: dict[str, list[str]]) -> None:
    """The feature policies, and the one attached beside each role at a
    workspace or org-wide: the most specific key that exists, as the previous
    IAM kept them in step."""
    store = nexus.iam.store
    for key, features in plan.items():
        store.put_managed_policy(_old_policy(key, features))
    count = 0
    for role in roles.ROLES:
        for attachment in store.list_attachments(policy_id=role):
            if attachment.scope is None:
                continue
            _abi, org, workspace = attachment.scope.split(":", 2)
            if "-" in (org, workspace):
                continue
            key = role_features.key_for(role.removeprefix("builtin."), org, workspace, plan)
            count += 1
            store.attach(
                Attachment(
                    f"att_old{count}",
                    f"builtin.features.{key}",
                    attachment.principal_id,
                    attachment.scope,
                )
            )
    nexus.iam.invalidate()


def _world() -> NexusIam:
    nexus = NexusIam(FLAGS, features_with_roles=False)
    scopes = {ws: nexus.workspace(org, ws) for ws, org in WORKSPACES.items()}
    nexus.grant("alice", "owner", nexus.org("org-1"))
    nexus.grant("bob", "member", scopes["ws-a"])
    nexus.grant("carol", "viewer", scopes["ws-a"])
    nexus.grant("carol", "admin", scopes["ws-b"])
    nexus.grant("dave", "member", scopes["ws-c"])
    nexus.grant("erin", "owner", scopes["ws-d"])
    nexus.grant("frank", "viewer", scopes["ws-a"])
    nexus.grant("gina", "admin", nexus.org("org-2"))
    nexus.grant("henry", "member", nexus.org("org-1"))
    nexus.user("ivan")
    nexus.platform_admin("root")
    with as_service_account("engine"):
        team = nexus.iam.create_group("team", scope=scopes["ws-b"])
        nexus.iam.attach_policy(roles.MEMBER, team.id, scopes["ws-b"])
        nexus.iam.add_group_member(team.id, nexus.principal("frank"))
        nexus.iam.create_pending_grant("builtin", BOB_TOO, roles.MEMBER, scopes["ws-a"])
        nexus.iam.create_pending_grant("builtin", OWNER_TOO, roles.OWNER, "abi:org-1:-")
    return nexus


def _previous(nexus: NexusIam) -> NexusIam:
    _store_previous_state(nexus, _old_plan(FLAGS, {"org-1": OVERLAY}))
    return nexus


def _decisions(nexus: NexusIam, users=USERS) -> dict[tuple[str, str, str], bool]:
    """IAM's ``UseFeature`` for every user, workspace (those made later
    included) and known feature."""
    names = {
        (ws, key): nexus_resource("feature", org=org or NO_ORG, workspace=ws, id=key)
        for ws, org in {**WORKSPACES, **LATER}.items()
        for key in KNOWN_FEATURE_KEYS
    }
    found: dict[tuple[str, str, str], bool] = {}
    for user in users:
        with use_call_context(NexusIam.context(user)):
            allowed = set(nexus.iam.filter("nexus:UseFeature", list(names.values())).allowed)
        for (ws, key), name in names.items():
            found[(user, ws, key)] = name in allowed
    return found


async def _previous_database(db, nexus: NexusIam) -> None:
    await db.execute(
        text(
            "CREATE TABLE IF NOT EXISTS iam_migrations (name VARCHAR(128) PRIMARY KEY, "
            "applied_at TIMESTAMP, report TEXT)"
        )
    )
    # As migration 0040 made it.
    await db.execute(
        text(
            "CREATE TABLE organization_role_features (organization_id VARCHAR PRIMARY KEY, "
            "role_baseline TEXT NOT NULL, updated_by VARCHAR, created_at TIMESTAMP, "
            "updated_at TIMESTAMP)"
        )
    )
    await db.execute(
        text(
            "INSERT INTO organization_role_features (organization_id, role_baseline) "
            "VALUES ('org-1', :r)"
        ),
        {"r": json.dumps(OVERLAY)},
    )
    await db.execute(
        text("INSERT INTO iam_migrations (name, applied_at) VALUES (:n, :at)"),
        {"n": role_features.AFTER, "at": NOW},
    )
    for org in ("org-1", "org-2"):
        db.add(
            OrganizationModel(
                id=org, name=org, slug=org, owner_id="alice", created_at=NOW, updated_at=NOW
            )
        )
    for ws, org in WORKSPACES.items():
        db.add(
            WorkspaceModel(
                id=ws,
                name=ws,
                slug=ws,
                owner_id="alice",
                organization_id=org,
                created_at=NOW,
                updated_at=NOW,
            )
        )
    with as_service_account("engine"):
        pending = {g.email: g.id for g in nexus.iam.list_pending_grants()}
    for email, org, workspace, role in (
        (BOB_TOO, "org-1", "ws-a", "member"),
        (OWNER_TOO, "org-1", None, "owner"),
    ):
        db.add(
            InvitationModel(
                id=f"inv-{email}",
                email=email,
                provider="builtin",
                organization_id=org,
                org_role=role if workspace is None else None,
                workspace_id=workspace,
                workspace_role=role if workspace else None,
                grant_ids=json.dumps([pending[email]]),
                status="pending",
                created_at=NOW,
                updated_at=NOW,
            )
        )
    await db.commit()


async def _has_table(db, name: str) -> bool:
    connection = await db.connection()
    return await connection.run_sync(lambda sync: inspect(sync).has_table(name))


def _old_ids(nexus: NexusIam) -> list[str]:
    return [p.id for p in nexus.iam._all_policies() if p.id.startswith("builtin.features.")]


@pytest.mark.asyncio
async def test_every_user_keeps_exactly_their_features(nexus_db):
    nexus = _previous(_world())
    with nexus.installed():
        before = _decisions(nexus)
        # The previous state is not empty: the move has something to keep.
        assert before[("bob", "ws-a", "graph")] and not before[("bob", "ws-a", "files")]
        assert before[("alice", "ws-b", "settings")] and before[("frank", "ws-b", "graph")]
        assert before[("alice", "ws-later", "chat")] and before[("gina", "ws-later-2", "chat")]
        assert before[("dave", "ws-c", "chat")] is False
        # The engine starts on this version: nothing changes before the move.
        nexus.iam.bootstrap()
        nexus.iam.invalidate()
        assert _decisions(nexus) == before
        async with nexus_db() as db:
            await _previous_database(db, nexus)
            # Whatever the configuration says now (here: every default), the
            # move reads what was in force.
            made = await role_features.migrate_role_features(db, FeatureFlagsConfig())
            assert made
            assert not await _has_table(db, "organization_role_features")
            recorded = (
                await db.execute(
                    text("SELECT report FROM iam_migrations WHERE name = :n"),
                    {"n": role_features.MIGRATION_NAME},
                )
            ).scalar()
            assert json.loads(recorded)["pending_grants"] == 2
            assert _old_ids(nexus) == []
            assert _decisions(nexus) == before
            # Once: a second start changes nothing, and adds no policy.
            policies = {p.id for p in nexus.iam._all_policies()}
            assert await role_features.migrate_role_features(db, FLAGS) is None
            assert {p.id for p in nexus.iam._all_policies()} == policies
        # Workspaces made after the move: the org-wide holders' features reach
        # them as before, and nobody else's.
        for ws, org in LATER.items():
            nexus.workspace(org, ws)
        nexus.iam.invalidate()
        assert _decisions(nexus) == before
    owned = {(p.owner_scope, p.name) for p in nexus.iam._all_policies() if not p.managed}
    # Each workspace has one for every role that had features, held or not:
    # nobody is a member of ws-d, yet an invitation there can carry it.
    for role in ("owner", "admin", "member", "viewer"):
        assert (f"abi:{NO_ORG}:ws-d", f"Features of {role}") in owned
    # org-2's members had none: no policy to carry.
    assert ("abi:org-2:ws-c", "Features of member") not in owned
    # The org-wide holders' are their organization's.
    assert ("abi:org-1:-", "Features of owner") in owned
    assert ("abi:org-2:-", "Features of admin") in owned


@pytest.mark.asyncio
async def test_a_pending_invitation_keeps_its_roles_features(nexus_db):
    """Invited before the move, claimed after: the invitee has what the role
    brought then. The Nexus invitation lists the grant, so revoking it withdraws
    both."""
    nexus = _previous(_world())
    expected = _old_plan(FLAGS, {"org-1": OVERLAY})
    with nexus.installed():
        async with nexus_db() as db:
            await _previous_database(db, nexus)
            await role_features.migrate_role_features(db, FLAGS)
            rows = {
                row[0]: (json.loads(row[1]), json.loads(row[2] or "[]"))
                for row in (
                    await db.execute(text("SELECT id, grant_ids, policy_ids FROM invitations"))
                ).all()
            }
        with as_service_account("engine"):
            pending = {g.id: g for g in nexus.iam.list_pending_grants()}
            for invitation_id, (grant_ids, policy_ids) in rows.items():
                assert len(grant_ids) == 2 and len(policy_ids) == 1, invitation_id
                assert {pending[g].policy_id for g in grant_ids} - {policy_ids[0]} <= set(
                    roles.ROLES
                )
            zoe = nexus.iam.ensure_user(
                "https://idp.example", "zoe", provider="builtin", email=BOB_TOO, email_verified=True
            )
            olga = nexus.iam.ensure_user(
                "https://idp.example",
                "olga",
                provider="builtin",
                email=OWNER_TOO,
                email_verified=True,
            )
            nexus.iam.claim_pending_grants(zoe.id)
            nexus.iam.claim_pending_grants(olga.id)
        # As Nexus does after the sign-in that claims an org role.
        Memberships.mirror_org_wide(nexus.iam, olga.id, "abi:org-1:-", "owner")

        def features(principal_id: str, workspace: str) -> set[str]:
            names = {
                key: nexus_resource("feature", org="org-1", workspace=workspace, id=key)
                for key in KNOWN_FEATURE_KEYS
            }
            with use_call_context(NexusIam.context(principal_id)):
                allowed = set(nexus.iam.filter("nexus:UseFeature", list(names.values())).allowed)
            return {key for key, name in names.items() if name in allowed}

        assert features(zoe.id, "ws-a") == set(expected["org-1.member"])
        assert features(zoe.id, "ws-b") == set()
        for workspace in ("ws-a", "ws-later"):
            assert features(olga.id, workspace) == set(expected["owner"]), workspace


@pytest.mark.asyncio
async def test_an_interrupted_move_keeps_the_old_features_and_finishes_next_start(
    nexus_db, monkeypatch
):
    nexus = _previous(_world())
    with nexus.installed():
        before = _decisions(nexus)
        nexus.iam.bootstrap()
        async with nexus_db() as db:
            await _previous_database(db, nexus)
            real = role_features.move

            def failing(iam, workspaces, keys):
                real(iam, [w for w in workspaces if w[0] != "ws-b"], keys)
                raise RuntimeError("IAM went away")

            monkeypatch.setattr(role_features, "move", failing)
            assert await role_features.migrate_role_features(db, FLAGS) is None
            # Not recorded: the old policies and the overlay stay, nobody lost anything.
            assert await _has_table(db, "organization_role_features")
            assert _old_ids(nexus)
            nexus.iam.invalidate()
            assert _decisions(nexus) == before
            monkeypatch.setattr(role_features, "move", real)
            assert await role_features.migrate_role_features(db, FLAGS)
            assert not await _has_table(db, "organization_role_features")
            assert _old_ids(nexus) == []
        nexus.iam.invalidate()
        assert _decisions(nexus) == before


@pytest.mark.asyncio
async def test_a_role_left_before_the_move_takes_its_old_features_with_it(nexus_db):
    """Between the engine's start and the move, a role detached takes the old
    companion with it, as the older IAM's sync did: never wider."""
    nexus = _previous(_world())
    with nexus.installed():
        with as_service_account("api"):
            nexus.iam.detach_policy(roles.MEMBER, nexus.principal("bob"), "abi:org-1:ws-a")
        assert not _decisions(nexus, ["bob"])[("bob", "ws-a", "chat")]
        async with nexus_db() as db:
            await _previous_database(db, nexus)
            await role_features.migrate_role_features(db, FLAGS)
        assert not any(_decisions(nexus, ["bob"]).values())


@pytest.mark.asyncio
async def test_the_move_waits_for_the_workspace_overrides(nexus_db):
    nexus = _previous(_world())
    with nexus.installed():
        before = _decisions(nexus)
        async with nexus_db() as db:
            await db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS iam_migrations (name VARCHAR(128) "
                    "PRIMARY KEY, applied_at TIMESTAMP, report TEXT)"
                )
            )
            assert await role_features.migrate_role_features(db, FLAGS) is None
            found = (await db.execute(text("SELECT name FROM iam_migrations"))).all()
            assert found == []
        # Waiting loses nothing: the old policies are still in force.
        assert _decisions(nexus) == before


@pytest.mark.asyncio
async def test_a_new_member_uses_no_feature_until_a_policy_grants_one():
    nexus = NexusIam(FLAGS, features_with_roles=False)
    scope = nexus.workspace("org-1", "ws-1")
    nexus.grant("owner", "owner", scope)
    nexus.grant("bob", "member", scope)
    with nexus.installed():
        for user in ("owner", "bob"):
            assert not await AUTHZ.allowed("UseFeature", user=user, workspace="ws-1", id="chat")
        nexus.give_features(nexus.principal("bob"), ["chat"], scope)
        assert await AUTHZ.allowed("UseFeature", user="bob", workspace="ws-1", id="chat")
        assert not await AUTHZ.allowed("UseFeature", user="bob", workspace="ws-1", id="files")


@pytest.mark.asyncio
async def test_a_disabled_feature_is_usable_by_nobody_the_platform_admin_included():
    nexus = NexusIam(FLAGS, features_with_roles=False)
    scope = nexus.workspace("org-1", "ws-1")
    nexus.grant("bob", "member", scope)
    nexus.platform_admin("root")
    nexus.give_features(nexus.principal("bob"), ["chat", "tasks"], scope)
    with nexus.installed():
        assert await AUTHZ.allowed("UseFeature", user="root", workspace="ws-1", id="chat")
        for user in ("root", "bob"):
            decision = await AUTHZ.decide("UseFeature", user=user, workspace="ws-1", id="tasks")
            assert (decision.allowed, decision.reason) == (False, "feature_disabled")
            assert not await AUTHZ.allowed("ListTasks", user=user, workspace="ws-1", id="-")


def test_a_configuration_that_still_sets_the_role_features_is_warned(caplog):
    assert role_features.warn_deprecated_settings(FeatureFlagsConfig()) == []
    assert role_features.warn_deprecated_settings(FLAGS) == [
        "role_baseline",
        "organization_overrides",
    ]
    assert "no longer do anything" in caplog.text


@pytest.mark.asyncio
async def test_what_cannot_move_is_named_and_the_rest_waits(nexus_db, monkeypatch, caplog):
    """One attachment that fails (a stale row, say) is named for the operator;
    the move goes on with the rest but is not recorded, so nothing is retired
    and nobody loses a feature; the next start finishes it."""
    nexus = _previous(_world())
    with nexus.installed():
        before = _decisions(nexus)
        bob = nexus.principal("bob")
        real = nexus.iam.attach_policy

        def stale(policy_id, principal_id, scope=None):
            if principal_id == bob:
                raise RuntimeError("principal is gone")
            return real(policy_id, principal_id, scope)

        monkeypatch.setattr(nexus.iam, "attach_policy", stale)
        async with nexus_db() as db:
            await _previous_database(db, nexus)
            assert await role_features.migrate_role_features(db, FLAGS) is None
            assert f"builtin.member of {bob} at abi:org-1:ws-a" in caplog.text
            assert not await role_features._recorded(db, role_features.MIGRATION_NAME)
            assert _old_ids(nexus)
            nexus.iam.invalidate()
            assert _decisions(nexus) == before
            monkeypatch.setattr(nexus.iam, "attach_policy", real)
            assert await role_features.migrate_role_features(db, FLAGS)
            assert await role_features._recorded(db, role_features.RETIRED_NAME)
            # Retired and recorded: later starts look no more.
            monkeypatch.setattr(nexus.iam, "retired_policies", lambda: pytest.fail("looked again"))
            assert await role_features.migrate_role_features(db, FLAGS) is None
        nexus.iam.invalidate()
        assert _decisions(nexus) == before


@pytest.mark.asyncio
async def test_a_role_lowered_before_the_move_takes_the_old_features_of_the_higher(nexus_db):
    """Nexus lowers a role by attaching the new one, then detaching the old: the
    older version's admin features go with the admin role, never kept beside
    viewer."""
    nexus = _previous(_world())
    carol = nexus.principal("carol")
    with nexus.installed():
        with as_service_account("api"):
            nexus.iam.attach_policy(roles.VIEWER, carol, "abi:org-1:ws-b")
            nexus.iam.detach_policy(roles.ADMIN, carol, "abi:org-1:ws-b")
        held = {
            a.policy_id
            for a in nexus.iam.store.list_attachments(principal_id=carol)
            if a.scope == "abi:org-1:ws-b"
        }
        assert not any(p.endswith(".admin") for p in held), held
        async with nexus_db() as db:
            await _previous_database(db, nexus)
            await role_features.migrate_role_features(db, FLAGS)
        held = {
            p.name
            for a in nexus.iam.store.list_attachments(principal_id=carol)
            if a.scope == "abi:org-1:ws-b"
            for p in [nexus.iam.store.get_policy(a.policy_id)]
        }
        assert "Features of admin" not in held
