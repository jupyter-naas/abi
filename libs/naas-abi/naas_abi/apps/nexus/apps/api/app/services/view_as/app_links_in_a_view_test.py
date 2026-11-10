"""Apps opened in a view: the link is the person's, ends no later than the view, is revoked
when the view ends (Stop, sign-out or expiry), and each open is audited."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.core import database
from naas_abi.apps.nexus.apps.api.app.models import AuthSessionModel
from naas_abi.apps.nexus.apps.api.app.services.apps import links
from naas_abi.apps.nexus.apps.api.app.services.view_as import runtime
from naas_abi.apps.nexus.apps.api.app.services.view_as.active import use_view
from naas_abi.apps.nexus.apps.api.app.services.view_as.full_app_testing import (
    bind_database,
    build_full_app,
    engine_iam_installed,
    services_installed,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as.port import (
    LinkView,
    link_view_in,
    tag_description,
    view_mark,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as.view_as_http_test import (  # noqa: F401
    ALPHA,
    start,
)
from naas_abi_core.engine.nats_auth import APP_AUDIENCE, PREVIEW_AUDIENCE
from sqlalchemy import select


@pytest_asyncio.fixture
async def apps(world, monkeypatch):
    world.app = build_full_app()
    # Links live in IAM's real time: the view's clock is the real one, as a server's is.
    world.clock.now = datetime.now(UTC).replace(tzinfo=None)
    bind_database(monkeypatch)
    with services_installed(), engine_iam_installed(world.iam):
        yield world


async def running_view(world, client=None):
    """The record of the view that runs now, as a request of its browser sees it."""
    async with database.AsyncSessionLocal() as db:
        for session_id in (await db.execute(select(AuthSessionModel.id))).scalars().all():
            found = await runtime.RUNTIME.service(db).running(session_id)
            if found is not None:
                return found
    raise AssertionError("no view is running")


def mint(
    view, *, minutes: int = 60, audience: str = APP_AUDIENCE, resource: str = "app-remote/m/a"
):
    """A link, made as the person, the way a route does it inside a request of the view."""
    with use_view(view):
        return links.mint_link(
            user_id="dave",
            audience=audience,
            resource=resource,
            minutes=minutes,
        )


@pytest.mark.asyncio
async def test_a_link_made_in_a_view_is_the_persons_and_ends_with_the_view(apps) -> None:
    root = await apps.sign_in("root")
    assert (await start(root, apps, "dave")).status_code == 200
    view = await running_view(apps, root)

    grant, seconds = mint(view, minutes=60)

    opened = links.open_link(grant, APP_AUDIENCE)
    assert opened is not None
    assert opened.user_id == "dave"  # the person's link, not the viewer's
    assert opened.view == LinkView(mark=view_mark(view), person="Dave")
    # An hour was asked for: the view ends in 15 minutes, and so does the link.
    assert seconds <= 15 * 60
    assert opened.expires_at is not None
    assert abs((opened.expires_at - view.ends_at.replace(tzinfo=UTC)).total_seconds()) < 2
    # The preview link of a draft is bound just the same.
    preview, left = mint(view, audience=PREVIEW_AUDIENCE, resource="preview/alpha/slug")
    assert left <= 15 * 60 and links.open_link(preview, PREVIEW_AUDIENCE).view is not None


@pytest.mark.asyncio
async def test_a_link_made_outside_a_view_is_unchanged(apps) -> None:
    grant, seconds = mint(None, minutes=60)

    opened = links.open_link(grant, APP_AUDIENCE)

    assert opened is not None and opened.view is None
    assert 59 * 60 <= seconds <= 60 * 60


@pytest.mark.asyncio
async def test_a_link_made_from_a_view_link_keeps_the_limits(apps) -> None:
    """The catalog URL turns a link into a fresh grant: it stays the view's, and within the
    time of the link it came from."""
    view_link = LinkView(mark="abc", person="Dave")
    until = datetime.now(UTC) + timedelta(minutes=5)

    grant, seconds = links.mint_link(
        user_id="dave",
        audience=APP_AUDIENCE,
        resource="app-remote/m/a",
        minutes=60,
        not_after=until,
        view=view_link,
    )

    opened = links.open_link(grant, APP_AUDIENCE)
    assert opened is not None and opened.view == view_link
    assert seconds <= 5 * 60


def test_the_description_says_which_view_made_a_link() -> None:
    view = LinkView(mark="0123456789abcdef", person="Dave | the Great")
    tagged = tag_description(view, "remote app: m/a")
    assert link_view_in(tagged) == LinkView(mark="0123456789abcdef", person="Dave the Great")
    assert link_view_in("remote app: m/a") is None
    assert link_view_in("view-as:") is None and link_view_in("") is None
    assert len(tag_description(LinkView("m", "x" * 500), "y" * 500)) <= 200


@pytest.mark.asyncio
async def test_the_links_of_a_view_are_revoked_at_stop(apps) -> None:
    root = await apps.sign_in("root")
    await start(root, apps, "dave")
    view = await running_view(apps, root)
    in_view, _ = mint(view)
    other_view_link = mint(None)[0]  # the person's own link, made outside any view
    assert links.open_link(in_view, APP_AUDIENCE) is not None

    stopped = await root.delete("/api/iam/view-as")

    assert stopped.json() == {"stopped": True}
    assert links.open_link(in_view, APP_AUDIENCE) is None  # revoked with the view
    assert links.open_link(other_view_link, APP_AUDIENCE) is not None  # theirs: untouched


@pytest.mark.asyncio
async def test_the_links_of_a_view_are_revoked_at_sign_out(apps) -> None:
    root = await apps.sign_in("root")
    await start(root, apps, "dave")
    view = await running_view(apps, root)
    grant, _ = mint(view)

    out = await root.post("/api/auth/oidc/logout")

    assert out.status_code in (200, 204)
    assert links.open_link(grant, APP_AUDIENCE) is None


@pytest.mark.asyncio
async def test_the_links_of_a_view_are_revoked_when_it_expires(apps) -> None:
    root = await apps.sign_in("root")
    await start(root, apps, "dave")
    view = await running_view(apps, root)
    grant, _ = mint(view)

    apps.clock.now = apps.clock.now + timedelta(minutes=16)
    await root.get("/api/auth/oidc/session")  # the first request that sees the end

    assert links.open_link(grant, APP_AUDIENCE) is None
    stops = await apps.records("view_as_stop")
    assert [e.detail for e in stops] == ["expired"]


@pytest.mark.asyncio
async def test_each_open_is_audited_and_no_record_means_no_link(apps) -> None:
    root = await apps.sign_in("root")
    await start(root, apps, "dave")
    view = await running_view(apps, root)

    async def make() -> str:
        return "link"

    with use_view(view):
        assert await runtime.audited_open("prices", make) == "link"

    opened = await apps.records("view_as_open_app")
    assert sorted(e.phase for e in opened) == ["requested", "succeeded"]
    assert {e.actor_id for e in opened} == {"root"}  # the viewer
    assert {e.resource_id for e in opened} == {apps.principals["dave"]}  # the person
    assert all("prices" in e.detail and ALPHA in e.detail for e in opened)

    # Outside a view an open is no business of the audit.
    before = len(await apps.records("view_as_open_app"))
    assert await runtime.audited_open("prices", make) == "link"
    assert len(await apps.records("view_as_open_app")) == before
