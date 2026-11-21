"""Platform Files given with the workspace (#1590): a workspace set to Read or Read and
write gives its people Platform Files, in Nexus and in the object storage; joining or
leaving the workspace gives or takes it at the next decision; only the platform admin
changes the setting; the legacy drive flags 0073 kept are converted.

A real IAM (``NexusIam``) with an organization and two workspaces whose defaults are
made as Nexus makes them, memberships given through ``MEMBERSHIPS``. Nothing is mocked."""

from __future__ import annotations

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container
from naas_abi.apps.nexus.apps.api.app.services.iam.platform_files import (
    OFF,
    READ,
    READ_POLICY,
    WRITE,
    WRITE_POLICY,
    DriveFlagChange,
    convert_legacy_drive_flags,
    ensure_policies,
    platform_files_groups,
    set_workspace_platform_files,
    sync_platform_files,
    workspace_platform_files,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import Offer
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ORG = org_container("org-1")
FILE = "abi:nexus:platform_file/platform/shared/notes.md"
OFFER = Offer.of(features=["files", "chat"])
NEXUS = {
    "list": "nexus:ListPlatformFiles",
    "read": "nexus:GetPlatformFile",
    "write": "nexus:PutPlatformFile",
    "delete": "nexus:DeletePlatformFile",
}


@pytest.fixture
def world():
    nexus = NexusIam(features_with_roles=False)
    with nexus.installed():
        nexus.grouped_org("org-1", "Acme")
        alpha = nexus.grouped_workspace("org-1", "ws-1", "Alpha", offer=OFFER)
        beta = nexus.grouped_workspace("org-1", "ws-2", "Beta", offer=OFFER)
        for person in ("member", "viewer", "wadmin", "oadmin", "beta", "late", "stranger"):
            nexus.user(person)
        nexus.platform_admin("root")
        nexus.W = alpha.container  # type: ignore[attr-defined]
        nexus.W2 = beta.container  # type: ignore[attr-defined]
        yield nexus


async def _team(world) -> None:
    await MEMBERSHIPS.grant("oadmin", "admin", ORG)
    await MEMBERSHIPS.grant("member", "member", world.W)
    await MEMBERSHIPS.grant("viewer", "viewer", world.W)
    await MEMBERSHIPS.grant("wadmin", "admin", world.W)
    await MEMBERSHIPS.grant("beta", "member", world.W2)


@pytest_asyncio.fixture
async def team(world):
    await _team(world)
    return world


def _set(world, user: str | None, mode: str, workspace: str = "ws-1") -> str:
    if user is None:
        with as_service_account("api"):
            return set_workspace_platform_files(world.iam, workspace, mode)
    with use_call_context(NexusIam.context(user)):
        return set_workspace_platform_files(world.iam, workspace, mode)


def _can(world, user: str, action: str, resource: str = FILE) -> bool:
    with use_call_context(NexusIam.context(user)):
        return world.iam.authorize(action, resource).allowed


def _uses(world, user: str) -> dict[str, bool]:
    return {op: _can(world, user, action) for op, action in NEXUS.items()}


ALL = {"list": True, "read": True, "write": True, "delete": True}
READ_ONLY = {"list": True, "read": True, "write": False, "delete": False}
NOTHING = {"list": False, "read": False, "write": False, "delete": False}


@pytest.fixture
def storage(world, tmp_path) -> ObjectStorageService:
    storage = ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path / "store")))
    storage.put_object("naas_abi/platform-drive/shared", "notes.md", b"# shared")
    storage.set_services(IEngine.Services(iam=world.iam))
    return storage


def _store_as(storage: ObjectStorageService, user: str) -> dict[str, bool]:
    """What the object storage itself lets ``user`` do in the platform drive."""
    done: dict[str, bool] = {}
    with use_call_context(NexusIam.context(user)):
        for op, call in (
            ("list", lambda: storage.list_objects("naas_abi/platform-drive/shared")),
            ("read", lambda: storage.get_object("naas_abi/platform-drive/shared", "notes.md")),
            ("write", lambda: storage.put_object("naas_abi/platform-drive/shared", "new.md", b"x")),
            ("delete", lambda: storage.delete_object("naas_abi/platform-drive/shared", "new.md")),
        ):
            try:
                listed = call()
                done[op] = op != "list" or bool(listed)
            except (Exceptions.ObjectNotFound, PermissionDeniedError):
                done[op] = False
    return done


