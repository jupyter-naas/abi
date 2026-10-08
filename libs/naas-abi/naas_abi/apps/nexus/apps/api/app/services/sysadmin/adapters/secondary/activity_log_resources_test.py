import asyncio
import json
from urllib.parse import quote

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.activity_log_resources import (
    ActivityLogResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    ReadOnlyResourcesContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    InvalidResource,
    ResourceNotFound,
)
from naas_abi_core.services.activity_log.ActivityLogPort import ActivityEvent
from naas_abi_core.services.activity_log.ActivityLogService import ActivityLogService
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogSqliteAdapter import (
    ActivityLogSqliteAdapter,
)

ALICE = quote("user:alice/admin", safe="")


@pytest.fixture
def service(tmp_path):
    log = ActivityLogService(ActivityLogSqliteAdapter(str(tmp_path / "activity")))
    for i in range(4):
        log.record(
            ActivityEvent(
                actor_id="user:alice/admin",
                event_type=f"http.request.{i}",
                correlation_id=f"req-{i}",
                attributes={"i": i},
            )
        )
    log.record(ActivityEvent(actor_id="service:triple_store", event_type="insert"))
    log.record(ActivityEvent(actor_id="anonymous", event_type="http.request"))
    yield log
    log.shutdown()


class TestActors(ReadOnlyResourcesContract):
    @pytest.fixture
    def resources(self, service):
        return ActivityLogResources(service)


class TestEventsOfOneActor(ReadOnlyResourcesContract):
    base = ALICE

    @pytest.fixture
    def resources(self, service):
        return ActivityLogResources(service)


def test_actors_are_containers_with_encoded_ids(service):
    page = asyncio.run(ActivityLogResources(service).list())

    assert [(e.name, e.kind) for e in page.entries] == [
        ("anonymous", "container"),
        ("service:triple_store", "container"),
        ("user:alice/admin", "container"),
    ]
    assert page.entries[2].id == ALICE


def test_events_list_newest_first_with_a_seq_cursor(service):
    resources = ActivityLogResources(service)

    first = asyncio.run(resources.list(ALICE, limit=3))
    rest = asyncio.run(resources.list(ALICE, cursor=first.next_cursor, limit=3))

    assert [e.name for e in first.entries + rest.entries] == [
        "http.request.3",
        "http.request.2",
        "http.request.1",
        "http.request.0",
    ]
    assert rest.next_cursor is None
    assert first.entries[0].attributes["correlation_id"] == "req-3"


def test_read_shows_the_event_as_json(service):
    resources = ActivityLogResources(service)
    newest = asyncio.run(resources.list(ALICE)).entries[0]

    body = json.loads(asyncio.run(resources.read(newest.id)).content.text)

    assert (body["actor_id"], body["event_type"], body["attributes"]) == (
        "user:alice/admin",
        "http.request.3",
        {"i": 3},
    )


def test_unknown_and_malformed_ids(service):
    resources = ActivityLogResources(service)

    with pytest.raises(ResourceNotFound):
        asyncio.run(resources.stat(f"{ALICE}/999"))
    with pytest.raises(ResourceNotFound):
        asyncio.run(resources.list(quote("user:nobody", safe="")))
    with pytest.raises(InvalidResource):
        asyncio.run(resources.list(ALICE, cursor="later"))
    with pytest.raises(InvalidResource):
        asyncio.run(resources.read(ALICE))


def _request(log, actor="user:u1", path="/api/workspaces", status=200, **extra):
    log.record(
        ActivityEvent(
            actor_id=actor,
            event_type="http.request",
            correlation_id="req-9",
            attributes={
                "method": "GET",
                "path": path,
                "status_code": status,
                "duration_ms": 12,
                "ip": "10.0.0.2",
                "user_agent": "Mozilla/5.0 (Macintosh)",
                "query_params": {"limit": "50"},
                **extra,
            },
        )
    )


def test_actors_carry_their_kind_and_last_activity(service):
    page = asyncio.run(ActivityLogResources(service).list())
    kinds = {e.name: e.attributes["kind"] for e in page.entries}

    assert kinds == {
        "anonymous": "anonymous",
        "service:triple_store": "service",
        "user:alice/admin": "user",
    }
    assert all(e.modified for e in page.entries)


def test_http_requests_are_named_by_path_with_method_and_status(service):
    _request(service)
    resources = ActivityLogResources(service)

    (request,) = asyncio.run(resources.list(quote("user:u1", safe=""))).entries
    detail = asyncio.run(resources.read(request.id))

    assert request.name == "/api/workspaces"
    assert {k: request.attributes[k] for k in ("method", "status", "duration_ms", "ip")} == {
        "method": "GET",
        "status": "200",
        "duration_ms": "12",
        "ip": "10.0.0.2",
    }
    assert request.attributes["summary"] == "?limit=50 · 10.0.0.2 · Mozilla/5.0"
    assert detail.view["type"] == "json"
    assert detail.view["value"]["attributes"]["path"] == "/api/workspaces"


def test_users_show_by_name_when_known(service):
    _request(service, actor="user:u1")
    asked = []

    async def names(ids):
        asked.append(ids)
        return {"u1": ("Ada Lovelace", "ada@example.com")}

    page = asyncio.run(ActivityLogResources(service, actor_names=names).list())
    ada = next(e for e in page.entries if e.attributes["actor"] == "user:u1")

    assert asked == [["alice/admin", "u1"]]
    assert (ada.name, ada.attributes["email"]) == ("Ada Lovelace", "ada@example.com")
    assert ada.attributes["summary"] == "ada@example.com · user:u1"
    assert ada.id == quote("user:u1", safe="")


def test_names_are_best_effort(service):
    async def broken(ids):
        raise RuntimeError("db down")

    page = asyncio.run(ActivityLogResources(service, actor_names=broken).list())

    assert "user:alice/admin" in {e.name for e in page.entries}


def test_sql_actor_names_reads_the_users_table(tmp_path):
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.activity_log_resources import (
        sql_actor_names,
    )
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}")

    async def run():
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE users (id TEXT, name TEXT, email TEXT)"))
            await conn.execute(text("INSERT INTO users VALUES ('u1', 'Ada', 'ada@example.com')"))
        found = await sql_actor_names(lambda: engine)(["u1", "u2"])
        await engine.dispose()
        return found

    assert asyncio.run(run()) == {"u1": ("Ada", "ada@example.com")}
