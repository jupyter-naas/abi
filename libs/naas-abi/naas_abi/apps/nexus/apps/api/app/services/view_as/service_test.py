"""The view's use cases, on fakes: what is asked of IAM, what is kept, what is audited."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.testing import MemoryAudit
from naas_abi.apps.nexus.apps.api.app.services.view_as.port import (
    VIEW_LIFETIME,
    Person,
    RecordedGroups,
    UnknownPersonError,
    UnknownWorkspaceError,
    ViewAlreadyRunningError,
    Viewer,
    WorkspaceRef,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as.service import ViewAsService
from naas_abi.apps.nexus.apps.api.app.services.view_as.testing import FakeViewIam, MemoryViewStore
from naas_abi_core.services.iam.IAMPorts import ViewAsRefused

NOW = datetime(2026, 11, 6, 10, 0, 0)
ALPHA = "abi:nexus:organization/acme/nexus:workspace/alpha"
BRAVO = "abi:nexus:organization/acme/nexus:workspace/bravo"
VIEWER = Viewer(user_id="root", session_id="s1", group_ids=("grp_root",))


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def world():
    store, iam, audit, clock = MemoryViewStore(), FakeViewIam(), MemoryAudit(), Clock()
    store.people["usr_carol"] = store.people["carol"] = Person("carol", "usr_carol", "Carol")
    store.workspace_rows["alpha"] = WorkspaceRef("alpha", "Alpha", "acme", "Acme")
    store.workspace_rows["bravo"] = WorkspaceRef("bravo", "Bravo", "acme", "Acme")
    iam.containers = {"alpha": ALPHA, "bravo": BRAVO}
    iam.belongs = {"carol": ["alpha", "bravo"]}
    iam.allowed = {("usr_carol", ALPHA)}
    service = ViewAsService(store, iam, audit, clock=clock)
    return service, store, iam, audit, clock


def test_a_view_lasts_fifteen_minutes() -> None:
    assert VIEW_LIFETIME == timedelta(minutes=15)


@pytest.mark.asyncio
async def test_a_start_keeps_the_view_for_fifteen_minutes_and_audits_it(world) -> None:
    service, store, iam, audit, _ = world
    view = await service.start(VIEWER, "usr_carol", "alpha")

    assert (view.person_name, view.workspace_name, view.container) == ("Carol", "Alpha", ALPHA)
    assert view.ends_at == NOW + timedelta(minutes=15) and view.ended_at is None
    assert store.views["s1"] == view
    assert iam.checked == [("usr_carol", ALPHA)]
    assert audit.phases("view_as_start") == ["requested", "succeeded"]
    first = audit.records[0].action
    assert (first.actor_id, first.service, first.resource_id) == ("root", "iam", "usr_carol")
    assert "alpha" in first.detail and (NOW + timedelta(minutes=15)).isoformat() in first.detail
    assert first.detail.endswith("groups: none")


@pytest.mark.asyncio
async def test_the_view_keeps_the_groups_iam_checked_and_when_they_were_recorded(world) -> None:
    service, store, iam, audit, _ = world
    store.groups["carol"] = RecordedGroups(("grp_a", "grp_b"), datetime(2026, 11, 5, 8, 0))

    view = await service.start(VIEWER, "usr_carol", "alpha")

    assert iam.groups == [("grp_a", "grp_b")]
    assert view.group_ids == ("grp_a", "grp_b") and view.groups_from == datetime(2026, 11, 5, 8, 0)
    assert "recorded at 2026-11-05T08:00:00" in audit.records[0].action.detail


@pytest.mark.asyncio
async def test_a_refusal_is_iams_and_is_audited(world) -> None:
    service, store, iam, audit, _ = world
    iam.allowed = set()

    with pytest.raises(ViewAsRefused, match="You may not view as usr_carol"):
        await service.start(VIEWER, "usr_carol", "alpha")

    assert store.views == {}
    assert audit.phases("view_as_start") == ["requested", "failed"]
    assert audit.records[-1].error == "ViewAsRefused"


@pytest.mark.asyncio
async def test_nothing_starts_when_the_audit_cannot_be_written(world) -> None:
    service, store, iam, audit, _ = world
    audit.broken = True

    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import AuditUnavailable

    with pytest.raises(AuditUnavailable):
        await service.start(VIEWER, "usr_carol", "alpha")

    assert store.views == {} and iam.checked == []


@pytest.mark.asyncio
async def test_an_unknown_person_or_workspace_starts_nothing(world) -> None:
    service, store, _, audit, _ = world
    with pytest.raises(UnknownPersonError):
        await service.start(VIEWER, "usr_nobody", "alpha")
    with pytest.raises(UnknownWorkspaceError):
        await service.start(VIEWER, "usr_carol", "nowhere")
    assert store.views == {}
    assert audit.phases("view_as_start") == ["requested", "failed", "requested", "failed"]


@pytest.mark.asyncio
async def test_one_view_per_session(world) -> None:
    service, store, _, audit, _ = world
    await service.start(VIEWER, "usr_carol", "alpha")

    with pytest.raises(ViewAlreadyRunningError):
        await service.start(VIEWER, "usr_carol", "alpha")

    other = Viewer(user_id="root", session_id="s2")
    assert (await service.start(other, "usr_carol", "alpha")).session_id == "s2"


@pytest.mark.asyncio
async def test_a_view_that_is_over_makes_room_for_a_new_one_and_is_recorded_expired(world) -> None:
    service, store, _, audit, clock = world
    await service.start(VIEWER, "usr_carol", "alpha")
    clock.now = NOW + timedelta(minutes=16)

    again = await service.start(VIEWER, "usr_carol", "alpha")

    assert again.started_at == clock.now
    stops = [r for r in audit.records if r.action.operation == "view_as_stop"]
    assert [r.action.detail for r in stops] == ["expired"]


@pytest.mark.asyncio
async def test_stop_ends_the_view_and_records_it(world) -> None:
    service, store, _, audit, clock = world
    await service.start(VIEWER, "usr_carol", "alpha")
    clock.now = NOW + timedelta(minutes=3)

    ended = await service.stop("s1")

    assert ended is not None and ended.ended_at == clock.now
    assert await service.running("s1") is None
    stop = [r for r in audit.records if r.action.operation == "view_as_stop"]
    assert [(r.action.actor_id, r.action.resource_id, r.action.detail) for r in stop] == [
        ("root", "usr_carol", "stop")
    ]
    assert await service.stop("s1") is None  # nothing runs: nothing more is recorded
    assert len([r for r in audit.records if r.action.operation == "view_as_stop"]) == 1


@pytest.mark.asyncio
async def test_a_view_past_its_end_is_ended_and_recorded_when_a_request_sees_it(world) -> None:
    service, _, _, audit, clock = world
    await service.start(VIEWER, "usr_carol", "alpha")
    assert (await service.resolve(VIEWER)) is not None
    clock.now = NOW + timedelta(minutes=15)  # the end is the end

    assert await service.running("s1") is None  # reading records nothing
    assert audit.phases("view_as_stop") == []
    assert await service.resolve(VIEWER) is None
    assert [r.action.detail for r in audit.records if r.action.operation == "view_as_stop"] == [
        "expired"
    ]
    assert await service.resolve(VIEWER) is None  # recorded once
    assert audit.phases("view_as_stop") == ["succeeded"]


@pytest.mark.asyncio
async def test_iam_is_asked_again_at_every_request_with_one_check(world) -> None:
    service, _, iam, audit, _ = world
    await service.start(VIEWER, "usr_carol", "alpha")

    for _ in range(3):
        assert await service.resolve(VIEWER) is not None
    assert iam.one_check == 3

    iam.allowed = set()  # the viewer lost the right
    assert await service.resolve(VIEWER) is None
    assert [r.action.detail for r in audit.records if r.action.operation == "view_as_stop"] == [
        "no longer allowed"
    ]


@pytest.mark.asyncio
async def test_the_end_of_a_view_is_never_kept_open_by_an_audit_that_fails(world) -> None:
    service, store, _, audit, _ = world
    await service.start(VIEWER, "usr_carol", "alpha")
    audit.broken = True

    assert await service.stop("s1") is not None
    assert store.views["s1"].ended_at is not None


@pytest.mark.asyncio
async def test_the_workspaces_are_those_iam_accepts(world) -> None:
    service, store, iam, _, _ = world

    found = await service.workspaces(VIEWER, "usr_carol")

    assert [(w.id, w.name, w.organization_id, w.organization_name) for w in found] == [
        ("alpha", "Alpha", "acme", "Acme")
    ]
    assert await service.workspaces(VIEWER, "usr_nobody") == []
    iam.allowed = set()
    assert await service.workspaces(VIEWER, "usr_carol") == []


@pytest.mark.asyncio
async def test_the_person_is_named_by_their_principal_id_whichever_id_was_given(world) -> None:
    service, store, iam, audit, _ = world

    found = await service.workspaces(VIEWER, "carol")  # the Nexus id of the account
    view = await service.start(VIEWER, "carol", "alpha")

    assert [w.id for w in found] == ["alpha"]
    assert iam.checked == [("usr_carol", ALPHA)]
    assert view.person_principal_id == "usr_carol"
    assert audit.records[0].action.resource_id == "usr_carol"
    assert await service.resolve(VIEWER) is not None  # the re-check asks about the same id
    await service.stop("s1")
    assert [
        r.action.resource_id for r in audit.records if r.action.operation == "view_as_stop"
    ] == ["usr_carol"]
