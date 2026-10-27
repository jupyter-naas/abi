"""Nexus and the sets: the move of the feature overrides (no one's features
change), a new workspace's set from its catalog seed, and the flags a user gets."""

from __future__ import annotations

from datetime import datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import (
    BASELINE_ROLES,
    KNOWN_FEATURE_KEYS,
    enabled_feature_catalog,
    resolve_role_baseline,
)
from naas_abi.apps.nexus.apps.api.app.models import OrganizationModel, WorkspaceModel
from naas_abi.apps.nexus.apps.api.app.services.iam import sets
from naas_abi_core.engine.call_context import as_service_account
from sqlalchemy import text

FLAGS = FeatureFlagsConfig()
NOW = datetime(2026, 1, 1)
ENABLED = enabled_feature_catalog(FLAGS)


def _old_flags(role: str, overrides: dict[str, bool]) -> dict[str, bool]:
    """What a role had in a workspace with ``overrides``, before sets: its
    defaults, then each override on or off for every role."""
    features = set(resolve_role_baseline(FLAGS).get(role, []))
    for key, on in overrides.items():
        (features.add if on else features.discard)(key)
    return {key: key in features and key in ENABLED for key in KNOWN_FEATURE_KEYS}


def test_an_off_override_leaves_the_set_and_an_on_one_is_kept_for_roles_lacking_it():
    moves = sets.plan_override_moves(
        {"ws-1": {"maps": False, "apps": True}, "ws-2": {"chat": True}, "ws-3": {}},
        org_of={"ws-1": "org-1", "ws-2": None, "ws-3": "org-1"},
        enabled=ENABLED,
        role_defaults={None: resolve_role_baseline(FLAGS)},
    )

    assert [(m.org, m.workspace) for m in moves] == [("org-1", "ws-1"), ("_none", "ws-2")]
    first, second = moves
    assert first.features is not None and "maps" not in first.features
    # Every other known feature, one the deployment enables later included.
    assert "code" in first.features and "settings" in first.features
    assert "apps" in first.features
    # Owners and admins have apps by default; members and viewers kept it.
    assert dict(first.kept) == {"member": ("apps",), "viewer": ("apps",)}
    # Every role has chat: nothing to keep, nothing narrows.
    assert second.features is None and dict(second.kept) == {}


def test_a_catalog_seed_narrows_only_the_types_it_names_within_the_orgs():
    seed = sets.SeedItems(agents=frozenset({("people", "A"), ("crm", "Sales")}), apps=None)

    narrowed = sets.narrowed_by_seed(("people", "agent/crm/*", "workflow/crm/Sync"), seed)

    # The seeded agents the org has (through its whole module or a wildcard);
    # the rest of each module as the org has it.
    assert narrowed == (
        "agent/crm/Sales",
        "agent/people/A",
        "app/people/*",
        "people:*",
        "pipeline/people/*",
        "workflow/crm/Sync",
        "workflow/people/*",
    )
    # A seeded agent the org does not have stays out.
    assert sets.narrowed_by_seed(("people",), sets.SeedItems(frozenset({("crm", "X")}), None)) == (
        "app/people/*",
        "people:*",
        "pipeline/people/*",
        "workflow/people/*",
    )
    # No seed of agents or apps: the org's items as they are.
    assert sets.narrowed_by_seed(("people",), sets.SeedItems(None, None)) == ("people",)


def test_a_seed_in_an_org_with_no_set_snapshots_no_module():
    seed = sets.SeedItems(agents=frozenset({("people", "A")}), apps=frozenset())

    narrowed = sets.narrowed_by_seed(None, seed)

    # Every module, installed now or later, for what the seed does not name.
    assert narrowed == ("*:*", "agent/people/A", "pipeline/*/*", "workflow/*/*")


def test_an_off_override_keeps_later_features_and_settings():
    from naas_abi.apps.nexus.apps.api.app.core.feature_flags import feature_set_from_overrides

    found = feature_set_from_overrides({"maps": False, "settings": False, "chat": True})
    assert found is not None
    assert "maps" not in found and "settings" in found and "code" in found
    assert feature_set_from_overrides({"chat": True}) is None


@pytest.mark.asyncio
async def test_the_move_of_the_overrides_changes_no_ones_features(team, nexus_db):
    overrides = {"maps": False, "apps": True}
    async with nexus_db() as db:
        await db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS iam_migrations (name VARCHAR(128) PRIMARY KEY, "
                "applied_at TIMESTAMP, report TEXT)"
            )
        )
        db.add(
            OrganizationModel(
                id="org-1", name="EDF", slug="edf", owner_id="owner", created_at=NOW, updated_at=NOW
            )
        )
        db.add(
            WorkspaceModel(
                id="ws-1",
                name="W",
                slug="w",
                owner_id="owner",
                organization_id="org-1",
                created_at=NOW,
                updated_at=NOW,
                feature_overrides='{"maps": false, "apps": true}',
            )
        )
        await db.commit()

        moved = await sets.migrate_feature_overrides(db, FLAGS)

        assert moved == 1
        for role in BASELINE_ROLES:
            flags = await sets.user_feature_flags(role, [("org-1", "ws-1")], ENABLED)
            assert flags is not None
            assert flags["ws-1"] == _old_flags(role, overrides), role
        column = (await db.execute(text("SELECT feature_overrides FROM workspaces"))).scalar()
        assert column is None
        # Once: a second start changes nothing.
        assert await sets.migrate_feature_overrides(db, FLAGS) == 0
    with as_service_account("engine"):
        assert "maps" not in (team.iam.get_set("org-1", "ws-1").features or ())