# -- the policies -------------------------------------------------------------------------


def test_the_two_policies_are_the_platforms_written_once_with_both_halves(world):
    first = ensure_policies(world.iam)
    assert ensure_policies(world.iam) == first
    with as_service_account("api"):
        policies = {p.name: p for p in world.iam.list_policies(limit=500).items}
    read, write = (
        policies[READ_POLICY].document.to_dict(),
        policies[WRITE_POLICY].document.to_dict(),
    )
    actions = lambda doc: {a for s in doc["statements"] for a in s["actions"]}  # noqa: E731
    resources = lambda doc: {r for s in doc["statements"] for r in s["resources"]}  # noqa: E731
    assert actions(read) == {
        "nexus:ListPlatformFiles",
        "nexus:GetPlatformFile",
        "object_storage:ListObjects",
        "object_storage:ListObjectsRecursive",
        "object_storage:GetObject",
        "object_storage:GetObjectMetadata",
        "object_storage:GetObjectStream",
    }
    assert actions(write) == actions(read) | {
        "nexus:PutPlatformFile",
        "nexus:DeletePlatformFile",
        "object_storage:PutObject",
        "object_storage:PutObjectStream",
        "object_storage:DeleteObject",
    }
    assert (
        resources(read)
        == resources(write)
        == {
            "abi:nexus:platform_file/*",
            "abi:object_storage:object/naas_abi/platform-drive",
            "abi:object_storage:object/naas_abi/platform-drive/*",
        }
    )
    for name in (READ_POLICY, WRITE_POLICY):
        assert policies[name].owner_scope == "abi:"


# -- who may change it ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_workspace_admin_or_an_org_admin_cannot_set_it_a_platform_admin_can(team):
    for user in ("wadmin", "oadmin", "member"):
        for mode in (READ, WRITE, OFF):
            with pytest.raises(PermissionDeniedError):
                _set(team, user, mode)
    assert workspace_platform_files(team.iam, "ws-1") == OFF
    assert platform_files_groups(team.iam) == {}

    assert _set(team, "root", WRITE) == WRITE
    assert workspace_platform_files(team.iam, "ws-1") == WRITE
    with pytest.raises(PermissionDeniedError):
        _set(team, "wadmin", READ)
    assert workspace_platform_files(team.iam, "ws-1") == WRITE

    assert _set(team, "root", READ) == READ
    assert workspace_platform_files(team.iam, "ws-1") == READ
    assert _set(team, "root", OFF) == OFF
    assert workspace_platform_files(team.iam, "ws-1") == OFF
    assert platform_files_groups(team.iam) == {}


def test_an_unknown_mode_or_workspace_is_refused(world):
    with pytest.raises(ValueError):
        _set(world, "root", "everything")
    with pytest.raises(Exception, match="not found"):
        _set(world, "root", WRITE, workspace="ws-404")


# -- what it gives ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_and_write_gives_every_person_of_the_workspace_platform_files(team, storage):
    for user in ("member", "viewer", "wadmin", "beta", "stranger"):
        assert _uses(team, user) == NOTHING, user
        assert _store_as(storage, user) == NOTHING, user

    _set(team, "root", WRITE)

    for user in ("member", "viewer", "wadmin"):
        assert _uses(team, user) == ALL, user
        assert _store_as(storage, user) == ALL, user
    # Another workspace's people, and a stranger, are refused (Nexus and the storage).
    for user in ("beta", "stranger"):
        assert _uses(team, user) == NOTHING, user
        assert _store_as(storage, user) == NOTHING, user


@pytest.mark.asyncio
async def test_read_lists_and_reads_and_writes_nothing(team, storage):
    _set(team, "root", READ)

    assert _uses(team, "member") == READ_ONLY
    assert _store_as(storage, "member") == READ_ONLY


