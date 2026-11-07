"""The generic identity suite against the in-process fake provider."""

import pytest

from naas_abi_core.services.identity.tests.fake_idp import FakeIdP
from naas_abi_core.services.identity.tests.identity_contract import (
    IdentityProviderContract,
)


class TestFakeIdP(IdentityProviderContract):
    @pytest.fixture(scope="class")
    def harness(self):
        with FakeIdP() as idp:
            yield idp
