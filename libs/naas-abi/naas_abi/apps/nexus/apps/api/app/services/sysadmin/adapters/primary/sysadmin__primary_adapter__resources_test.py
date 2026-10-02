import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.primary.sysadmin__primary_adapter__FastAPI import (
    router,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_resources import (
    InMemoryAuditLog,
    InMemoryResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import get_resource_admin
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources_service import (
    ResourceAdminService,
)

BASE = "/api/admin/system/resources"


@pytest.fixture
def objects():
    return InMemoryResources(
        "object_storage", {"docs/a.txt": b"hello", "docs/b.txt": b"bye", "top.bin": b"\x00"}
    )


@pytest.fixture
def secrets():
    return InMemoryResources("secret", {"OPENAI_API_KEY": b"sk-123"}, masked=True)


@pytest.fixture
def audit():
    return InMemoryAuditLog()


@pytest.fixture
def admin(objects, secrets, audit):
    return ResourceAdminService(
        {
            "object_storage": objects,
            "secret": secrets,
            "vector_store": SourceUnavailable("vector_store", "not a dependency"),
        },
        audit,
        upload_limit=32,
    )


def _client(admin, *, is_superadmin=True):
    app = FastAPI()
    app.include_router(router, prefix="/api/admin/system")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="u1", email="u1@example.com", name="U1", is_superadmin=is_superadmin
    )
    app.dependency_overrides[get_resource_admin] = lambda: admin
    return TestClient(app)


@pytest.fixture
def client(admin):
    return _client(admin)


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", ""),
        ("GET", "/secret/entries"),
        ("GET", "/secret/entry?id=OPENAI_API_KEY"),
        ("POST", "/secret/reveal?id=OPENAI_API_KEY"),
        ("GET", "/object_storage/download?id=top.bin"),
        ("PUT", "/object_storage/entry?id=x.txt"),
        ("DELETE", "/object_storage/entry?id=top.bin&confirm=top.bin"),
    ],
)
def test_every_route_is_for_super_admins_only(admin, objects, method, path):
    response = _client(admin, is_superadmin=False).request(method, BASE + path, content=b"x")

    assert response.status_code == 403
    assert "top.bin" in objects.items and "x.txt" not in objects.items


def test_lists_services_with_availability(client):
    services = {s["name"]: s for s in client.get(BASE).json()["services"]}

    assert services["secret"]["capabilities"] == {
        "browse": True,
        "lookup": False,
        "create": True,
        "reveal": True,
        "write_format": "",
        "search": False,
    }
    assert services["vector_store"]["available"] is False
    assert services["vector_store"]["reason"] == "not a dependency"


def test_browses_containers_and_pages(client):
    root = client.get(f"{BASE}/object_storage/entries").json()
    page = client.get(f"{BASE}/object_storage/entries", params={"parent": "docs", "limit": 1})

    assert [(e["id"], e["kind"]) for e in root["entries"]] == [
        ("docs", "container"),
        ("top.bin", "item"),
    ]
    assert [e["id"] for e in page.json()["entries"]] == ["docs/a.txt"]
    assert page.json()["next_cursor"] == "1"


def test_reads_mask_secrets_and_reveal_is_audited_and_not_cached(client, audit):
    masked = client.get(f"{BASE}/secret/entry", params={"id": "OPENAI_API_KEY"})
    revealed = client.post(f"{BASE}/secret/reveal", params={"id": "OPENAI_API_KEY"})

    assert masked.json()["content"] == {
        "encoding": "masked",
        "text": None,
        "size": None,
        "truncated": False,
    }
    assert "sk-123" not in masked.text
    assert revealed.json()["content"]["text"] == "sk-123"
    assert revealed.headers["cache-control"] == "no-store"
    assert [(r.action.actor_id, r.action.operation, r.phase) for r in audit.records] == [
        ("u1", "reveal", "requested"),
        ("u1", "reveal", "succeeded"),
    ]


