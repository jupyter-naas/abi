import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    ApiConfiguration,
)

DOC_PATHS = ("/openapi.json", "/docs", "/redoc")


@pytest.mark.parametrize("env", [None, "", "local", "dev", "LOCAL"])
def test_docs_default_on_for_local_development(env):
    from naas_abi_core.apps.api.api import api_docs_enabled

    assert api_docs_enabled(ApiConfiguration(), env) is True


@pytest.mark.parametrize("env", ["dokploy", "prod", "remote", "staging"])
def test_docs_default_off_for_deployed_stacks(env):
    from naas_abi_core.apps.api.api import api_docs_enabled

    assert api_docs_enabled(ApiConfiguration(), env) is False


@pytest.mark.parametrize("env", [None, "local", "dev", "dokploy", "prod"])
@pytest.mark.parametrize("docs_enabled", [True, False])
def test_docs_enabled_setting_wins_over_env(env, docs_enabled):
    from naas_abi_core.apps.api.api import api_docs_enabled

    configuration = ApiConfiguration(docs_enabled=docs_enabled)
    assert api_docs_enabled(configuration, env) is docs_enabled


def test_docs_enabled_reads_from_api_config():
    assert ApiConfiguration().docs_enabled is None
    assert (
        ApiConfiguration.model_validate({"docs_enabled": False}).docs_enabled is False
    )


def _app_with_route() -> FastAPI:
    app = FastAPI(title="Docs test", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return app


def test_app_without_docs_serves_none_of_the_pages():
    client = TestClient(_app_with_route())

    for path in DOC_PATHS:
        assert client.get(path).status_code == 404, path
    assert client.get("/ping").status_code == 200


def test_mount_api_docs_serves_schema_swagger_and_redoc():
    from naas_abi_core.apps.api.api import mount_api_docs

    app = _app_with_route()
    mount_api_docs(app, title="Docs test", favicon_url="/static/favicon.ico")
    client = TestClient(app)

    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    body = schema.json()
    assert "openapi" in body
    assert "/ping" in body["paths"]
    # The doc routes themselves stay out of the schema.
    assert not any(path in body["paths"] for path in DOC_PATHS)

    for path in ("/docs", "/redoc"):
        page = client.get(path)
        assert page.status_code == 200, path
        assert "/openapi.json" in page.text
        assert "/static/favicon.ico" in page.text


def test_schema_behind_api_key_when_pages_are_off(monkeypatch):
    from fastapi import Depends
    from naas_abi_core.apps.api.api import is_token_valid, mount_openapi_schema

    monkeypatch.setenv("ABI_API_KEY", "test-key")
    app = _app_with_route()
    mount_openapi_schema(app, dependencies=[Depends(is_token_valid)])
    client = TestClient(app)

    assert client.get("/openapi.json").status_code == 401
    assert (
        client.get(
            "/openapi.json", headers={"Authorization": "Bearer wrong"}
        ).status_code
        == 401
    )
    schema = client.get("/openapi.json", headers={"Authorization": "Bearer test-key"})
    assert schema.status_code == 200
    assert "/ping" in schema.json()["paths"]
    for path in ("/docs", "/redoc"):
        assert client.get(path).status_code == 404, path
