"""The whole Nexus application behind the view's middleware, over the test world of
``view_as_http_test``: the identity middleware, the guard and the activity log in the order
``main.py`` adds them, every real route, the test world's database and IAM.

Used by the tests of what a view shows (private content), writes (nothing) and records."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from naas_abi import ABIModule, NexusConfig
from naas_abi.apps.nexus.apps.api.app.services.identity_events.middleware import (
    RequestIdentityMiddleware,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as.adapters.primary.view_as__primary_adapter__ASGI import (  # noqa: E501
    ViewGuardMiddleware,
)


def build_full_app(*, activity_log: object | None = None) -> FastAPI:
    """``activity_log``: a service the HTTP activity log records into (main.py's place:
    inside identity, outside the guard)."""
    config = SimpleNamespace(configuration=SimpleNamespace(nexus_config=NexusConfig()))
    with patch.object(ABIModule, "get_instance", return_value=config):
        from naas_abi.apps.nexus.apps.api.app import main

        app = FastAPI()
        main._register_routes(app)
    # What main.py does: the guard in front of the routes, identity outermost.
    app.add_middleware(ViewGuardMiddleware)
    if activity_log is not None:
        from naas_abi.apps.nexus.apps.api.app.services.activity_log.HttpActivityLogMiddleware import (  # noqa: E501
            HttpActivityLogMiddleware,
        )

        app.state.activity_log_service = activity_log
        app.add_middleware(HttpActivityLogMiddleware)
    app.add_middleware(RequestIdentityMiddleware)
    return app


@contextmanager
def services_installed() -> Iterator[None]:
    """The services the routes take from the registry, over the test database."""
    from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry
    from naas_abi.apps.nexus.apps.api.app.services.registry_bootstrap import (
        initialize_nexus_service_registry,
    )

    previous = ServiceRegistry._instance
    ServiceRegistry._instance = None
    initialize_nexus_service_registry()
    try:
        yield
    finally:
        ServiceRegistry._instance = previous


@contextmanager
def engine_iam_installed(iam) -> Iterator[None]:
    """The world's IAM as the engine's, for what Nexus asks of it in process: personal
    keys and the links of apps."""
    from naas_abi.apps.nexus.apps.api.app.services.auth import credentials

    previous = credentials.configure_iam(lambda: iam)
    try:
        yield
    finally:
        credentials.configure_iam(previous)


def bind_database(monkeypatch) -> None:
    """Point every module that imported ``AsyncSessionLocal`` by name at the test database
    (``view_as_http_test.world`` replaced the one in ``core.database``): a module imported
    once keeps the sessionmaker of the first test that imported it."""
    import sys

    from naas_abi.apps.nexus.apps.api.app.core import database

    for name, module in list(sys.modules.items()):
        if name.startswith("naas_abi.apps.nexus") and hasattr(module, "AsyncSessionLocal"):
            monkeypatch.setattr(module, "AsyncSessionLocal", database.AsyncSessionLocal)