@pytest.mark.asyncio
async def test_it_is_given_by_a_group_and_attached_to_no_person(team):
    _set(team, "root", WRITE)

    (group,) = platform_files_groups(team.iam).values()
    with as_service_account("api"):
        record = team.iam.get_group(group)
        policies = {
            p.id for p in team.iam.list_policies(limit=500).items if "Platform Files" in p.name
        }
        attached = [a for a in team.iam.list_attachments() if a.policy_id in policies]
    assert record.name == "Platform Files · Alpha (ws-1)"
    assert record.owner_scope == "abi:"
    assert {(a.principal_id, a.scope) for a in attached} == {(group, None)}
    with as_service_account("engine"):
        explained = team.iam.explain(NEXUS["write"], FILE, principal_id=team.principal("member"))
    assert explained.statement is not None and explained.statement.via_group == group


@pytest.mark.asyncio
async def test_decided_at_the_platform_whatever_the_workspace(team):
    """Someone who has it through W sees it from another workspace too (#1529)."""
    await MEMBERSHIPS.grant("member", "member", team.W2)
    _set(team, "root", WRITE)
    assert _uses(team, "member") == ALL


# -- membership changes ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_joining_or_leaving_the_workspace_gives_or_takes_it_at_the_next_decision(team):
    _set(team, "root", WRITE)
    assert _uses(team, "late") == NOTHING

    await MEMBERSHIPS.grant("late", "viewer", team.W)
    assert _uses(team, "late") == ALL

    await MEMBERSHIPS.revoke("late", team.W)
    assert _uses(team, "late") == NOTHING

    # A workspace admin leaving keeps nothing either.
    await MEMBERSHIPS.revoke("wadmin", team.W)
    assert _uses(team, "wadmin") == NOTHING


@pytest.mark.asyncio
async def test_a_person_in_two_workspaces_keeps_what_the_other_gives(team):
    _set(team, "root", WRITE)
    _set(team, "root", READ, workspace="ws-2")
    await MEMBERSHIPS.grant("member", "member", team.W2)
    assert _uses(team, "member") == ALL

    await MEMBERSHIPS.revoke("member", team.W)
    assert _uses(team, "member") == READ_ONLY


def _alpha_workspace_group(world) -> str:
    with as_service_account("api"):
        return next(
            str(g.id)
            for g in world.iam.list_groups(limit=500, scope=world.W).items
            if g.membership_of == world.W and g.name == "Alpha workspace"
        )


@pytest.mark.asyncio
async def test_a_member_added_or_removed_on_the_iam_admin_pages_is_followed(team):
    from types import SimpleNamespace

    from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.engine import (
        EngineIamGateway,
    )
    from naas_abi.apps.nexus.apps.api.app.services.iam_admin.runtime import _follow_member
    from naas_abi.apps.nexus.apps.api.app.services.iam_admin.service import IamAdminService
    from naas_abi.apps.nexus.apps.api.app.services.iam_admin.testing import MemoryAudit

    _set(team, "root", WRITE)
    await MEMBERSHIPS.grant("late", "member", team.W2)  # of the organization already
    admin = IamAdminService(EngineIamGateway(), MemoryAudit(), follow_member=_follow_member)
    root = SimpleNamespace(id="root")
    group, late = _alpha_workspace_group(team), team.principal("late")

    await admin.add_member(root, group, late)
    assert _uses(team, "late") == ALL
    await admin.remove_member(root, group, late)
    assert _uses(team, "late") == NOTHING


@pytest.mark.asyncio
async def test_the_start_puts_back_in_step_a_membership_made_around_nexus(team):
    _set(team, "root", WRITE)
    late, alpha = team.principal("late"), _alpha_workspace_group(team)
    with as_service_account("api"):
        team.iam.add_group_member(alpha, late)  # straight into IAM: nobody followed
    assert _uses(team, "late") == NOTHING

    assert sync_platform_files(team.iam) == (1, 0)
    assert _uses(team, "late") == ALL
    assert sync_platform_files(team.iam) == (0, 0)


@pytest.mark.asyncio
async def test_a_deleted_workspace_takes_its_platform_files_with_it(team):
    _set(team, "root", WRITE)
    await MEMBERSHIPS.drop_scope("org-1", "ws-1")

    assert platform_files_groups(team.iam) == {}
    assert _uses(team, "member") == NOTHING