def test_replacing_needs_confirmation(client, objects):
    created = client.put(f"{BASE}/object_storage/entry", params={"id": "new.txt"}, content=b"n")
    refused = client.put(f"{BASE}/object_storage/entry", params={"id": "new.txt"}, content=b"m")
    replaced = client.put(
        f"{BASE}/object_storage/entry",
        params={"id": "new.txt", "confirm": "new.txt"},
        content=b"m",
    )

    assert created.status_code == 200 and created.json()["id"] == "new.txt"
    assert refused.status_code == 409
    assert refused.json()["detail"]["confirm"] == "new.txt"
    assert replaced.status_code == 200
    assert objects.items["new.txt"] == b"m"


def test_delete_needs_confirmation(client, objects):
    refused = client.delete(f"{BASE}/object_storage/entry", params={"id": "top.bin"})
    deleted = client.delete(
        f"{BASE}/object_storage/entry", params={"id": "top.bin", "confirm": "top.bin"}
    )

    assert refused.status_code == 409
    assert deleted.status_code == 204
    assert "top.bin" not in objects.items
    assert client.get(f"{BASE}/object_storage/entry", params={"id": "top.bin"}).status_code == 404


def test_uploads_over_the_limit_are_refused(client, objects):
    response = client.put(
        f"{BASE}/object_storage/entry", params={"id": "big.bin"}, content=b"x" * 33
    )

    assert response.status_code == 413
    assert response.json()["detail"]["limit"] == 32
    assert "big.bin" not in objects.items


def test_downloads_are_attachments(client):
    response = client.get(f"{BASE}/object_storage/download", params={"id": "docs/a.txt"})

    assert response.content == b"hello"
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert client.get(f"{BASE}/secret/download", params={"id": "OPENAI_API_KEY"}).status_code == 405


def test_no_change_without_audit(objects, secrets):
    admin = ResourceAdminService(
        {"object_storage": objects, "secret": secrets}, InMemoryAuditLog(fail="db down")
    )

    response = _client(admin).delete(
        f"{BASE}/object_storage/entry", params={"id": "top.bin", "confirm": "top.bin"}
    )

    assert response.status_code == 503
    assert response.json()["detail"]["source"] == "audit"
    assert "top.bin" in objects.items


def test_unknown_and_unavailable_services(client):
    assert client.get(f"{BASE}/nope/entries").status_code == 404
    unavailable = client.get(f"{BASE}/vector_store/entries")
    assert unavailable.status_code == 503
    assert unavailable.json()["detail"] == {"source": "vector_store", "reason": "not a dependency"}


def test_invalid_requests(client):
    assert (
        client.get(f"{BASE}/object_storage/entries", params={"parent": "top.bin"}).status_code
        == 400
    )
    assert client.get(f"{BASE}/object_storage/entries", params={"cursor": "x"}).status_code == 400
    assert client.post(f"{BASE}/object_storage/reveal", params={"id": "top.bin"}).status_code == 405


def test_history_of_one_entry_and_of_everything(client):
    client.delete(f"{BASE}/object_storage/entry", params={"id": "top.bin", "confirm": "top.bin"})
    client.post(f"{BASE}/secret/reveal", params={"id": "OPENAI_API_KEY"})

    one = client.get(f"{BASE}/object_storage/history", params={"id": "top.bin"}).json()["entries"]
    everything = client.get(f"{BASE}/history").json()["entries"]

    assert [(e["operation"], e["phase"]) for e in one] == [
        ("delete", "succeeded"),
        ("delete", "requested"),
    ]
    assert [e["service"] for e in everything] == [
        "secret",
        "secret",
        "object_storage",
        "object_storage",
    ]
    assert client.get(f"{BASE}/nope/history", params={"id": "x"}).status_code == 404


def test_search_is_passed_only_to_services_that_support_it(admin, objects):
    calls = []
    original = objects.list

    async def spy(parent="", *, cursor=None, limit=100, **options):
        calls.append(options)
        return await original(parent, cursor=cursor, limit=limit)

    objects.list = spy
    client = _client(admin)

    client.get(f"{BASE}/object_storage/entries", params={"query": "doc"})
    objects.capabilities = type(objects.capabilities)(browse=True, create=True, search=True)
    client.get(f"{BASE}/object_storage/entries", params={"query": "doc"})

    assert calls == [{}, {"query": "doc"}]
