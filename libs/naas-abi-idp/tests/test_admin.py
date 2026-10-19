import pytest
from starlette.testclient import TestClient

from naas_abi_idp.admin import AdminAPI


class AsUser:
    """The scope the app host builds: the user is the one discovery verified."""

    def __init__(self, app, user_id):
        self.app, self.user_id = app, user_id

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            scope["abi"] = {"user_id": self.user_id}
        await self.app(scope, receive, send)


@pytest.fixture
def admin(service):
    return TestClient(AsUser(AdminAPI(service).app(), ""))


def test_users_are_created_listed_and_disabled(admin, service):
    created = admin.post("/users", json={"email": "Bob@Example.com", "name": "Bob B"})
    assert created.status_code == 201
    user = created.json()
    assert user["email"] == "bob@example.com" and user["disabled"] is False
    assert "password_hash" not in user
    assert admin.post("/users", json={"email": "bob@example.com"}).status_code == 409
    assert admin.post("/users", json={"email": "nope"}).status_code == 400
    assert admin.post("/users", json={}).status_code == 400

    listed = admin.get("/users").json()
    assert [u["email"] for u in listed["users"]] == ["bob@example.com"]
    assert (
        admin.get("/users/by-email", params={"email": "BOB@example.com"}).json()["id"]
        == user["id"]
    )
    assert (
        admin.get("/users/by-email", params={"email": "x@example.com"}).status_code
        == 404
    )
    assert admin.get(f"/users/{user['id']}").json()["name"] == "Bob B"

    off = admin.post(f"/users/{user['id']}/disable").json()
    assert off["disabled"] is True
    assert service.request_code("bob@example.com", None) is False
    assert admin.post(f"/users/{user['id']}/enable").json()["disabled"] is False
    assert admin.get("/users/u_missing").status_code == 404


def test_users_page(admin):
    for i in range(5):
        admin.post("/users", json={"email": f"u{i}@example.com"})
    first = admin.get("/users", params={"limit": 2}).json()
    assert len(first["users"]) == 2 and first["next"]
    second = admin.get("/users", params={"limit": 10, "after": first["next"]}).json()
    assert len(second["users"]) == 3 and second["next"] is None
    assert admin.get("/users", params={"limit": "x"}).status_code == 400


def test_groups_and_members(admin):
    group = admin.post(
        "/groups", json={"name": "Data readers", "description": "d"}
    ).json()
    assert admin.post("/groups", json={"name": "Data readers"}).status_code == 409
    assert admin.post("/groups", json={"name": "!!"}).status_code == 400
    user = admin.post(
        "/users", json={"email": "bob@example.com", "groups": ["Data readers"]}
    ).json()
    assert user["groups"] == [group["id"]]
    assert [g["name"] for g in admin.get("/groups").json()["groups"]] == [
        "Data readers"
    ]
    user = admin.delete(f"/groups/{group['id']}/members/{user['id']}").json()
    assert user["groups"] == []
    user = admin.put(f"/groups/Data readers/members/{user['id']}").json()
    assert user["groups"] == [group["id"]]
    assert admin.delete(f"/groups/{group['id']}").json() == {"deleted": True}
    assert admin.get(f"/users/{user['id']}").json()["groups"] == []
    assert admin.delete("/groups/nope").status_code == 404


def test_a_client_secret_is_shown_once(admin, service):
    created = admin.post(
        "/clients",
        json={"name": "ci", "scopes": ["jobs"], "grant_types": ["client_credentials"]},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["client_secret"] and body["confidential"] is True
    listed = admin.get("/clients").json()["clients"]
    assert all("client_secret" not in c and "secret_hash" not in c for c in listed)
    assert (
        admin.post(f"/clients/{body['client_id']}/disable").json()["disabled"] is True
    )
    assert (
        admin.post("/clients", json={"name": "x", "grant_types": ["bogus"]}).status_code
        == 400
    )


def test_the_signing_key_rotates(admin, service):
    before = service.keys.active().kid
    rotated = admin.post("/keys/rotate").json()["kid"]
    assert rotated != before and service.keys.active().kid == rotated


def test_a_call_for_a_signed_in_user_is_refused(service):
    for_user = TestClient(AsUser(AdminAPI(service).app(), "usr_someone"))
    assert for_user.get("/users").status_code == 403
    assert for_user.post("/users", json={"email": "a@example.com"}).status_code == 403
    assert service.find_user("a@example.com") is None


def test_bad_bodies(admin):
    assert admin.post("/users", content="not json").status_code == 400
    assert admin.post("/users", content="[1]").status_code == 400
    assert admin.post("/users", content=b"x" * 70000).status_code == 400
