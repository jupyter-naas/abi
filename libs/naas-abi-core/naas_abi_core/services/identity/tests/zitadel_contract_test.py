"""The generic identity suite against Zitadel, from its pinned native binary.

Skipped when the binaries cannot be had here (an unsupported platform, no
network); ``ABI_REQUIRE_ZITADEL=1`` (CI) turns that skip into a failure.
"""

import os

import pytest

from naas_abi_core.services.identity.tests.identity_contract import (
    IdentityProviderContract,
)
from naas_abi_core.services.identity.tests.zitadel_server import (
    BinariesUnavailable,
    ZitadelHarness,
    ZitadelServer,
)

pytestmark = pytest.mark.integration


def zitadel_or_skip() -> ZitadelServer:
    try:
        return ZitadelServer().start()
    except BinariesUnavailable as exc:
        if os.environ.get("ABI_REQUIRE_ZITADEL") == "1":
            raise
        pytest.skip(f"Zitadel is not available: {exc}")


class TestZitadel(IdentityProviderContract):
    @pytest.fixture(scope="class")
    def harness(self):
        server = zitadel_or_skip()
        try:
            yield ZitadelHarness(server)
        finally:
            server.stop()
