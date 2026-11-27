"""The files a workspace gives outside it (ADR ``20261125_offer_gives_outside_resources``):
Organization, Platform and System Files are given sections of "<W> access". Its people
reach them, in Nexus and in the object storage, within their level there, while they
belong to W; whoever holds a section gives it, a workspace's admin only narrows it.

A real IAM (``NexusIam``) with an organization and two workspaces made as Nexus makes
them, memberships given through ``MEMBERSHIPS``, the offer written through the offer
service as the caller, and an object storage that asks IAM. Nothing is mocked."""

from __future__ import annotations

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.services.feature_access.service import (
    FeatureAccessService,
)
from naas_abi.apps.nexus.apps.api.app.services.files import placement
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import CONTAINER_DEFAULTS
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import nexus_resource, org_container
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import Offer, offer_of
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.engine import (
    EngineIamGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.testing import MemoryAudit
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError, PermissionDeniedError
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

ORG = org_container("org-1")
OFFER = Offer.of(features=["files", "chat"])
PLATFORM_DRIVE = "naas_abi/platform-drive/shared"
ORG_DRIVE = "naas_abi/organization-drive/org-1"
BETA_DRIVE = "naas_abi/workspace-drive/ws-2"

# Each view's Nexus actions, on one of its files.
VIEWS = {
    "platform": (
        "abi:nexus:platform_file/platform/shared/notes.md",
        ("ListPlatformFiles", "GetPlatformFile", "PutPlatformFile", "DeletePlatformFile"),
    ),
    "org": (
        nexus_resource("file", container=ORG, id=("organization", "policy.md")),
        ("ListOrgFiles", "GetOrgFile", "PutOrgFile", "DeleteOrgFile"),
    ),
    "system": (
        "abi:nexus:system_file/system/naas_abi/workspace-drive/ws-2/secret.md",
        (
            "ListObjectStoreFiles",
            "GetObjectStoreFile",
            "PutObjectStoreFile",
            "DeleteObjectStoreFile",
        ),
    ),
}
ALL = {"list": True, "read": True, "write": True, "delete": True}
READ_ONLY = {"list": True, "read": True, "write": False, "delete": False}
NOTHING = {"list": False, "read": False, "write": False, "delete": False}


class _NoStore:
    async def managed_among(self, policy_ids):  # noqa: ANN001 - unused here
        return {}


@pytest.fixture
def world():
    nexus = NexusIam(features_with_roles=False)
    with nexus.installed():
        nexus.grouped_org("org-1", "Acme")
        alpha = nexus.grouped_workspace("org-1", "ws-1", "Alpha", offer=OFFER)
        beta = nexus.grouped_workspace("org-1", "ws-2", "Beta", offer=OFFER)
        solo = nexus.grouped_workspace(None, "ws-solo", "Solo", offer=OFFER)
        for person in ("member", "viewer", "wadmin", "oadmin", "beta", "late", "stranger"):
            nexus.user(person)
        nexus.platform_admin("root")
        nexus.W = alpha.container  # type: ignore[attr-defined]
        nexus.alpha = alpha  # type: ignore[attr-defined]
        nexus.W2 = beta.container  # type: ignore[attr-defined]
        nexus.SOLO = solo.container  # type: ignore[attr-defined]
        placement._PLACED.clear()
        placement._PLACED_ORGS.clear()
        placement.place_organization_drive_sync("org-1")
        placement.place_workspace_drive_sync("ws-2")
        yield nexus
    CONTAINER_DEFAULTS.forget_grouped()


@pytest_asyncio.fixture
async def team(world):
    await MEMBERSHIPS.grant("oadmin", "admin", ORG)
    await MEMBERSHIPS.grant("member", "member", world.W)
    await MEMBERSHIPS.grant("viewer", "viewer", world.W)
    await MEMBERSHIPS.grant("wadmin", "admin", world.W)
    await MEMBERSHIPS.grant("beta", "member", world.W2)
    return world


@pytest.fixture
def offers() -> FeatureAccessService:
    return FeatureAccessService(
        EngineIamGateway(),
        _NoStore(),  # type: ignore[arg-type]
        MemoryAudit(),
        container_of=AUTHZ.container_of,
        defaults_of=CONTAINER_DEFAULTS.record_of,
        features=lambda: ["files", "chat"],
    )


@pytest.fixture
def storage(world, tmp_path) -> ObjectStorageService:
    storage = ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path / "store")))
    storage.put_object(PLATFORM_DRIVE, "notes.md", b"# shared")
    storage.put_object(ORG_DRIVE, "policy.md", b"# policy")
    storage.put_object(BETA_DRIVE, "secret.md", b"# beta")
    storage.set_services(IEngine.Services(iam=world.iam))
    return storage


