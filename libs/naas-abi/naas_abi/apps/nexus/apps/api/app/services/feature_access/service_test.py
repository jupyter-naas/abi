"""Workspace settings > General › Features and Agents/Apps over a real IAM and a
SQLite database: each choice is what the workspace's allow-list, "<W> access",
offers; IAM decides every write as the caller, a Deny elsewhere still wins, and a
statement written on the policy's page is left alone.

Acme offers Chat and Files and the module acme.sales; its workspace Alpha offers Chat
and Files. Olivia owns both (in "Alpha admins", so she holds what Alpha offers); Bob,
Carol and Dave are members of Alpha, and "Alpha members" holds "Alpha access" as the
workspace group will (S2); Erin is given an admin role at Alpha by hand, outside the
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
    OfferChange,
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
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
    Offer,
    offer_document,
    offer_of,
)
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
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam import module_scopes
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
    """Acme and Alpha made as the routes make them, their offers set."""
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
            org_record.access_policy_id,
            expected_revision=1,
            document=offer_document(Offer.of(modules=["acme.sales"], features=["chat", "files"])),
        )
        access = nexus.iam.get_policy(record.access_policy_id)
        nexus.iam.update_policy(
            record.access_policy_id,
            expected_revision=access.revision,
            document=offer_document(Offer.of(features=["chat", "files"])),
        )
    # As the workspace group will (S2): everyone in Alpha holds what it offers.
    with as_service_account("api"):
        nexus.iam.attach_policy(record.access_policy_id, record.members_group_id, ALPHA)
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


def _access(nexus: NexusIam, acme) -> object:
    with as_service_account("api"):
        return nexus.iam.get_policy(acme.access_policy_id)


@pytest.mark.asyncio
async def test_everyone_and_nobody_are_what_the_workspaces_access_policy_offers(
    nexus, acme, service, audit
):
    rows = _rows(await service.read("olivia", "alpha"))
    assert (rows["chat"]["choice"], rows["files"]["choice"]) == ("everyone", "everyone")
    assert rows["chat"]["policy"]["id"] == acme.access_policy_id
    assert all(_uses(nexus, user, "chat") for user in ("bob", "carol", "dave", "olivia"))

    state = await service.save(
        "olivia", "alpha", [FeatureChange("chat", "nobody"), FeatureChange("files", "everyone")]
    )
    assert state["errors"] == {}
    rows = _rows(state)
    assert (rows["chat"]["choice"], rows["files"]["choice"]) == ("nobody", "everyone")
    # One policy, the workspace's access: no "Feature · X" policy is made.
    assert offer_of(_access(nexus, acme).document).features == {"files"}
    assert not any(_uses(nexus, user, "chat") for user in ("bob", "dave"))
    # Olivia owns Acme: she holds its offer from above, as before.
    assert _uses(nexus, "olivia", "chat")
    assert audit.phases("feature-access.nobody") == ["requested", "succeeded"]
    with as_service_account("api"):
        names = {p.name for p in nexus.iam.list_policies(scope=ALPHA).items}
    assert not any(name.startswith("Feature · ") for name in names)

    state = await service.save("olivia", "alpha", [FeatureChange("chat", "everyone")])
    assert _rows(state)["chat"]["choice"] == "everyone" and _uses(nexus, "dave", "chat")


@pytest.mark.asyncio
async def test_only_is_refused_per_feature(nexus, acme, service):
    state = await service.save(
        "olivia",
        "alpha",
        [
            FeatureChange("chat", "only", (nexus.principal("bob"),)),
            FeatureChange("files", "nobody"),
        ],
    )
    assert "not a workspace setting" in state["errors"]["chat"]
    assert set(state["errors"]) == {"chat"}
    assert _rows(state)["chat"]["choice"] == "everyone"
    assert _rows(state)["files"]["choice"] == "nobody"


@pytest.mark.asyncio
async def test_a_newcomer_to_the_workspace_gets_what_it_offers(nexus, acme, service):
    assert not _uses(nexus, "frank", "chat")
    await MEMBERSHIPS.grant("frank", "member", ALPHA)
    assert _uses(nexus, "frank", "chat")
    await MEMBERSHIPS.revoke("frank", ALPHA)
    assert not _uses(nexus, "frank", "chat")


@pytest.mark.asyncio
async def test_a_caller_who_does_not_hold_the_feature_cannot_change_it(nexus, acme, service):
    await service.save("olivia", "alpha", [FeatureChange("chat", "nobody")])
    nexus.grant("erin", "admin", ALPHA)  # IAM's rights at Alpha, outside its groups: no feature
    rows = _rows(await service.read("erin", "alpha"))
    assert not rows["chat"]["editable"] and "do not hold Chat" in rows["chat"]["reason"]
    state = await service.save("erin", "alpha", [FeatureChange("chat", "everyone")])
    assert set(state["errors"]) == {"chat"}
    assert not _uses(nexus, "dave", "chat")
    # Not only this service's rule: IAM refuses her the widening itself.
    access = _access(nexus, acme)
    widened = offer_document(Offer.of(features=["chat", "files"]))
    with use_call_context(NexusIam.context("erin")), pytest.raises(PermissionDeniedError):
        nexus.iam.update_policy(
            acme.access_policy_id, expected_revision=access.revision, document=widened
        )


@pytest.mark.asyncio
async def test_a_feature_the_organization_does_not_offer_is_said_and_refused(nexus, acme, service):
    rows = _rows(await service.read("root", "alpha"))
    assert (rows["chat"]["offered"], rows["marketplace"]["offered"]) == (True, False)
    assert rows["marketplace"]["held"] and rows["marketplace"]["editable"]
    state = await service.save("root", "alpha", [FeatureChange("marketplace", "everyone")])
    assert "not offered in this workspace's organization" in state["errors"]["marketplace"]
    assert _rows(state)["marketplace"]["choice"] == "nobody"


@pytest.mark.asyncio
async def test_a_deny_elsewhere_wins_and_other_policies_are_listed(nexus, acme, service):
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
    # The workspace's access policy is the choice, never listed beside it.
    assert "Alpha access" not in {a["name"] for a in rows["chat"]["also"]}
    assert rows["chat"]["choice"] == "everyone" and rows["chat"]["editable"]


@pytest.mark.asyncio
async def test_a_feature_allowed_on_the_policy_page_is_shown_read_only(nexus, acme, service):
    access = _access(nexus, acme)
    document = offer_document(Offer.of(features=["files"]))
    document["statements"].append({**_features("chat")["statements"][0], "sid": "ByHand"})
    with use_call_context(NexusIam.context("root")):
        nexus.iam.update_policy(
            acme.access_policy_id, expected_revision=access.revision, document=document
        )
    row = _rows(await service.read("olivia", "alpha"))["chat"]
    assert row["choice"] == "everyone"
    assert row["hand_edited"] and not row["editable"] and "policy page" in row["reason"]
    state = await service.save("olivia", "alpha", [FeatureChange("chat", "nobody")])
    assert "chat" in state["errors"] and _uses(nexus, "dave", "chat")


@pytest.mark.asyncio
async def test_a_batch_naming_an_unknown_feature_or_nobody_changes_nothing(nexus, acme, service):
    for changes in (
        [FeatureChange("chat", "nobody"), FeatureChange("tasks", "everyone")],
        [FeatureChange("chat", "only")],
        [FeatureChange("chat", "everyone"), FeatureChange("chat", "nobody")],
    ):
        with pytest.raises(ValueError):
            await service.save("olivia", "alpha", changes)
    assert _rows(await service.read("olivia", "alpha"))["chat"]["choice"] == "everyone"
    assert await service.managed_among(["pol_none"]) == {}


@pytest.mark.asyncio
async def test_access_policies_still_marks_the_policies_an_older_general_wrote(
    nexus, acme, nexus_db, service, audit
):
    from naas_abi.apps.nexus.apps.api.app.services.iam_admin.service import IamAdminService

    with use_call_context(NexusIam.context("root")):
        older = nexus.iam.create_policy("Feature · Chat", _features("chat"), scope=ALPHA)
    await SqlFeaturePolicyStore(nexus_db).put("alpha", "chat", older.id)
    admin = IamAdminService(
        EngineIamGateway(), audit, managed_from=SqlFeaturePolicyStore(nexus_db).managed_among
    )
    listed = (await admin.list_policies("olivia", scope=ALPHA))["items"]
    marks = {p["id"]: p["managed_from"] for p in listed}
    assert marks[older.id] == "general"
    assert marks[acme.access_policy_id] is None


# -- agents, apps, workflows and pipelines ------------------------------------------------


def _uses_agent(nexus: NexusIam, user: str, module: str, name: str) -> bool:
    resource = module_scopes.scope_resource("agent", module, name, container=ALPHA)
    with use_call_context(NexusIam.context(user)):
        return nexus.iam.authorize("module:UseAgent", resource).allowed


@pytest.mark.asyncio
async def test_agents_and_apps_are_offered_in_the_workspaces_access_policy(
    nexus, acme, service, audit
):
    state = await service.read_offer("olivia", "alpha")
    assert state["editable"] and state["offered"]["agents"] == []
    assert not _uses_agent(nexus, "dave", "acme.sales", "SalesAgent")
    state = await service.save_offer(
        "olivia", "alpha", [OfferChange("agents", "acme.sales", "SalesAgent", True)]
    )
    assert state["offered"]["agents"] == [{"module": "acme.sales", "name": "SalesAgent"}]
    assert _uses_agent(nexus, "dave", "acme.sales", "SalesAgent")
    assert not _uses_agent(nexus, "dave", "acme.sales", "OtherAgent")
    assert audit.phases("workspace-offer.update") == ["requested", "succeeded"]
    # Features are kept: one policy, sections apart.
    assert offer_of(_access(nexus, acme).document).features == {"chat", "files"}
    # Beyond what the organization offers: IAM refuses it (it would grant nothing),
    # nothing changes.
    with pytest.raises(ValueError, match="would grant nothing"):
        await service.save_offer(
            "olivia", "alpha", [OfferChange("agents", "other.module", "X", True)]
        )
    state = await service.save_offer(
        "olivia", "alpha", [OfferChange("agents", "acme.sales", "SalesAgent", False)]
    )
    assert state["offered"]["agents"] == []
    assert not _uses_agent(nexus, "dave", "acme.sales", "SalesAgent")
