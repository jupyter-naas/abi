"""Routes a module mounts answer only callers with a credential the engine
accepts, unless the module opts out; the check follows the router's own
choice of route."""

from __future__ import annotations

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from naas_abi_core.apps.api import abi_api_key_auth
from naas_abi_core.apps.api.module_routes import mount_module_apis
from starlette.responses import PlainTextResponse
from starlette.routing import Route

KEY = "deployment-key"
ORIGIN = "https://app.example.test"


class Datasets:
    """Mounts a data router and a sub-application."""

    unguarded_api_paths: tuple[str, ...] = ()

    def api(self, app: FastAPI) -> None:
        router = APIRouter()

        @router.get("/rows/{name}")
        def rows(name: str) -> dict:
            return {"rows": [name]}

        @router.get("/secret")
        def secret() -> dict:
            return {"secret": True}

        app.include_router(router, prefix="/api/datasets")
        app.mount(
            "/api/datasets-files",
            FastAPI(routes=[Route("/f", lambda r: PlainTextResponse("file"))]),
        )


class Logos:
    """Serves images to anyone, and says so."""

    unguarded_api_paths = ("/api/logos",)

    def api(self, app: FastAPI) -> None:
        app.add_api_route("/api/logos/{name}", lambda name: {"logo": name})
        app.add_api_route("/app-html/logos/page", lambda: {"page": True})


class SelfChecking:
    """Checks every caller itself, like the Nexus API."""

    api_checks_its_callers = True

    def api(self, app: FastAPI) -> None:
        app.add_api_route("/api/auth/login", lambda: {"login": True}, methods=["POST"])
        app.add_api_route("/api/own/{name}", lambda name: {"own": name})


@pytest.fixture
def c(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ABI_API_KEY", KEY)
    monkeypatch.setattr(abi_api_key_auth, "_EXTRA_APP_HTML_TOKEN_VALIDATORS", [])
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=[ORIGIN])

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    mount_module_apis(app, [Datasets(), Logos(), SelfChecking()])
    return TestClient(app)


def test_module_routes_keep_to_callers_with_a_credential(c: TestClient) -> None:
    key = {"Authorization": f"Bearer {KEY}"}

    assert c.get("/api/datasets/rows/a").status_code == 401
    assert (
        c.get("/api/datasets/rows/a", headers={"Authorization": "Bearer x"}).status_code
        == 401
    )
    assert c.get("/api/datasets-files/f").status_code == 401
    assert c.get("/api/datasets/rows/a", headers=key).json() == {"rows": ["a"]}
    assert c.get("/api/datasets-files/f", headers=key).text == "file"


@pytest.mark.parametrize(
    ("path", "headers"),
    [
        ("/api/datasets/rows/%23a", {}),
        ("/api/datasets/rows/a%3Fb", {}),
        ("/api/datasets/secret", {"Host": "x#"}),
        ("/api/datasets/secret", {"Host": "x?"}),
        ("/api/datasets/secret", {"Host": "x/elsewhere?q="}),
        ("/api/datasets/secret/", {}),
    ],
)
def test_module_routes_keep_to_the_route_the_router_picks(
    c: TestClient, path: str, headers: dict[str, str]
) -> None:
    response = c.get(path, headers=headers)

    assert response.status_code in (401, 307), response.text
    assert "secret" not in response.text and "rows" not in response.text


def test_module_routes_keep_their_explicit_opt_outs(c: TestClient) -> None:
    assert c.get("/api/logos/acme").json() == {"logo": "acme"}
    assert c.post("/api/auth/login").json() == {"login": True}
    assert c.get("/api/own/a").json() == {"own": "a"}
    # The engine's own routes and /app-html/ (its own middleware) are not the
    # module guard's.
    assert c.get("/health").status_code == 200
    assert c.get("/app-html/logos/page").status_code == 200


def test_module_route_refusals_keep_their_cors_headers(c: TestClient) -> None:
    response = c.get("/api/datasets/secret", headers={"Origin": ORIGIN})

    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_a_registered_validator_vouches_for_module_routes(
    c: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        abi_api_key_auth,
        "_EXTRA_APP_HTML_TOKEN_VALIDATORS",
        [lambda token, request: token == "vouched"],
    )

    response = c.get(
        "/api/datasets/rows/a", headers={"Authorization": "Bearer vouched"}
    )

    assert response.status_code == 200
