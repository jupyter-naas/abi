"""A workspace owns exactly its drive, and the kernel holds everyone to it."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.files import placement
from naas_abi.apps.nexus.apps.api.app.services.iam import placements
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi_core.engine.call_context import use_call_context
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService


@pytest.fixture(autouse=True)
def _forget_placed_workspaces():
    """Each test has its own IAM: nothing is placed in it yet."""
    placement._PLACED.clear()
    yield
    placement._PLACED.clear()


def keys(workspace_id: str) -> list[str]:
    return [p.id_key() for p in placement.workspace_drive_placements(workspace_id)]


def test_a_workspace_places_its_drive_folder_and_everything_below() -> None:
    assert keys("ws-1") == [
        "naas_abi/workspace-drive/ws-1",
        "naas_abi/workspace-drive/ws-1/*",
    ]


@pytest.mark.parametrize("workspace_id", ["", ".", "..", "a/b", "../ws-2"])
def test_an_id_that_is_not_one_plain_segment_places_nothing(workspace_id: str) -> None:
    with pytest.raises(ValueError):
        placement.workspace_drive_placements(workspace_id)


class FakeDb:
    def __init__(self, ids: list[str]) -> None:
        self.ids = ids

    async def execute(self, _query):
        return [(workspace_id,) for workspace_id in self.ids]


@pytest.mark.asyncio
async def test_existing_workspaces_come_from_the_workspaces_table() -> None:
    assert placement.workspace_drives in placements.SOURCES
    found = list(await placement.workspace_drives(FakeDb(["ws-1", "a/b", "ws-2"])))
    # "a/b" is no workspace id: it is left out, the others are placed.
    assert [p.workspace for p in found] == ["ws-1", "ws-1", "ws-2", "ws-2"]


@pytest.mark.asyncio
async def test_a_placed_drive_covers_exactly_the_drive(team) -> None:
    await placement.place_workspace_drive("ws-1")

    def workspace_of(object_id: str) -> str | None:
        found = team.iam.placement_of("object_storage", object_id)
        return found.workspace if found else None

    assert workspace_of("naas_abi/workspace-drive/ws-1") == "ws-1"
    assert workspace_of("naas_abi/workspace-drive/ws-1/docs/a.txt") == "ws-1"
    # Neither a longer id, a sibling, nor another tree is inside it.
    for outside in (
        "naas_abi/workspace-drive/ws-10/a.txt",
        "naas_abi/workspace-drive/ws-1-2/a.txt",
        "naas_abi/workspace-drive/ws-1%2F..%2Fws-2/a.txt",
        "naas_abi/workspace-drive",
        "naas_abi/platform-drive/a.txt",
        "naas_abi/my-drive/member/a.txt",
        "naas_abi/.scaffolded/staff-folders/ws-1",
        "users/member/a.txt",
        "ws-1/a.txt",
    ):
        assert workspace_of(outside) is None, outside
    await placement.ensure_workspace_drive_placed("ws-1")  # already placed: nothing to do


def test_placing_from_a_commit_hook_waits_for_iam_to_know_the_workspace(nexus_iam) -> None:
    assert placement.place_workspace_drive_sync("ws-new") is False  # unknown to IAM yet
    nexus_iam.workspace("org-1", "ws-new")
    assert placement.place_workspace_drive_sync("ws-new") is True
    found = nexus_iam.iam.placement_of("object_storage", "naas_abi/workspace-drive/ws-new/a")
    assert (found.org, found.workspace) == ("org-1", "ws-new")


@pytest.fixture
def kernel(tmp_path, nexus_iam: NexusIam):
    """The real object storage, wired to the IAM that holds the workspaces."""
    nexus_iam.workspace("org-1", "ws-1")
    nexus_iam.workspace("org-1", "ws-2")
    nexus_iam.grant("owner", "owner", "abi:org-1:ws-1")
    nexus_iam.grant("viewer", "viewer", "abi:org-1:ws-1")
    nexus_iam.grant("other", "member", "abi:org-1:ws-2")
    storage = ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path)))
    storage.set_services(IEngine.Services(iam=nexus_iam.iam))
    return storage


def acting(user: str):
    return use_call_context(NexusIam.context(user))


@pytest.mark.asyncio
async def test_the_kernel_reaches_a_workspaces_roles_to_its_drive_only(kernel, nexus_iam) -> None:
    drive = "naas_abi/workspace-drive"
    with acting("owner"):
        # Nobody placed the drive yet: it belongs to the platform.
        with pytest.raises(Exceptions.ObjectNotFound):
            kernel.put_object(f"{drive}/ws-1", "a.txt", b"one")

    await placement.place_workspace_drive("ws-1")
    await placement.place_workspace_drive("ws-2")

    with acting("owner"):
        kernel.put_object(f"{drive}/ws-1", "a.txt", b"one")
        kernel.put_object(f"{drive}/ws-1/docs", "b.txt", b"two")
        assert kernel.get_object(f"{drive}/ws-1", "a.txt") == b"one"
        assert "naas_abi/workspace-drive/ws-1/a.txt" in kernel.list_objects(f"{drive}/ws-1")
        # The other workspace's drive is not its owner's, nor is a path that
        # climbs out of this one.
        with pytest.raises(Exceptions.ObjectNotFound):
            kernel.get_object(f"{drive}/ws-2", "a.txt")
        with pytest.raises(Exceptions.InvalidObjectPath):
            kernel.get_object(f"{drive}/ws-1", "../ws-2/a.txt")
        with pytest.raises(Exceptions.InvalidObjectPath):
            kernel.get_object(f"{drive}/ws-1/../ws-2", "a.txt")
        with pytest.raises(Exceptions.ObjectNotFound):
            kernel.put_object(f"{drive}/ws-1-2", "a.txt", b"x")

    with acting("viewer"):
        assert kernel.get_object(f"{drive}/ws-1", "a.txt") == b"one"
        with pytest.raises(PermissionDeniedError):
            kernel.put_object(f"{drive}/ws-1", "c.txt", b"x")
        with pytest.raises(PermissionDeniedError):
            kernel.delete_object(f"{drive}/ws-1", "a.txt")

    with acting("other"):
        with pytest.raises(Exceptions.ObjectNotFound):
            kernel.get_object(f"{drive}/ws-1", "a.txt")
        kernel.put_object(f"{drive}/ws-2", "own.txt", b"mine")
