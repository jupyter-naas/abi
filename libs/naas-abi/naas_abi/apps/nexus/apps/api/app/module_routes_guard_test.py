"""The engine guards what modules mount on its API (``mount_module_apis``);
the Nexus API, mounted by the ``naas_abi`` module, checks its callers itself
and stays reachable as Nexus decides: sign-in pages open, protected routes on
Nexus's own credentials."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi import ABIModule, NexusConfig
from naas_abi_core.apps.api.module_routes import mount_module_apis

GUARD_REFUSAL = {"detail": "Invalid authentication credentials"}


def test_the_nexus_api_keeps_its_own_caller_checks(monkeypatch) -> None:
    monkeypatch.setenv("ABI_API_KEY", "deployment-key")
    config = SimpleNamespace(configuration=SimpleNamespace(nexus_config=NexusConfig()))
    with patch.object(ABIModule, "get_instance", return_value=config):
        from naas_abi.apps.nexus.apps.api.app import main

        # What ``naas_abi``'s api(app) mounts, with the module's own opt-out.
        nexus = SimpleNamespace(
            api=main._register_routes,
            api_checks_its_callers=ABIModule.api_checks_its_callers,
            unguarded_api_paths=ABIModule.unguarded_api_paths,
        )
        app = FastAPI()
        guarded = mount_module_apis(app, [nexus])

    assert ABIModule.api_checks_its_callers is True
    assert guarded == []
    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/health").status_code == 200
    # A sign-in route and a protected route answer as Nexus decides: never the
    # engine guard's refusal.
    for method, path, headers in (
        ("GET", "/api/auth/oidc/providers", {}),
        ("GET", "/api/workspaces", {"Authorization": "Bearer abi_pk_example_secret"}),
    ):
        response = client.request(method, path, headers=headers)
        assert not (response.status_code == 401 and response.json() == GUARD_REFUSAL)
