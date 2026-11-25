"""Platform Files moves into the offer (``files_offer_v1``): each "Platform Files · <W>"
group an earlier version kept becomes ``GivenPlatformFiles`` in "<W> access", in the
mode it held; the groups and the two platform policies go. And the legacy drive flags
0073 kept are converted into the offer.

A real IAM (``NexusIam``) with the groups and policies as #1590 wrote them, the
workspaces made as Nexus makes them and a SQLite database. Nothing is mocked."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app import models  # noqa: F401 - its tables in nexus_db
from naas_abi.apps.nexus.apps.api.app.services.iam import files_offer, given_files
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
    CONTAINER_DEFAULTS,
    SqlDefaultsStore,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import Offer, offer_of
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from sqlalchemy import inspect, text

OFFER = Offer.of(features=["files", "chat"])
FILE = "abi:nexus:platform_file/platform/shared/notes.md"
NEXUS = ("ListPlatformFiles", "GetPlatformFile", "PutPlatformFile", "DeletePlatformFile")
ALL = [True, True, True, True]
READ_ONLY = [True, True, False, False]
NOTHING = [False, False, False, False]


@pytest.fixture
def world():
    nexus = NexusIam(features_with_roles=False)
    with nexus.installed():
        nexus.grouped_org("org-1", "Acme")
        nexus.alpha = nexus.grouped_workspace("org-1", "ws-1", "Alpha", offer=OFFER)  # type: ignore[attr-defined]
        nexus.beta = nexus.grouped_workspace("org-1", "ws-2", "Beta", offer=OFFER)  # type: ignore[attr-defined]
        for person in ("member", "viewer", "beta", "kept"):
            nexus.user(person)
        yield nexus
    CONTAINER_DEFAULTS.forget_grouped()


@pytest_asyncio.fixture
async def legacy(world):
    """The people, then what #1590 wrote: the two policies, a group per workspace that
    gave Platform Files (one of a workspace since deleted), its members W's people."""
    await MEMBERSHIPS.grant("member", "member", world.alpha.container)
    await MEMBERSHIPS.grant("viewer", "viewer", world.alpha.container)
    await MEMBERSHIPS.grant("beta", "member", world.beta.container)
    with as_service_account("api"):
        policies = {
            mode: world.iam.create_policy(
                name,
                {
                    "version": "2026-10-13",
                    "statements": given_files.statements(given_files.PLATFORM_FILES, mode),
                },
            ).id
            for mode, name in (
                ("read", files_offer.READ_POLICY),
                ("write", files_offer.WRITE_POLICY),
            )
        }
        for name, mode, people in (
            ("Platform Files · Alpha (ws-1)", "write", ("member", "viewer")),
            ("Platform Files · Beta (ws-2)", "read", ("beta",)),
            ("Platform Files · (ws-gone)", "read", ()),
        ):
            group = world.iam.create_group(name)
            world.iam.attach_policy(policies[mode], group.id)
            for person in people:
                world.iam.add_group_member(group.id, world.principal(person))
    world.legacy_policies = policies  # type: ignore[attr-defined]
    return world


def _policies(world) -> dict[str, str]:
    return {r.container: r.access_policy_id for r in (world.alpha, world.beta)}


def _uses(world, user: str) -> list[bool]:
    with use_call_context(NexusIam.context(user)):
        return [world.iam.authorize(f"nexus:{a}", FILE).allowed for a in NEXUS]


def _given(world, record) -> str | None:
    with as_service_account("api"):
        return offer_of(world.iam.get_policy(record.access_policy_id).document).platform_files


def _left(world) -> list[str]:
    with as_service_account("api"):
        groups = [g.name for g in world.iam.list_groups(limit=500).items if g.status != "deleted"]
        policies = [p.name for p in world.iam.list_policies(limit=500).items]
    return [n for n in [*groups, *policies] if n.startswith(files_offer.GROUP_PREFIX)]