# -- the legacy drive flags ------------------------------------------------------------------


@pytest_asyncio.fixture
async def legacy_db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.sqlite'}")
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE workspace_drive_flags_legacy (workspace_id VARCHAR(255) PRIMARY "
                "KEY, platform_drive_enabled BOOLEAN NOT NULL DEFAULT FALSE, "
                "system_drive_enabled BOOLEAN NOT NULL DEFAULT FALSE)"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO workspace_drive_flags_legacy VALUES "
                "('ws-1', TRUE, TRUE), ('ws-2', FALSE, TRUE), ('ws-gone', TRUE, FALSE)"
            )
        )
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _tables(sessions) -> set[str]:
    async with sessions() as db:
        rows = await db.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'"))
        return {row[0] for row in rows}


@pytest.mark.asyncio
async def test_the_flags_kept_by_0073_become_the_setting_once(team, legacy_db):
    async with legacy_db() as db:
        report = await convert_legacy_drive_flags(team.iam, db)

    assert [(c.workspace_id, c.flag, c.action) for c in report] == [
        ("ws-1", "platform", "converted"),
        ("ws-1", "system", "reported"),
        ("ws-2", "system", "reported"),
        ("ws-gone", "platform", "none"),
    ]
    assert all(isinstance(c, DriveFlagChange) and c.detail for c in report)
    assert workspace_platform_files(team.iam, "ws-1") == WRITE
    assert workspace_platform_files(team.iam, "ws-2") == OFF
    for user in ("member", "viewer", "wadmin"):
        assert _uses(team, user) == ALL, user
    assert _uses(team, "beta") == NOTHING
    assert "workspace_drive_flags_legacy" not in await _tables(legacy_db)

    # Idempotent: the table is gone, nothing more to convert.
    async with legacy_db() as db:
        assert await convert_legacy_drive_flags(team.iam, db) == []


@pytest.mark.asyncio
async def test_a_converted_workspaces_people_use_platform_files_through_the_files_routes(
    team, legacy_db, storage
):
    """The Nexus files routes over the object storage, which decides its own half: a
    member of the flagged workspace lists, reads, writes and deletes; a member of a
    workspace whose flag was System Files alone is refused."""
    from naas_abi.apps.nexus.apps.api.app.services.files import placement
    from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__iam_test import (  # noqa: E501
        _client_factory,
    )

    placement._PLACED.clear()
    async with legacy_db() as db:
        await convert_legacy_drive_flags(team.iam, db)
    client = _client_factory(storage)
    platform = {"scope": "platform_drive"}
    body = {"path": "shared/new.md", "content": "x", "scope": "platform_drive"}

    async with client("member") as http:
        listing = await http.get("/api/files/", params={**platform, "path": "shared"})
        assert listing.status_code == 200
        assert "notes.md" in {f["name"] for f in listing.json()["files"]}
        read = await http.get("/api/files/shared/notes.md", params=platform)
        assert read.json()["content"] == "# shared"
        assert (await http.post("/api/files/", json=body)).status_code == 200
        assert (await http.delete("/api/files/shared/new.md", params=platform)).status_code == 200

    async with client("beta") as http:
        assert (await http.get("/api/files/", params=platform)).status_code == 403
        assert (await http.get("/api/files/shared/notes.md", params=platform)).status_code == 403
        assert (await http.post("/api/files/", json=body)).status_code == 403


@pytest.mark.asyncio
async def test_a_dry_run_reports_and_changes_nothing(team, legacy_db):
    async with legacy_db() as db:
        report = await convert_legacy_drive_flags(team.iam, db, apply=False)

    assert ("ws-1", "platform", "converted") in [(c.workspace_id, c.flag, c.action) for c in report]
    assert workspace_platform_files(team.iam, "ws-1") == OFF
    assert "workspace_drive_flags_legacy" in await _tables(legacy_db)


@pytest.mark.asyncio
async def test_nothing_kept_means_nothing_to_convert(team, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'empty.sqlite'}")
    try:
        async with async_sessionmaker(engine)() as db:
            assert await convert_legacy_drive_flags(team.iam, db) == []
    finally:
        await engine.dispose()
