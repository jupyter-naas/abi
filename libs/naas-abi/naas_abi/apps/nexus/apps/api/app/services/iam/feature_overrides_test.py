"""The move of the workspace feature overrides, then the move of the names.

On an install before container paths (``testing.LegacyNexusIam``): a feature an
``on`` override gave a role it lacked by default is kept, as a workspace policy,
for who held that role there (directly or org-wide); the move writes the old
grammar, and once the names are rewritten (``container_names``) the same people
use the same features, on the names of today."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.models import OrganizationModel, WorkspaceModel
from naas_abi.apps.nexus.apps.api.app.services.iam import feature_overrides, legacy_names
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    nexus_resource,
    workspace_container,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import LegacyNexusIam, NexusIam
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from sqlalchemy import text

NOW = datetime(2026, 1, 1)
FEATURES = ["chat", "files", "graph", "settings"]
FLAGS = FeatureFlagsConfig(
    enabled_features=FEATURES,
    role_baseline={
        "owner": FEATURES,
        "admin": ["chat", "files", "settings"],
        "member": ["chat"],
        "viewer": ["chat"],
    },
)
WORKSPACES = {"ws-a": "org-1", "ws-b": "org-1", "ws-d": None}
# ws-a and ws-d turned graph on (members lacked it) and files off.
OVERRIDES = {"ws-a": {"graph": True, "files": False}, "ws-d": {"graph": True}}
USERS = (
    "alice",  # owner of org-1: org-wide
    "bob",  # member of ws-a
    "carol",  # viewer of ws-a
    "dave",  # member of ws-b, which has no override
    "gina",  # admin of org-1: org-wide
    "henry",  # member of ws-d, a workspace with no organization
)


def _world() -> LegacyNexusIam:
    nexus = LegacyNexusIam(FLAGS)
    scopes = {ws: nexus.workspace(org, ws) for ws, org in WORKSPACES.items()}
    nexus.grant("alice", "owner", nexus.org("org-1"))
    nexus.grant("bob", "member", scopes["ws-a"])
    nexus.grant("carol", "viewer", scopes["ws-a"])
    nexus.grant("dave", "member", scopes["ws-b"])
    nexus.grant("gina", "admin", nexus.org("org-1"))
    nexus.grant("henry", "member", scopes["ws-d"])
    return nexus


async def _previous_database(db) -> None:
    await db.execute(
        text(
            "CREATE TABLE IF NOT EXISTS iam_migrations (name VARCHAR(128) PRIMARY KEY, "
            "applied_at TIMESTAMP, report TEXT)"
        )
    )
    db.add(
        OrganizationModel(
            id="org-1", name="org-1", slug="org-1", owner_id="alice", created_at=NOW, updated_at=NOW
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
                feature_overrides=json.dumps(OVERRIDES[ws]) if ws in OVERRIDES else None,
                created_at=NOW,
                updated_at=NOW,
            )
        )
    await db.commit()


def _feature(nexus: LegacyNexusIam, ws: str, key: str) -> str:
    """A feature of a workspace, named in the grammar the world is in."""
    org = WORKSPACES[ws]
    if nexus.rewritten:
        return nexus_resource("feature", container=workspace_container(org, ws), id=key)
    return f"{legacy_names.workspace_scope(org, ws)}:nexus:feature/{key}"


def _decisions(nexus: LegacyNexusIam) -> dict[tuple[str, str, str], bool]:
    found: dict[tuple[str, str, str], bool] = {}
    for user in USERS:
        with use_call_context(NexusIam.context(user)):
            for ws in WORKSPACES:
                for key in FEATURES:
                    allowed = nexus.iam.authorize("nexus:UseFeature", _feature(nexus, ws, key))
                    found[(user, ws, key)] = allowed.allowed
    return found


@pytest.mark.asyncio
async def test_a_kept_feature_is_kept_through_the_move_of_the_names(nexus_db):
    nexus = _world()
    with nexus.installed():
        async with nexus_db() as db:
            await _previous_database(db)
            assert await feature_overrides.migrate_feature_overrides(db, FLAGS) == 2
        kept = {k for k, v in _decisions(nexus).items() if v}
        # Who held a role lacking graph where it was turned on keeps it; nothing else.
        assert kept == {
            ("bob", "ws-a", "graph"),
            ("carol", "ws-a", "graph"),
            ("gina", "ws-a", "graph"),
            ("henry", "ws-d", "graph"),
        }
        nexus.rewrite()
        assert {k for k, v in _decisions(nexus).items() if v} == kept
    with as_service_account("engine"):
        owners = {
            p.owner_scope
            for p in nexus.iam._all_policies()
            if p.name == feature_overrides.KEPT_FEATURES_POLICY
        }
    assert owners == {workspace_container("org-1", "ws-a"), workspace_container(None, "ws-d")}