@pytest.mark.asyncio
async def test_a_users_flags_are_iams_within_the_sets(team):
    with as_service_account("engine"):
        team.iam.put_set("org-1", "ws-1", features=["chat", "settings"])

    flags = await sets.user_feature_flags("member", [("org-1", "ws-1")], ENABLED)

    assert flags is not None
    assert [k for k, on in flags["ws-1"].items() if on] == ["chat"]
    # A feature the deployment turned off is never on, even for the platform admin.
    team.platform_admin("root")
    root = await sets.user_feature_flags("root", [("org-1", "ws-1")], ENABLED)
    assert root is not None and root["ws-1"]["code"] is False and root["ws-1"]["maps"] is True


@pytest.mark.asyncio
async def test_a_new_workspace_follows_its_org_unless_something_narrows(team):
    with as_service_account("engine"):
        team.iam.put_set("org-1", modules=["people"], features=["chat"])

    assert await sets.seed_workspace("org-1", "ws-1") is None
    with as_service_account("engine"):
        team.iam.put_set("org-1", modules=["people", "market"], features=["chat", "maps"])
        effective = team.iam.effective_set("org-1", "ws-1")
    assert effective.modules == ("market", "people")
    assert effective.features == ("chat", "maps")

    # Features chosen: that part alone is recorded, the modules still follow.
    recorded = await sets.seed_workspace("org-1", "ws-1", features=["chat", "files"])
    assert recorded is not None
    assert (recorded.modules, recorded.features) == (None, ("chat",))


def test_the_move_runs_again_without_duplicates(team):
    team.grant("bob", "member", "abi:org-1:ws-1")
    team.grant("olga", "admin", "abi:org-1:-")  # org-wide through the mirror
    move = sets.OverrideMove("org-1", "ws-1", None, {"member": ("apps",), "admin": ("apps",)})
    with as_service_account("engine"):
        sets._apply_move(team.iam, move)
        sets._apply_move(team.iam, move)
        kept = [
            p
            for p in team.iam.list_policies(scope="abi:org-1:ws-1", limit=200).items
            if p.name == sets.KEPT_FEATURES_POLICY
        ]
        holders = {a.principal_id for a in team.iam.list_attachments(policy_id=kept[0].id)}
    assert len(kept) == 1
    # The team's member and admin, Bob, and Olga, an org admin who holds her role
    # org-wide: she keeps it too.
    with as_service_account("engine"):
        olga = team.iam.store.find_user("urn:abi:nexus", "olga")
    assert olga is not None and olga.id in holders and len(holders) == 4


def test_the_move_keeps_within_an_org_narrowed_since(team):
    """A migration retried after the platform admin narrowed the org: the
    workspace's set is recorded within the org's, never refused on every boot."""
    with as_service_account("engine"):
        team.iam.put_set("org-1", modules=["people", "market"], features=["chat", "maps"])
        team.iam.put_set("org-1", "ws-1", modules=["people", "market"])
        team.iam.put_set("org-1", modules=["people"], features=["chat"])
        sets._apply_move(
            team.iam, sets.OverrideMove("org-1", "ws-1", ("chat", "files", "maps"), {})
        )
        found = team.iam.get_set("org-1", "ws-1")
    assert (found.modules, found.features) == (("people",), ("chat",))


@pytest.mark.asyncio
async def test_iam_failing_shows_less_never_more_and_never_a_500(team, monkeypatch):
    class Broken:
        def __getattr__(self, name):
            raise TimeoutError("NATS timeout")

    monkeypatch.setattr(sets.runtime, "iam", lambda: Broken())

    flags = await sets.user_feature_flags("member", [("org-1", "ws-1")], ENABLED)
    assert flags is not None and not any(flags["ws-1"].values())
    assert sets.effective_set("org-1", "ws-1").features == ()


@pytest.mark.asyncio
async def test_an_interrupted_move_is_not_recorded_and_finishes_next_start(
    team, nexus_db, monkeypatch
):
    async with nexus_db() as db:
        await db.execute(
            text(
                "CREATE TABLE IF NOT EXISTS iam_migrations (name VARCHAR(128) PRIMARY KEY, "
                "applied_at TIMESTAMP, report TEXT)"
            )
        )
        db.add(
            WorkspaceModel(
                id="ws-1",
                name="W",
                slug="w",
                owner_id="owner",
                organization_id="org-1",
                created_at=NOW,
                updated_at=NOW,
                feature_overrides='{"apps": true}',
            )
        )
        await db.commit()
        real = sets._apply_move

        def failing(iam, move):
            raise TimeoutError("NATS timeout")

        monkeypatch.setattr(sets, "_apply_move", failing)
        assert await sets.migrate_feature_overrides(db, FLAGS) == 0
        recorded = (await db.execute(text("SELECT count(*) FROM iam_migrations"))).scalar()
        column = (await db.execute(text("SELECT feature_overrides FROM workspaces"))).scalar()
        assert recorded == 0 and column is not None

        monkeypatch.setattr(sets, "_apply_move", real)
        assert await sets.migrate_feature_overrides(db, FLAGS) == 1
        assert await sets.migrate_feature_overrides(db, FLAGS) == 0