def _uses(world, user: str, view: str) -> dict[str, bool]:
    resource, actions = VIEWS[view]
    with use_call_context(NexusIam.context(user)):
        return {
            op: world.iam.authorize(f"nexus:{action}", resource).allowed
            for op, action in zip(("list", "read", "write", "delete"), actions, strict=True)
        }


def _stores(storage: ObjectStorageService, user: str, folder: str, name: str) -> dict[str, bool]:
    """What the object storage itself lets ``user`` do in ``folder``."""
    done: dict[str, bool] = {}
    with use_call_context(NexusIam.context(user)):
        for op, call in (
            ("list", lambda: storage.list_objects(folder)),
            ("read", lambda: storage.get_object(folder, name)),
            ("write", lambda: storage.put_object(folder, "new.md", b"x")),
            ("delete", lambda: storage.delete_object(folder, "new.md")),
        ):
            try:
                listed = call()
                done[op] = op != "list" or bool(listed)
            except (Exceptions.ObjectNotFound, PermissionDeniedError):
                done[op] = False
    return done


async def _give(offers, user: str, workspace: str = "ws-1", **changes: str) -> dict:
    return await offers.set_files(user, workspace, changes)


def _rows(state: dict) -> dict[str, dict]:
    return {row["key"]: row for row in state["files"]}


# -- Platform Files ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_platform_files_reach_the_workspaces_people_within_their_level(team, offers, storage):
    assert _uses(team, "member", "platform") == NOTHING
    await _give(offers, "root", platform_files="write")
    assert _uses(team, "member", "platform") == ALL
    assert _uses(team, "wadmin", "platform") == ALL
    # Read and write lets a Viewer read, not write.
    assert _uses(team, "viewer", "platform") == READ_ONLY
    for user in ("stranger", "beta", "oadmin"):
        assert _uses(team, user, "platform") == NOTHING, user
    # Both halves: the object storage decides the same.
    assert _stores(storage, "member", PLATFORM_DRIVE, "notes.md") == ALL
    assert _stores(storage, "viewer", PLATFORM_DRIVE, "notes.md") == READ_ONLY
    assert _stores(storage, "stranger", PLATFORM_DRIVE, "notes.md") == NOTHING

    await _give(offers, "root", platform_files="read")
    assert _uses(team, "member", "platform") == READ_ONLY
    assert _stores(storage, "member", PLATFORM_DRIVE, "notes.md") == READ_ONLY
    await _give(offers, "root", platform_files="off")
    assert _uses(team, "member", "platform") == NOTHING


@pytest.mark.asyncio
async def test_joining_or_leaving_the_workspace_gives_or_takes_it_at_the_next_decision(
    team, offers
):
    await _give(offers, "root", platform_files="write")
    assert _uses(team, "late", "platform") == NOTHING
    await MEMBERSHIPS.grant("late", "member", team.W)
    assert _uses(team, "late", "platform") == ALL
    await MEMBERSHIPS.revoke("late", team.W)
    assert _uses(team, "late", "platform") == NOTHING
    await MEMBERSHIPS.revoke("wadmin", team.W)
    assert _uses(team, "wadmin", "platform") == NOTHING


@pytest.mark.asyncio
async def test_a_person_in_two_workspaces_keeps_what_the_other_gives(team, offers):
    await _give(offers, "root", platform_files="write")
    await _give(offers, "root", "ws-2", platform_files="read")
    await MEMBERSHIPS.grant("member", "member", team.W2)
    assert _uses(team, "member", "platform") == ALL
    await MEMBERSHIPS.revoke("member", team.W)
    assert _uses(team, "member", "platform") == READ_ONLY


@pytest.mark.asyncio
async def test_only_the_platform_admin_gives_platform_or_system_files(team, offers):
    for user in ("wadmin", "oadmin"):
        state = await offers.read_offer(user, "ws-1")
        for key in ("platform_files", "system_files"):
            row = _rows(state)[key]
            assert row["mode"] == "off" and not row["editable"], (user, key)
            assert row["choices"] == ["off"] and "platform admin" in row["reason"]
        with pytest.raises(PermissionDeniedError):
            await _give(offers, user, platform_files="read")
        with pytest.raises(PermissionDeniedError):
            await _give(offers, user, system_files="read")
    # A member may not even read "<W> access": not found.
    with pytest.raises((PermissionDeniedError, IAMNotFoundError)):
        await _give(offers, "member", platform_files="read")
    root = _rows(await offers.read_offer("root", "ws-1"))
    assert root["platform_files"]["editable"] and root["platform_files"]["choices"] == [
        "off",
        "read",
        "write",
    ]
    assert root["system_files"]["choices"] == ["off", "read"]
    state = await _give(offers, "root", platform_files="write", system_files="read")
    assert _rows(state)["platform_files"]["mode"] == "write"
    assert _rows(state)["system_files"]["mode"] == "read"


