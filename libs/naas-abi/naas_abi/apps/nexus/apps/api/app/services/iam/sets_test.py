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
    assert "apps" in first.features
    # Owners and admins have apps by default; members and viewers kept it.
    assert dict(first.kept) == {"member": ("apps",), "viewer": ("apps",)}
    # Every role has chat: nothing to keep, nothing narrows.
    assert second.features is None and dict(second.kept) == {}


def test_a_catalog_seed_narrows_agents_and_apps_and_keeps_the_rest():
    exposed = [
        {
            "module": "people",
            "agents": [{"name": "A"}, {"name": "B"}],
            "apps": [{"name": "Viewer"}],
            "workflows": [{"name": "sync"}],
            "pipelines": [],
            "declared": {"actions": [{"action": "people:Export"}]},
        },
        {
            "module": "market",
            "agents": [{"name": "C"}],
            "apps": [],
            "workflows": [],
            "pipelines": [],
            "declared": None,
        },
    ]
    seed = sets.SeedItems(agents=frozenset({("people", "A")}), apps=frozenset())

    narrowed = sets.narrowed_by_seed(None, exposed, seed)

    assert narrowed is not None
    assert "agent/people/A" in narrowed and "agent/people/B" not in narrowed
    assert "agent/market/C" not in narrowed and "app/people/Viewer" not in narrowed
    assert {"workflow/people/*", "pipeline/people/*", "people:Export"} <= set(narrowed)
    # Within the org's: a module the org lacks stays out.
    only_people = sets.narrowed_by_seed(("people",), exposed, seed)
    assert only_people is not None and not any("market" in i for i in only_people)
    # No seed of agents or apps: the org's items as they are.
    assert sets.narrowed_by_seed(("people",), exposed, sets.SeedItems(None, None)) == ("people",)


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
