"""A page load in a view changes nothing: no Nexus row, no IAM write.

Every GET route that names the viewed workspace is called in a view of Dave in Alpha, against
the test database and the test IAM, with a page's parameters. Beside it, the same routes
called outside a view show that the writes are real (the maps' seed rows, the Coder user,
the My Drive placement): a view skips them. The view's own record and the viewer's session
``last_seen_at`` are the only rows that may change.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.routing import APIRoute
from naas_abi.apps.nexus.apps.api.app.core import database
from naas_abi.apps.nexus.apps.api.app.services.view_as import confinement
from naas_abi.apps.nexus.apps.api.app.services.view_as.private_content_test import (  # noqa: F401
    FakeCoding,
    _as_viewer_of,
    full,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as.view_as_http_test import (  # noqa: F401
    ALPHA,
)
from sqlalchemy import text

# Tables a view may write: its own record.
OWN_TABLES = {"view_as_views"}
# The viewer's session is touched at every request of theirs.
IGNORED_COLUMNS = {"auth_sessions": {"last_seen_at"}}
# A path parameter takes this, a required query parameter too.
DUMMY = "x"


async def snapshot() -> dict[str, list[str]]:
    """Every row of every table, as text, but the view's own record."""
    found: dict[str, list[str]] = {}
    async with database.AsyncSessionLocal() as db:
        names = (
            await db.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            )
        ).scalars()
        for name in sorted(names):
            if name in OWN_TABLES:
                continue
            ignored = IGNORED_COLUMNS.get(name, set())
            rows = (await db.execute(text(f'SELECT * FROM "{name}"'))).mappings().all()  # noqa: S608
            found[name] = sorted(
                json.dumps({k: str(v) for k, v in row.items() if k not in ignored}, sort_keys=True)
                for row in rows
            )
    return found


def changes(before: dict[str, list[str]], after: dict[str, list[str]]) -> dict[str, tuple]:
    return {
        name: (len(before.get(name, [])), len(after.get(name, [])))
        for name in set(before) | set(after)
        if before.get(name) != after.get(name)
    }


def workspace_pages(app) -> list[tuple[str, str]]:
    """Every GET route that names the viewed workspace, as a request: (path, query)."""
    found = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or "GET" not in route.methods:
            continue
        if not route.path.startswith("/api/") or (
            confinement.ANSWERED_WITHOUT_A_WORKSPACE.get(("GET", route.path))
        ):
            continue
        if not confinement.route_names_workspace(route):
            continue
        path = route.path
        for name in route.param_convertors:
            path = path.replace("{" + name + "}", ALPHA if name == "workspace_id" else DUMMY)
            path = re.sub(r"\{" + name + r":[a-z]+\}", DUMMY, path)
        query = {"workspace_id": ALPHA}
        for param in route.dependant.query_params:
            if param.field_info.is_required() and param.name != "workspace_id":
                query[param.name] = DUMMY
        found.append((path, "&".join(f"{k}={v}" for k, v in query.items())))
    return sorted(set(found))


async def call_all(client, pages, iam=None) -> tuple[dict[str, object], dict[str, object]]:
    """Call each page; its answer, and what it changed (page -> tables), after each."""
    answers: dict[str, object] = {}
    wrote: dict[str, object] = {}
    state = await snapshot()
    revision = iam.store.revision() if iam is not None else None
    for path, query in pages:
        try:
            answers[path] = (await client.get(f"{path}?{query}")).status_code
        except Exception as exc:  # noqa: BLE001 - a route that raises still must not have written
            answers[path] = type(exc).__name__
        now = await snapshot()
        if changes(state, now):
            wrote[path] = changes(state, now)
        if iam is not None and iam.store.revision() != revision:
            wrote[path] = {**wrote.get(path, {}), "iam": True}
            revision = iam.store.revision()
        state = now
    return answers, wrote


@pytest.mark.asyncio
async def test_no_workspace_page_writes_anything_in_a_view(full) -> None:  # noqa: F811
    pages = workspace_pages(full.app)
    assert len(pages) > 100  # the whole application's workspace pages, not a sample
    root = await _as_viewer_of(full, "dave")

    answers, wrote = await call_all(root, pages, full.iam)

    assert wrote == {}  # no Nexus row, no IAM write, by any page
    assert full.coding.ensured == []  # no Coder user
    assert 200 in answers.values()  # pages did answer: the test ran real routes


@pytest.mark.asyncio
async def test_the_same_pages_do_write_outside_a_view(full) -> None:  # noqa: F811
    """The control: the writes the view skips are real, or the test above proves nothing."""
    pages = [
        (path, query)
        for path, query in workspace_pages(full.app)
        if path.startswith(("/api/maps/", "/api/coding-environments", "/api/files/"))
        and "/x" not in path
    ]
    dave = await full.sign_in("dave")

    _, wrote = await call_all(dave, pages, full.iam)

    assert any(path.startswith("/api/maps/") for path in wrote)  # the maps' seed rows
    assert full.coding.ensured  # the Coder user
    assert wrote["/api/files/"] == {"iam": True}  # the drive's placement in IAM


@pytest.mark.asyncio
async def test_the_routes_answered_without_a_workspace_write_nothing_either(full) -> None:  # noqa: F811
    pages = []
    for method, path in confinement.ANSWERED_WITHOUT_A_WORKSPACE:
        assert method == "GET"
        pages.append((re.sub(r"\{[^}]+\}", DUMMY, path), "a=b"))
    root = await _as_viewer_of(full, "dave")

    answers, wrote = await call_all(root, pages, full.iam)

    assert wrote == {}
    assert answers["/api/auth/me"] == 200 and answers["/api/workspaces"] == 200
