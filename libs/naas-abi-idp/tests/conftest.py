"""Fixtures: the provider over in-memory adapters, and a controllable clock."""

from __future__ import annotations

import pytest

from naas_abi_idp.adapters.memory import (
    MemoryDocumentStore,
    MemoryMailer,
    MemorySecretStore,
)
from naas_abi_idp.configuration import ClientConfiguration, IdPConfiguration
from naas_abi_idp.service import IdPService

ISSUER = "http://localhost:9879/idp"
REDIRECT = "http://localhost:9879/api/auth/oidc/callback"


class Clock:
    def __init__(self, now: float = 1_800_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def mailer() -> MemoryMailer:
    return MemoryMailer()


@pytest.fixture
def configuration() -> IdPConfiguration:
    return IdPConfiguration(
        issuer=ISSUER,
        # Mail leaves synchronously here, so a test reads it at once; the
        # background default has its own tests (test_service.py).
        background_mail=False,
        clients=[
            ClientConfiguration(
                client_id="abi",
                secret="abi-secret-abi-secret",
                redirect_uris=[REDIRECT],
            ),
            ClientConfiguration(
                client_id="public-app",
                secret=None,
                redirect_uris=["http://localhost:3000/callback"],
            ),
            ClientConfiguration(
                client_id="robot",
                secret="robot-secret-robot-secret",
                grant_types=["client_credentials"],
                scopes=["jobs"],
            ),
        ],
    )


@pytest.fixture
def service(configuration, mailer, clock) -> IdPService:
    service = IdPService(
        MemoryDocumentStore(),
        MemorySecretStore(),
        mailer,
        configuration,
        clock=clock,
    )
    service.seed_clients(configuration.clients)
    return service
