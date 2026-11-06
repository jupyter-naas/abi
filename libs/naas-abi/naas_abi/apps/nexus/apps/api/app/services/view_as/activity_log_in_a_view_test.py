"""The activity log in a view: the events name the viewer, with the person viewed as an
attribute. Nothing is recorded as the person's activity."""

from __future__ import annotations

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.services.view_as.full_app_testing import (
    bind_database,
    build_full_app,
    services_installed,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as.view_as_http_test import (  # noqa: F401
    ALPHA,
    start,
)
from naas_abi_core.engine.call_context import current_call_context


class RecordingLog:
    """The activity log service: each event, with the actor the call names."""

    def __init__(self) -> None:
        self.events: list[tuple[str | None, object]] = []

    def record(self, event) -> None:
        caller = current_call_context().on_behalf_of
        self.events.append((caller.id if caller else None, event))

    def by(self, actor: str) -> list:
        return [event for who, event in self.events if who == actor]


@pytest_asyncio.fixture
async def logged(world, monkeypatch):
    log = RecordingLog()
    app = build_full_app(activity_log=log)
    bind_database(monkeypatch)
    world.app, world.log = app, log
    with services_installed():
        yield world


async def _requests(log: RecordingLog, path: str) -> list:
    return [e for _, e in log.events if e.attributes.get("path") == path]


@pytest.mark.asyncio
async def test_a_request_in_a_view_is_recorded_as_the_viewer(logged) -> None:
    root = await logged.sign_in("root")
    assert (await start(root, logged, "dave")).status_code == 200
    logged.log.events.clear()

    answered = await root.get(f"/api/chat/conversations?workspace_id={ALPHA}")

    assert answered.status_code == 200
    events = await _requests(logged.log, "/api/chat/conversations")
    assert len(events) == 1
    [(actor, event)] = [(a, e) for a, e in logged.log.events if e in events]
    assert actor == "root"  # the viewer
    assert event.attributes["view_as"] == {
        "principal_id": logged.principals["dave"],
        "workspace_id": ALPHA,
    }
    assert logged.log.by("dave") == []  # nothing is the person's activity


@pytest.mark.asyncio
async def test_a_refused_request_in_a_view_is_recorded_as_the_viewer_too(logged) -> None:
    root = await logged.sign_in("root")
    await start(root, logged, "dave")
    logged.log.events.clear()

    refused = await root.post("/api/chat/conversations", json={"workspace_id": ALPHA})

    assert refused.status_code == 403
    assert logged.log.by("dave") == []
    [event] = logged.log.by("root")
    assert event.attributes["status_code"] == 403
    assert event.attributes["view_as"]["principal_id"] == logged.principals["dave"]


@pytest.mark.asyncio
async def test_outside_a_view_the_event_names_the_user_and_no_view(logged) -> None:
    dave = await logged.sign_in("dave")
    root = await logged.sign_in("root")

    await dave.get(f"/api/chat/conversations?workspace_id={ALPHA}")
    await start(root, logged, "dave")
    await root.delete("/api/iam/view-as")
    logged.log.events.clear()
    await root.get(f"/api/chat/conversations?workspace_id={ALPHA}")  # root again: no view

    for actor in ("dave", "root"):
        for event in logged.log.by(actor):
            assert "view_as" not in event.attributes