@pytest.mark.asyncio
async def test_a_workspace_admin_narrows_or_removes_what_is_given_never_widens_it(team, offers):
    await _give(offers, "root", platform_files="write")
    row = _rows(await offers.read_offer("wadmin", "ws-1"))["platform_files"]
    assert row["editable"] and row["choices"] == ["off", "read", "write"]
    await _give(offers, "wadmin", platform_files="read")
    row = _rows(await offers.read_offer("wadmin", "ws-1"))["platform_files"]
    assert row["mode"] == "read" and row["choices"] == ["off", "read"]
    with pytest.raises(PermissionDeniedError):
        await _give(offers, "wadmin", platform_files="write")
    await _give(offers, "wadmin", platform_files="off")
    assert _uses(team, "member", "platform") == NOTHING


@pytest.mark.asyncio
async def test_what_was_given_is_never_given_again(team, offers):
    """A member of W given Platform Files holds none of it: as an admin of another
    workspace they cannot give it there."""
    await _give(offers, "root", platform_files="write")
    await MEMBERSHIPS.grant("wadmin", "admin", team.W2)
    with pytest.raises(PermissionDeniedError):
        await _give(offers, "wadmin", "ws-2", platform_files="read")
    assert not _rows(await offers.read_offer("wadmin", "ws-2"))["platform_files"]["editable"]


# -- Organization Files ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_organization_files_are_given_by_the_organizations_admins(team, offers, storage):
    """A workspace's people hold no role at the organization: the offer gives them its
    Organization Files, in Nexus and in the object storage, within their level."""
    assert _uses(team, "member", "org") == NOTHING
    row = _rows(await offers.read_offer("oadmin", "ws-1"))["org_files"]
    assert row["editable"] and row["choices"] == ["off", "read", "write"]
    assert not _rows(await offers.read_offer("wadmin", "ws-1"))["org_files"]["editable"]
    with pytest.raises(PermissionDeniedError):
        await _give(offers, "wadmin", org_files="read")

    state = await _give(offers, "oadmin", org_files="write")
    assert _rows(state)["org_files"]["mode"] == "write"
    assert _uses(team, "member", "org") == ALL
    assert _uses(team, "viewer", "org") == READ_ONLY
    assert _uses(team, "beta", "org") == NOTHING
    assert _stores(storage, "member", ORG_DRIVE, "policy.md") == ALL
    assert _stores(storage, "viewer", ORG_DRIVE, "policy.md") == READ_ONLY
    assert _stores(storage, "beta", ORG_DRIVE, "policy.md") == NOTHING
    with as_service_account("api"):
        access = team.iam.get_policy(team.alpha.access_policy_id)
    assert offer_of(access.document).features == {"files", "chat"}


@pytest.mark.asyncio
async def test_a_workspace_in_no_organization_has_no_organization_files(team, offers):
    state = await offers.read_offer("root", "ws-solo")
    assert "org_files" not in _rows(state)
    with pytest.raises(ValueError, match="no organization"):
        await _give(offers, "root", "ws-solo", org_files="read")


# -- System Files ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_files_are_read_only_and_read_every_key(team, offers, storage):
    """System Files reads every key of the object storage, another workspace's drive
    included, and never writes."""
    assert _uses(team, "member", "system") == NOTHING
    assert _stores(storage, "member", BETA_DRIVE, "secret.md") == NOTHING
    await _give(offers, "root", system_files="read")
    assert _uses(team, "member", "system") == READ_ONLY
    assert _uses(team, "viewer", "system") == READ_ONLY
    assert _stores(storage, "member", BETA_DRIVE, "secret.md") == READ_ONLY
    assert _stores(storage, "member", PLATFORM_DRIVE, "notes.md") == READ_ONLY
    assert _uses(team, "stranger", "system") == NOTHING
    with pytest.raises(ValueError, match="System Files"):
        await _give(offers, "root", system_files="write")


@pytest.mark.asyncio
async def test_the_offer_says_what_my_files_is(team, offers):
    state = await offers.read_offer("wadmin", "ws-1")
    assert state["my_files"] == {"members": "write", "viewers": "read"}
    team.flags.viewer_my_files = False
    assert (await offers.read_offer("wadmin", "ws-1"))["my_files"]["viewers"] == "none"
