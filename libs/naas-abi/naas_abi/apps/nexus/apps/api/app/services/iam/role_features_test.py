"""The move of the role features into workspace policies, on a database at the
previous state: IAM holding the ``builtin.features.*`` the previous version
generated and attached beside each role, Nexus holding the organizations'
overlay table. Every user's ``UseFeature`` decisions are the same before and
after, in every workspace; then no role brings a feature."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import (
    KNOWN_FEATURE_KEYS,
    enabled_feature_catalog,
)
from naas_abi.apps.nexus.apps.api.app.models import OrganizationModel, WorkspaceModel
from naas_abi.apps.nexus.apps.api.app.services.iam import role_features
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.names import NO_ORG, nexus_resource
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.IAMPorts import Attachment, Policy
from naas_abi_core.services.iam.policy import PolicyDocument, Statement
from sqlalchemy import inspect, text

NOW = datetime(2026, 1, 1)
EVERY = [key for key in KNOWN_FEATURE_KEYS if key not in ("code", "tasks")]
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
            name = role.removeprefix("builtin.")
            keys = [f"{org}.{workspace}.{name}"] if workspace != "*" else []
            keys += [f"{org}.{name}", name]
            key = next(k for k in keys if k in plan)
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
    scopes = {
        ws: nexus.workspace(org, ws) for ws, org in WORKSPACES.items()
    }  # registers the orgs too
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
    return nexus


def _decisions(nexus: NexusIam) -> dict[tuple[str, str, str], bool]:
    """IAM's ``UseFeature`` for every user, workspace and known feature."""
    names = {
        (ws, key): nexus_resource("feature", org=org or NO_ORG, workspace=ws, id=key)
        for ws, org in WORKSPACES.items()
        for key in KNOWN_FEATURE_KEYS
    }
    found: dict[tuple[str, str, str], bool] = {}
    for user in USERS:
        with use_call_context(NexusIam.context(user)):
            allowed = set(nexus.iam.filter("nexus:UseFeature", list(names.values())).allowed)
        for (ws, key), name in names.items():
            found[(user, ws, key)] = name in allowed
    return found


async def _previous_database(db) -> None:
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
    await db.commit()


async def _has_table(db, name: str) -> bool:
    connection = await db.connection()
    return await connection.run_sync(lambda sync: inspect(sync).has_table(name))


@pytest.mark.asyncio
async def test_every_user_keeps_exactly_their_features(nexus_db):
    nexus = _world()
    _store_previous_state(nexus, _old_plan(FLAGS, {"org-1": OVERLAY}))
    with nexus.installed():
        before = _decisions(nexus)
        # The previous state is not empty: the move has something to keep.
        assert before[("bob", "ws-a", "graph")] and not before[("bob", "ws-a", "files")]
        assert before[("alice", "ws-b", "settings")] and before[("frank", "ws-b", "graph")]
        assert before[("dave", "ws-c", "chat")] is False
        nexus.iam.bootstrap()  # the engine starts: the old policies go
        nexus.iam.invalidate()
        assert not before == _decisions(nexus)
        async with nexus_db() as db:
            await _previous_database(db)
            made = await role_features.migrate_role_features(db, FLAGS)
            assert made
            assert not await _has_table(db, "organization_role_features")
            recorded = (
                await db.execute(
                    text("SELECT 1 FROM iam_migrations WHERE name = :n"),
                    {"n": role_features.MIGRATION_NAME},
                )
            ).first()
            assert recorded is not None
            after = _decisions(nexus)
            assert after == before
            # Once: a second start changes nothing, and adds no policy.
            policies = {p.id for p in nexus.iam._all_policies()}
            assert await role_features.migrate_role_features(db, FLAGS) is None
            assert {p.id for p in nexus.iam._all_policies()} == policies
            assert _decisions(nexus) == before
    assert not any(p.startswith("builtin.features.") for p in policies)
    owned = {(p.owner_scope, p.name) for p in nexus.iam._all_policies() if not p.managed}
    # Each workspace has one for every role that had features, held or not:
    # nobody is a member of ws-d, yet an invitation there can carry it.
    for role in ("owner", "admin", "member", "viewer"):
        assert (f"abi:{NO_ORG}:ws-d", f"Features of {role}") in owned
    # org-2's members had none: no policy to carry.
    assert ("abi:org-2:ws-c", "Features of member") not in owned


@pytest.mark.asyncio
async def test_an_interrupted_move_is_not_recorded_and_finishes_next_start(
    nexus_db, monkeypatch
):
    nexus = _world()
    _store_previous_state(nexus, _old_plan(FLAGS, {"org-1": OVERLAY}))
    with nexus.installed():
        before = _decisions(nexus)
        nexus.iam.bootstrap()
        async with nexus_db() as db:
            await _previous_database(db)
            real = role_features.apply

            def failing(iam, move, attachments):
                if move.workspace == "ws-b":
                    raise RuntimeError("IAM went away")
                return real(iam, move, attachments)

            monkeypatch.setattr(role_features, "apply", failing)
            await role_features.migrate_role_features(db, FLAGS)
            # Not recorded, and the overlay is kept for the next start.
            assert await _has_table(db, "organization_role_features")
            monkeypatch.setattr(role_features, "apply", real)
            assert await role_features.migrate_role_features(db, FLAGS)
            assert not await _has_table(db, "organization_role_features")
        nexus.iam.invalidate()
        assert _decisions(nexus) == before


@pytest.mark.asyncio
async def test_the_move_waits_for_the_workspace_overrides(nexus_db):
    nexus = _world()
    with nexus.installed():
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
            assert not await AUTHZ.allowed(
                "ListTasks", user=user, workspace="ws-1", id="-"
            )


def test_a_configuration_that_still_sets_the_role_features_is_warned(caplog):
    assert role_features.warn_deprecated_settings(FeatureFlagsConfig()) == []
    assert role_features.warn_deprecated_settings(FLAGS) == [
        "role_baseline",
        "organization_overrides",
    ]
    assert "no longer do anything" in caplog.text
