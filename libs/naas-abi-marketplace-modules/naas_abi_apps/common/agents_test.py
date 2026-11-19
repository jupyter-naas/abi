"""``read_secrets`` reads a module's secrets under its own prefix, as the
engine allows a module account (``module/<project>/<module id>``)."""

from __future__ import annotations

import asyncio

from naas_abi_apps.common.agents import read_secrets, secret_key
from naas_abi_apps.common.testing import fake_engine


def test_secrets_are_read_under_the_module_prefix() -> None:
    engine = fake_engine({"applications.x/API_KEY": "k"})

    assert asyncio.run(
        read_secrets(engine, {"key": "API_KEY", "none": ""}, module_id="applications.x")
    ) == {"key": "k", "none": ""}
    assert secret_key("applications.x", "applications.x/API_KEY") == (
        "applications.x/API_KEY"
    )


def test_a_refused_secret_reads_as_missing() -> None:
    class Refusing:
        async def get(self, key: str, default: object = None) -> object:
            from naas_abi_sdk.services.errors import PermissionDenied

            raise PermissionDenied(
                "PERMISSION_DENIED", "this secret is not the caller's"
            )

    engine = fake_engine()
    engine.services.secret = Refusing()

    assert asyncio.run(
        read_secrets(engine, {"key": "API_KEY"}, module_id="applications.x")
    ) == {"key": ""}
