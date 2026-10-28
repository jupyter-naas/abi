from __future__ import annotations

from types import SimpleNamespace

from naas_abi.apps.nexus.apps.api.app.services.apps.remote.factory import (
    build_remote_app_directory,
)


def test_the_directory_calls_modules_as_the_api_service_account_for_the_user(monkeypatch):
    """No shared secret signs anything here: the transports take the ``api``
    account's tokens from the engine, a delegation for the signed-in user, and a
    token addressed to one host for what is sent to a module."""
    from naas_abi.apps.nexus.apps.api.app.services import engine_credentials

    asked: list[tuple] = []

    class Credentials:
        def token(self) -> str:
            return "api-token"

        def token_for(self, user, recipient=None, scope=None) -> str:
            asked.append(("delegation", user, recipient))
            return "delegation"

    class Engine:
        def service_credentials(self, name, audience=None):
            asked.append(("credentials", name, audience))
            return Credentials()

    monkeypatch.setattr(
        "naas_abi.ABIModule.get_instance",
        staticmethod(lambda: SimpleNamespace(engine=Engine())),
    )
    nats = SimpleNamespace(
        nats_url="nats://localhost:4222",
        discovery=SimpleNamespace(project="demo"),
    )

    directory = build_remote_app_directory(nats)
    _discovery, transport, uploads, project = directory._factory()  # type: ignore[attr-defined]

    assert project == "demo"
    for held in (transport, uploads):
        assert callable(held.token) and held.token() == "api-token"
        assert held.delegate is not None and held.host_token is not None
    assert held.host_token("acme_research-1") == "api-token"
    assert ("credentials", "api", "abi:host:acme_research-1") in asked
    assert engine_credentials.CALLER_IDENTITY == "api"