@pytest.mark.asyncio
async def test_each_group_becomes_its_workspaces_given_section_and_goes(legacy):
    assert _uses(legacy, "viewer") == ALL  # what the group gave, uncapped
    report = files_offer.apply(legacy.iam, _policies(legacy))
    assert report.to_dict() == {
        "written": {"ws-1": "write", "ws-2": "read"},
        "kept": 0,
        "gone": ["ws-gone"],
        "groups_deleted": 3,
        "policies_deleted": 2,
        "policies_kept": {},
        "failed": {},
    }
    assert _given(legacy, legacy.alpha) == "write" and _given(legacy, legacy.beta) == "read"
    assert _left(legacy) == []
    # The offer gives it now, within each person's level.
    assert _uses(legacy, "member") == ALL
    assert _uses(legacy, "viewer") == READ_ONLY
    assert _uses(legacy, "beta") == READ_ONLY
    # The other sections are kept.
    with as_service_account("api"):
        access = legacy.iam.get_policy(legacy.alpha.access_policy_id)
    assert offer_of(access.document).features == {"files", "chat"}
    again = files_offer.apply(legacy.iam, _policies(legacy))
    assert not again.written and not again.groups_deleted and not again.policies_deleted


@pytest.mark.asyncio
async def test_a_policy_someone_else_holds_is_kept_and_named(legacy):
    with as_service_account("api"):
        legacy.iam.attach_policy(legacy.legacy_policies["read"], legacy.principal("kept"))
    report = files_offer.apply(legacy.iam, _policies(legacy))
    assert report.policies_kept == {files_offer.READ_POLICY: 1}
    assert report.policies_deleted == 1 and not report.failed
    assert _left(legacy) == [files_offer.READ_POLICY]


@pytest.mark.asyncio
async def test_the_move_runs_once_and_is_recorded(legacy, nexus_db):
    async with nexus_db() as db:
        store = SqlDefaultsStore(db)
        for record in (legacy.alpha, legacy.beta):
            await store.put(record)
        await db.commit()
        report = await files_offer.migrate(db, legacy.iam)
        assert report is not None and report.written == {"ws-1": "write", "ws-2": "read"}
        found = await db.execute(
            text("SELECT report FROM iam_migrations WHERE name = :n"),
            {"n": files_offer.MIGRATION_NAME},
        )
        assert json.loads(found.scalar_one())["groups_deleted"] == 3
        assert await files_offer.migrate(db, legacy.iam) is None


# -- the legacy drive flags ------------------------------------------------------------


async def _holding_table(nexus_db, rows: list[tuple[str, bool, bool]]) -> None:
    async with nexus_db() as db:
        await db.execute(
            text(
                f"CREATE TABLE {files_offer.HOLDING_TABLE} (workspace_id TEXT PRIMARY KEY, "
                "platform_drive_enabled BOOLEAN, system_drive_enabled BOOLEAN)"
            )
        )
        for row in rows:
            await db.execute(
                text(f"INSERT INTO {files_offer.HOLDING_TABLE} VALUES (:w, :p, :s)"),
                {"w": row[0], "p": row[1], "s": row[2]},
            )
        await db.commit()


async def _has_holding_table(nexus_db) -> bool:
    async with nexus_db() as db:
        connection = await db.connection()
        return await connection.run_sync(
            lambda sync: inspect(sync).has_table(files_offer.HOLDING_TABLE)
        )


@pytest.mark.asyncio
async def test_the_drive_flags_kept_by_0073_become_the_offer_once(world, nexus_db):
    await MEMBERSHIPS.grant("viewer", "viewer", world.alpha.container)
    await _holding_table(nexus_db, [("ws-1", True, True), ("ws-2", False, False)])
    async with nexus_db() as db:
        await SqlDefaultsStore(db).put(world.alpha)
        await db.commit()
        dry = await files_offer.convert_legacy_drive_flags(world.iam, db, apply=False)
    assert {(c.workspace_id, c.flag, c.action) for c in dry} == {
        ("ws-1", "platform", "converted"),
        ("ws-1", "system", "reported"),
    }
    assert await _has_holding_table(nexus_db) and _given(world, world.alpha) is None

    async with nexus_db() as db:
        changes = await files_offer.convert_legacy_drive_flags(world.iam, db)
    assert {(c.flag, c.action) for c in changes} == {
        ("platform", "converted"),
        ("system", "reported"),
    }
    assert not await _has_holding_table(nexus_db)
    assert _given(world, world.alpha) == "write"
    assert _uses(world, "viewer") == READ_ONLY
    async with nexus_db() as db:
        assert await files_offer.convert_legacy_drive_flags(world.iam, db) == []
