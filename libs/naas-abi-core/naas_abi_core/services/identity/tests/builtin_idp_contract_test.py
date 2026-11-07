"""The generic identity suite against the built-in IdP (``naas-abi-idp``)."""

import pytest

pytest.importorskip("naas_abi_idp")

from naas_abi_core.services.identity.tests.builtin_idp_server import (
    BuiltinIdPHarness,
)
from naas_abi_core.services.identity.tests.identity_contract import (
    IdentityProviderContract,
)


class TestBuiltinIdP(IdentityProviderContract):
    @pytest.fixture(scope="class")
    def harness(self):
        with BuiltinIdPHarness() as idp:
            yield idp
