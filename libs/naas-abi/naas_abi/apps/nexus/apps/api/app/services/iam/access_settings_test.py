"""The deployment's access choices (ADR ``20261120_access_levels_and_groups``):
who creates organizations and personal workspaces (``builtin.self``,
``nexus_config.personal_workspaces``), the model sets, and the capability groups.
A real IAM: nothing about who may do what is mocked."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam import model_sets
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.bootstrap import (
    apply_access_settings,
    self_grants,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.capabilities import (
    MODELS_ALL,
    WORKFLOW_RUNNERS,
    ensure_capability,
    find_capability,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import make_org
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    org_container,
    workspace_container,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import Offer, offer_document
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam import module_scopes

W = workspace_container("acme", "w")
MODEL = "abi:model_registry:model/{}"


@pytest.fixture
def world():
    model_sets.forget()
    nexus = NexusIam(features_with_roles=False)
    nexus.workspace("acme", "w")
    nexus.grant("owner", "owner", org_container("acme"))
    nexus.grant("member", "member", W)
    nexus.grant("viewer", "viewer", W)
    nexus.user("plain")
    nexus.platform_admin("root")
    with nexus.installed():
        yield nexus
    model_sets.forget()


def _allowed(nexus: NexusIam, user: str, action: str, resource: str) -> bool:
    with use_call_context(NexusIam.context(user)):
        return nexus.iam.authorize(action, resource).allowed


def _settings(monkeypatch, **values) -> None:
    from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings

    live = live_settings()
    for key, value in values.items():
        monkeypatch.setattr(live, key, value, raising=False)


# -- builtin.self ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_plain_user_creates_no_organization_and_no_personal_workspace(world, monkeypatch):
    _settings(monkeypatch, personal_workspaces=False)
    apply_access_settings(world.iam)
    assert not await AUTHZ.allowed("CreateOrganization", user="plain", id="org-new")
    assert not await AUTHZ.allowed("CreateWorkspace", user="plain", org=None, id="ws-new")
    # The platform admins create organizations; an org owner, workspaces in it.
    assert await AUTHZ.allowed("CreateOrganization", user="root", id="org-new")
    assert await AUTHZ.allowed("CreateWorkspace", user="owner", org="acme", id="ws-new")
    assert not await AUTHZ.allowed("CreateWorkspace", user="plain", org="acme", id="ws-new")


@pytest.mark.asyncio
async def test_personal_workspaces_on_gives_every_user_a_personal_workspace(world, monkeypatch):
    _settings(monkeypatch, personal_workspaces=True)
    apply_access_settings(world.iam)
    assert await AUTHZ.allowed("CreateWorkspace", user="plain", org=None, id="ws-new")
    # Never an organization, nor a workspace in someone else's organization.
    assert not await AUTHZ.allowed("CreateOrganization", user="plain", id="org-new")
    assert not await AUTHZ.allowed("CreateWorkspace", user="plain", org="acme", id="ws-new")
    # Turned off again at the next start: withdrawn.
    _settings(monkeypatch, personal_workspaces=False)
    apply_access_settings(world.iam)
    assert not await AUTHZ.allowed("CreateWorkspace", user="plain", org=None, id="ws-new")


def test_the_self_grant_is_one_create_on_personal_workspaces():
    assert self_grants(False) == []
    (grant,) = self_grants(True)
    assert (grant.action, grant.resources) == ("nexus:CreateWorkspace", ("abi:nexus:workspace/*",))


# -- model sets ------------------------------------------------------------------------------


def _attach(nexus: NexusIam, policy_ids: list[str], user: str) -> None:
    with as_service_account("api"):
        for policy_id in policy_ids:
            nexus.iam.attach_policy(policy_id, nexus.principal(user), None)


def test_no_level_reaches_a_model_until_its_set_is_attached(world, monkeypatch):
    _settings(monkeypatch, models=model_sets_config(["small"]))
    for user in ("member", "viewer", "owner"):
        assert not _allowed(world, user, "model_registry:Chat", MODEL.format("small"))
        assert not _allowed(world, user, "model_registry:Embed", MODEL.format("embed"))
    with as_service_account("api"):
        policies = model_sets.ensure_model_policies(world.iam, ["small"], ["embed"])
        # Idempotent: found again, kept in step with the configuration.
        again = model_sets.ensure_model_policies(world.iam, ["small", "medium"], ["embed"])
    assert again == policies
    _attach(world, model_sets.level_model_policy_ids(world.iam, "member"), "member")
    _attach(world, model_sets.level_model_policy_ids(world.iam, "viewer"), "viewer")
    _attach(world, model_sets.level_model_policy_ids(world.iam, "admin"), "owner")
    for model in ("small", "medium"):
        assert _allowed(world, "member", "model_registry:Chat", MODEL.format(model))
    # A direct chat outside the member set is refused.
    assert not _allowed(world, "member", "model_registry:Chat", MODEL.format("large"))
    assert not _allowed(world, "member", "model_registry:ChatStream", MODEL.format("large"))
    assert _allowed(world, "owner", "model_registry:Chat", MODEL.format("large"))
    # Viewers chat with no model; everyone embeds (search).
    assert not _allowed(world, "viewer", "model_registry:Chat", MODEL.format("small"))
    for user in ("member", "viewer", "owner"):
        assert _allowed(world, user, "model_registry:Embed", MODEL.format("embed"))
        assert _allowed(world, user, "model_registry:Resolve", MODEL.format("embed"))
    assert not _allowed(world, "viewer", "model_registry:Resolve", MODEL.format("large"))


def model_sets_config(ids: list[str]):
    from naas_abi.apps.nexus.access_config import NexusModelsConfig

    return NexusModelsConfig(member_set=ids)


def test_the_member_set_comes_from_the_configuration(world, monkeypatch):
    _settings(monkeypatch, models=model_sets_config(["configured-model"]))
    apply_access_settings(world.iam)
    _attach(world, model_sets.level_model_policy_ids(world.iam, "member"), "member")
    assert _allowed(world, "member", "model_registry:Chat", MODEL.format("configured-model"))
    assert not _allowed(world, "member", "model_registry:Chat", MODEL.format("other"))


# -- capability groups -----------------------------------------------------------------------


def _workflow(name: str = "nightly") -> str:
    return module_scopes.scope_resource("workflow", "acme.sales", name, container=W)


def test_workflow_runners_is_made_on_demand_and_lets_a_member_run_workflows(world):
    with as_service_account("api"):
        org = make_org(world.iam, "acme", "Acme")
        # Acme offers its module's workflows (the platform's choice).
        world.iam.update_policy(
            org.access_policy_id,
            expected_revision=1,
            document=offer_document(Offer.of(modules=["acme.sales"])),
        )
        assert find_capability(world.iam, "acme", "workflow_runners") is None
    assert not _allowed(world, "member", "module:RunWorkflow", _workflow())
    with as_service_account("api"):
        runners = ensure_capability(
            world.iam, "acme", "workflow_runners", org_access=org.access_policy_id
        )
        assert (
            ensure_capability(
                world.iam, "acme", "workflow_runners", org_access=org.access_policy_id
            )
            == runners
        )
        group = world.iam.get_group(runners.group_id)
        policy = world.iam.get_policy(runners.policy_id)
    assert (group.name, group.owner_scope) == (WORKFLOW_RUNNERS, org_container("acme"))
    assert (policy.owner_scope, policy.parent_id) == (org_container("acme"), org.access_policy_id)
    # Not in the group: refused. In it: allowed, within what the organization offers.
    assert not _allowed(world, "member", "module:RunWorkflow", _workflow())
    with as_service_account("api"):
        world.iam.add_group_member(runners.group_id, world.principal("member"))
    assert _allowed(world, "member", "module:RunWorkflow", _workflow())
    assert _allowed(world, "member", "module:ReadWorkflowRuns", _workflow())
    other = module_scopes.scope_resource("workflow", "new.module", "x", container=W)
    assert not _allowed(world, "member", "module:RunWorkflow", other)


def test_models_all_is_a_group_holding_every_model(world):
    with as_service_account("api"):
        everyone = ensure_capability(world.iam, "acme", "models_all")
        group = world.iam.get_group(everyone.group_id)
    # The platform's: a group an organization owns reaches no platform model.
    assert (group.name, group.owner_scope) == (MODELS_ALL, "abi:")
    assert not _allowed(world, "member", "model_registry:Chat", MODEL.format("large"))
    with as_service_account("api"):
        world.iam.add_group_member(everyone.group_id, world.principal("member"))
    assert _allowed(world, "member", "model_registry:Chat", MODEL.format("large"))
