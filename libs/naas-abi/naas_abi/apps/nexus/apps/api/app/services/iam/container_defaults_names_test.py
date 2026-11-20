"""The access policy and default groups of an organization or a workspace carry its
name: a rename renames them, the start repairs what an older rename left, and a name
a person chose stays (``container_defaults.align_names``)."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.models import WorkspaceModel
from naas_abi.apps.nexus.apps.api.app.services.iam import container_defaults
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
    DefaultsRecord,
    access_description,
    access_template,
    labels_in,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults_test import (  # noqa: F401
    ALPHA,
    _acme,
    _fresh_defaults,
    _members,
    _moves_recorded,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (  # noqa: E501
    OrganizationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationUpdateInput,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import OrganizationService
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (  # noqa: E501
    WorkspaceSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceUpdateInput
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import WorkspaceService
from naas_abi_core.engine.call_context import as_service_account
from sqlalchemy import update

ACME = org_container("acme")


@pytest.fixture
def world():
    nexus = NexusIam(features_with_roles=False)
    with nexus.installed():
        yield nexus


def _names(world, record: DefaultsRecord) -> tuple[str, str, str, str]:
    """The access policy's name and description, then the members' and admins' names."""
    with as_service_account("api"):
        policy = world.iam.get_policy(record.access_policy_id)
        members = world.iam.get_group(record.members_group_id)
        admins = world.iam.get_group(record.admins_group_id)
    return policy.name, policy.description, members.name, admins.name


def _made(container: str, label: str) -> tuple[str, str, str, str]:
    return (
        f"{label} access",
        access_description(container, label),
        f"{label} members",
        f"{label} admins",
    )


def test_a_description_as_made_gives_back_its_labels():
    template = access_template(ALPHA)
    assert template is not None
    assert labels_in(template, access_description(ALPHA, "Alpha")) == ("Alpha", "Alpha")
    assert labels_in(template, "Ours, written by hand") is None
    org = access_template(ACME)
    assert org is not None and "(acme)" in org
    assert labels_in(org, access_description(ACME, "A (b) c")) == ("A (b) c", "A (b) c")
    assert access_template("abi:") is None


@pytest.mark.asyncio
async def test_renaming_a_workspace_and_its_organization_renames_their_access_and_groups(
    world, nexus_db
):
    _org, _ws, org_record, ws_record = await _acme(nexus_db)
    assert _names(world, ws_record) == _made(ALPHA, "Alpha")
    async with nexus_db() as db:
        workspaces = WorkspaceService(adapter=WorkspaceSecondaryAdapterPostgres(db=db))
        await workspaces.update_workspace("alpha", WorkspaceUpdateInput(name="Apex"))
        orgs = OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))
        await orgs.update_organization("acme", OrganizationUpdateInput(name="Acme Corp"))
        # Another field alone renames nothing.
        await workspaces.update_workspace("alpha", WorkspaceUpdateInput(primary_color="#000"))
        await db.commit()
    assert _names(world, ws_record) == _made(ALPHA, "Apex")
    assert _names(world, org_record) == _made(ACME, "Acme Corp")
    # The same groups, with the same people.
    assert _members(world, ws_record.members_group_id) == {"olivia"}
    assert _members(world, org_record.admins_group_id) == {"olivia"}


@pytest.mark.asyncio
async def test_a_name_a_person_chose_stays(world, nexus_db):
    _org, _ws, _org_record, ws_record = await _acme(nexus_db)
    with as_service_account("api"):
        world.iam.update_group(ws_record.members_group_id, name="Analysts")
        policy = world.iam.get_policy(ws_record.access_policy_id)
        world.iam.update_policy(
            policy.id, expected_revision=policy.revision, description="Ours, written by hand"
        )
    async with nexus_db() as db:
        workspaces = WorkspaceService(adapter=WorkspaceSecondaryAdapterPostgres(db=db))
        await workspaces.update_workspace("alpha", WorkspaceUpdateInput(name="Apex"))
        await db.commit()
    assert _names(world, ws_record) == (
        "Apex access",
        "Ours, written by hand",
        "Analysts",
        "Apex admins",
    )


@pytest.mark.asyncio
async def test_the_start_names_them_after_a_rename_made_before(world, nexus_db):
    """As a workspace renamed before names followed, whose access policy someone
    renamed by hand, its description half edited: the groups and what is left of the
    description follow; the start after changes nothing."""
    _org, _ws, _org_record, ws_record = await _acme(nexus_db)
    half_edited = access_description(ALPHA, "Alpha").replace("workspace Alpha", "workspace Apex")
    with as_service_account("api"):
        policy = world.iam.get_policy(ws_record.access_policy_id)
        world.iam.update_policy(
            policy.id,
            expected_revision=policy.revision,
            name="Apex access",
            description=half_edited,
        )
    async with nexus_db() as db:
        await db.execute(
            update(WorkspaceModel).where(WorkspaceModel.id == "alpha").values(name="Apex")
        )
        await db.commit()
    await _moves_recorded(nexus_db, *container_defaults.MOVES)

    async with nexus_db() as db:
        await container_defaults.migrate(db)
    assert _names(world, ws_record) == _made(ALPHA, "Apex")
    # The organization, never renamed, keeps its names.
    with as_service_account("api"):
        assert world.iam.get_policy(_org_record.access_policy_id).name == "Acme access"

    with as_service_account("api"):
        records = {ws_record.container: ws_record}
        assert (
            container_defaults.align_all(world.iam, {}, {"alpha": ("acme", "Apex")}, records) == []
        )


@pytest.mark.asyncio
async def test_the_start_leaves_groups_it_cannot_tell_were_made(world, nexus_db):
    """With the description rewritten, nothing says which label the groups were made
    from: a group that does not carry the workspace's name stays as it is."""
    _org, _ws, _org_record, ws_record = await _acme(nexus_db)
    with as_service_account("api"):
        policy = world.iam.get_policy(ws_record.access_policy_id)
        world.iam.update_policy(
            policy.id, expected_revision=policy.revision, description="Ours, written by hand"
        )
        records = {ws_record.container: ws_record}
        assert (
            container_defaults.align_all(world.iam, {}, {"alpha": ("acme", "Apex")}, records) == []
        )
    assert _names(world, ws_record)[2:] == ("Alpha members", "Alpha admins")
