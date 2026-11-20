"""Workspace settings > General › Features over a real IAM and a SQLite database:
each choice is where the feature's policy is attached, IAM decides every write as
the caller, a Deny elsewhere still wins, and a policy changed by hand is left alone.

Acme allows Chat, Files and Marketplace; its workspace Alpha offers Chat and Files.
Olivia owns both (in "Alpha admins", so she holds what Alpha offers); Bob, Carol and
Dave are members of Alpha; Erin is given an admin role at Alpha by hand, outside the
groups, so she holds IAM's rights there and no feature; root is a platform admin."""

from __future__ import annotations

from datetime import datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.models import UserModel
from naas_abi.apps.nexus.apps.api.app.services.feature_access.adapters.secondary.postgres import (  # noqa: E501
    SqlFeaturePolicyStore,
)
from naas_abi.apps.nexus.apps.api.app.services.feature_access.port import FeatureChange
from naas_abi.apps.nexus.apps.api.app.services.feature_access.service import (
    FeatureAccessService,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
    CONTAINER_DEFAULTS,
    SqlDefaultsStore,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    nexus_resource,
    org_container,
    workspace_container,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.engine import (
    EngineIamGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.testing import MemoryAudit
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (  # noqa: E501
    OrganizationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import OrganizationService
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (  # noqa: E501
    WorkspaceSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceCreateInput
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import WorkspaceService
from naas_abi_core.engine.call_context import use_call_context
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError

NOW = datetime(2026, 1, 1)
FEATURES = ["chat", "files", "marketplace"]
ALPHA = workspace_container("acme", "alpha")
USE = "nexus:UseFeature"


def _features(*keys: str) -> dict:
    return {
        "version": "2026-10-13",
        "statements": [
            {
                "effect": "Allow",
                "actions": [USE],
                "resources": [f"${{scope}}/nexus:feature/{k}" for k in keys],
            }
        ],
    }


def _forget() -> None:
    CONTAINER_DEFAULTS._known.clear()
    CONTAINER_DEFAULTS._missing.clear()
    CONTAINER_DEFAULTS.session_factory = None


@pytest.fixture
def nexus():
    _forget()
    world = NexusIam(FeatureFlagsConfig(enabled_features=FEATURES), features_with_roles=False)
    with world.installed():
        yield world
    _forget()


@pytest.fixture
async def acme(nexus, nexus_db):
    """Acme and Alpha made as the routes make them, their access policies widened."""
    async with nexus_db() as db:
        for user_id in ("olivia", "bob", "carol", "dave", "frank", "erin", "root"):
            db.add(
                UserModel(
                    id=user_id,
                    email=f"{user_id}@example.com",
                    name=user_id.title(),
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        await db.flush()
        orgs = OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))
        await orgs.create_organization(
            name="Acme", slug="acme", owner_id="olivia", now=NOW, org_id="acme"
        )
        workspaces = WorkspaceService(adapter=WorkspaceSecondaryAdapterPostgres(db=db))
        await workspaces.create_workspace(
            WorkspaceCreateInput(
                name="Alpha", slug="alpha", owner_id="olivia", organization_id="acme", id="alpha"
            )
        )
        await db.commit()
        store = SqlDefaultsStore(db)
        org_record = await store.get(org_container("acme"))
        record = await store.get(ALPHA)
    for user_id in ("bob", "carol", "dave"):
        await MEMBERSHIPS.grant(user_id, "member", ALPHA)
    nexus.platform_admin("root")
    with use_call_context(NexusIam.context("root")):
        nexus.iam.update_policy(
            org_record.access_policy_id, expected_revision=1, document=_features(*FEATURES)
        )
        nexus.iam.update_policy(
            record.access_policy_id, expected_revision=1, document=_features("chat", "files")
        )
    return record


@pytest.fixture
def audit() -> MemoryAudit:
    return MemoryAudit()


@pytest.fixture
def service(nexus_db, audit) -> FeatureAccessService:
    return FeatureAccessService(
        EngineIamGateway(),
        SqlFeaturePolicyStore(nexus_db),
        audit,
        container_of=AUTHZ.container_of,
        defaults_of=CONTAINER_DEFAULTS.record_of,
        features=lambda: FEATURES,
    )


def _uses(nexus: NexusIam, user: str, key: str) -> bool:
    with use_call_context(NexusIam.context(user)):
        return nexus.iam.authorize(USE, nexus_resource("feature", container=ALPHA, id=key)).allowed


def _rows(state: dict) -> dict[str, dict]:
    return {row["key"]: row for row in state["features"]}


@pytest.mark.asyncio
async def test_everyone_only_and_nobody_are_where_the_feature_policy_is_attached(
    nexus, acme, service, audit
):
    bob = nexus.principal("bob")
    state = await service.save(
        "olivia",
        "alpha",
        [FeatureChange("chat", "everyone"), FeatureChange("files", "only", (bob,))],
    )
    assert state["errors"] == {}
    rows = _rows(state)
    assert rows["chat"]["choice"] == "everyone"
    assert (rows["files"]["choice"], [p["id"] for p in rows["files"]["principals"]]) == (
        "only",
        [bob],
    )
    with use_call_context(NexusIam.context("root")):
        chat = nexus.iam.get_policy(rows["chat"]["policy"]["id"])
    # One policy per feature, the workspace's, below its access policy.
    assert (chat.name, chat.owner_scope, chat.parent_id) == (
        "Feature · Chat",
        ALPHA,
        acme.access_policy_id,
    )
    assert all(_uses(nexus, user, "chat") for user in ("bob", "carol", "dave", "olivia"))
    assert _uses(nexus, "bob", "files") and not _uses(nexus, "dave", "files")
    assert audit.phases("feature-access.create") == ["requested", "succeeded"] * 2

    state = await service.save(
        "olivia", "alpha", [FeatureChange("chat", "nobody"), FeatureChange("files", "nobody")]
    )
    rows = _rows(state)
    assert (rows["chat"]["choice"], rows["files"]["choice"]) == ("nobody", "nobody")
    # Nobody detaches it: the policy stays, attached nowhere, and is used again later.
    assert rows["chat"]["policy"]["id"] == chat.id
    assert not any(_uses(nexus, user, "chat") for user in ("bob", "dave"))
    assert not _uses(nexus, "bob", "files")
    state = await service.save("olivia", "alpha", [FeatureChange("chat", "everyone")])
    assert _rows(state)["chat"]["policy"]["id"] == chat.id and _uses(nexus, "dave", "chat")


@pytest.mark.asyncio
async def test_a_newcomer_joining_the_members_gets_the_everyone_features(nexus, acme, service):
    await service.save("olivia", "alpha", [FeatureChange("chat", "everyone")])
    assert not _uses(nexus, "frank", "chat")
    await MEMBERSHIPS.grant("frank", "member", ALPHA)
    assert _uses(nexus, "frank", "chat")
    await MEMBERSHIPS.revoke("frank", ALPHA)
    assert not _uses(nexus, "frank", "chat")


@pytest.mark.asyncio
async def test_a_caller_who_does_not_hold_the_feature_cannot_change_it(nexus, acme, service):
    state = await service.save(
        "olivia", "alpha", [FeatureChange("chat", "only", (nexus.principal("bob"),))]
    )
    policy_id = _rows(state)["chat"]["policy"]["id"]
    nexus.grant("erin", "admin", ALPHA)  # IAM's rights at Alpha, outside its groups: no feature
    rows = _rows(await service.read("erin", "alpha"))
    assert not rows["chat"]["editable"] and "do not hold Chat" in rows["chat"]["reason"]
    state = await service.save(
        "erin", "alpha", [FeatureChange("chat", "everyone"), FeatureChange("files", "everyone")]
    )
    assert set(state["errors"]) == {"chat", "files"}
    assert _rows(state)["chat"]["choice"] == "only" and _rows(state)["files"]["policy"] is None
    assert not _uses(nexus, "dave", "chat")
    # Not only this service's rule: IAM refuses her the attachment itself.
    with use_call_context(NexusIam.context("erin")), pytest.raises(PermissionDeniedError):
        nexus.iam.attach_policy(policy_id, acme.members_group_id, ALPHA)


@pytest.mark.asyncio
async def test_a_feature_the_workspace_does_not_offer_is_said_and_refused(nexus, acme, service):
    rows = _rows(await service.read("root", "alpha"))
    assert (rows["chat"]["offered"], rows["marketplace"]["offered"]) == (True, False)
    assert rows["marketplace"]["held"] and rows["marketplace"]["editable"]
    state = await service.save("root", "alpha", [FeatureChange("marketplace", "everyone")])
    assert "not offered in this workspace" in state["errors"]["marketplace"]
    assert _rows(state)["marketplace"]["policy"] is None


@pytest.mark.asyncio
async def test_a_deny_elsewhere_wins_and_other_policies_are_listed(nexus, acme, service):
    await service.save("olivia", "alpha", [FeatureChange("chat", "everyone")])
    dave = nexus.principal("dave")
    deny = {
        **_features("chat"),
        "statements": [{**_features("chat")["statements"][0], "effect": "Deny"}],
    }
    with use_call_context(NexusIam.context("root")):
        no_chat = nexus.iam.create_policy("No chat for Dave", deny, scope=ALPHA)
        nexus.iam.attach_policy(no_chat.id, dave, ALPHA)
        both = nexus.iam.create_policy(
            "Workspace features", _features("chat", "files"), scope=ALPHA
        )
        nexus.iam.attach_policy(both.id, acme.members_group_id, ALPHA)
    assert not _uses(nexus, "dave", "chat") and _uses(nexus, "carol", "chat")
    rows = _rows(await service.read("olivia", "alpha"))
    also = {(a["name"], a["effect"], a["attached"]) for a in rows["chat"]["also"]}
    assert {("No chat for Dave", "Deny", True), ("Workspace features", "Allow", True)} <= also
    assert ("Workspace features", "Allow", True) in {
        (a["name"], a["effect"], a["attached"]) for a in rows["files"]["also"]
    }
    assert rows["chat"]["choice"] == "everyone" and rows["chat"]["editable"]


@pytest.mark.asyncio
async def test_a_feature_policy_changed_by_hand_is_shown_read_only(nexus, acme, service):
    state = await service.save("olivia", "alpha", [FeatureChange("chat", "everyone")])
    policy_id = _rows(state)["chat"]["policy"]["id"]
    with use_call_context(NexusIam.context("root")):
        nexus.iam.update_policy(policy_id, expected_revision=1, document=_features("chat", "files"))
    row = _rows(await service.read("olivia", "alpha"))["chat"]
    assert row["hand_edited"] and not row["editable"] and "policy page" in row["reason"]
    state = await service.save("olivia", "alpha", [FeatureChange("chat", "nobody")])
    assert "chat" in state["errors"] and _uses(nexus, "dave", "chat")


@pytest.mark.asyncio
async def test_a_batch_naming_an_unknown_feature_or_nobody_changes_nothing(nexus, acme, service):
    for changes in (
        [FeatureChange("chat", "everyone"), FeatureChange("tasks", "everyone")],
        [FeatureChange("chat", "only")],
        [FeatureChange("chat", "everyone"), FeatureChange("chat", "nobody")],
    ):
        with pytest.raises(ValueError):
            await service.save("olivia", "alpha", changes)
    assert _rows(await service.read("olivia", "alpha"))["chat"]["policy"] is None
    assert await service.managed_among(["pol_none"]) == {}


@pytest.mark.asyncio
async def test_access_policies_marks_the_policies_general_manages(
    nexus, acme, nexus_db, service, audit
):
    from naas_abi.apps.nexus.apps.api.app.services.iam_admin.service import IamAdminService

    state = await service.save("olivia", "alpha", [FeatureChange("chat", "everyone")])
    chat = _rows(state)["chat"]["policy"]["id"]
    admin = IamAdminService(
        EngineIamGateway(), audit, managed_from=SqlFeaturePolicyStore(nexus_db).managed_among
    )
    listed = (await admin.list_policies("olivia", scope=ALPHA))["items"]
    marks = {p["id"]: p["managed_from"] for p in listed}
    assert marks[chat] == "general"
    assert marks[acme.access_policy_id] is None
    assert (await admin.get_policy("olivia", chat))["managed_from"] == "general"
