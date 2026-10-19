"""``provisioning: zitadel`` against Zitadel, from its pinned native binary.

Skipped when the binaries cannot be had here (an unsupported platform, no
network); ``ABI_REQUIRE_ZITADEL=1`` (CI) turns that skip into a failure.
"""

from __future__ import annotations

import secrets

import pytest

from naas_abi_core.engine.engine_configuration.EngineConfiguration_Identity import (
    IdentityConfiguration,
)
from naas_abi_core.services.identity.adapters.secondary.AdminHttp import AdminHttp
from naas_abi_core.services.identity.adapters.secondary.ProvisioningZitadel import (
    ProvisioningZitadel,
)
from naas_abi_core.services.identity.IdentityPorts import ProvisioningError
from naas_abi_core.services.identity.tests.zitadel_contract_test import zitadel_or_skip

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def zitadel():
    server = zitadel_or_skip()
    try:
        yield server
    finally:
        server.stop()


def adapter(server, token: str | None = None) -> ProvisioningZitadel:
    bearer = {"Authorization": f"Bearer {token or server.admin_token}"}
    return ProvisioningZitadel(
        "zitadel", AdminHttp(server.issuer, headers=lambda: bearer)
    )


def email() -> str:
    return f"invitee-{secrets.token_hex(4)}@example.com"


def test_an_invited_person_is_created_once(zitadel):
    provisioning = adapter(zitadel)
    address = email()
    assert provisioning.find_user(address) is None
    created = provisioning.ensure_user(address, name="Bob Builder")
    assert created.created is True and created.provider == "zitadel"
    assert created.email == address and created.subject
    again = provisioning.ensure_user(address.upper())
    assert again.created is False and again.subject == created.subject
    found = provisioning.find_user(address)
    assert found is not None and found.subject == created.subject
    assert found.name == "Bob Builder" and found.disabled is False


def test_the_user_is_the_one_zitadel_knows(zitadel):
    provisioning = adapter(zitadel)
    created = provisioning.ensure_user(email())
    user = zitadel.api("GET", f"/v2/users/{created.subject}")["user"]
    assert user["userId"] == created.subject
    # The address is verified by whoever receives Zitadel's code, not asserted.
    assert user["human"]["email"].get("isVerified", False) is False


def test_a_name_may_be_a_single_word(zitadel):
    provisioning = adapter(zitadel)
    assert provisioning.ensure_user(email(), name="Cher").created is True


def test_a_token_zitadel_refuses_is_a_provisioning_error(zitadel):
    with pytest.raises(ProvisioningError):
        adapter(zitadel, token="not-a-token").ensure_user(email())


def test_an_address_zitadel_will_not_take_is_a_value_error(zitadel):
    with pytest.raises((ValueError, ProvisioningError)):
        adapter(zitadel).ensure_user("not an address")


def test_configured_from_the_engine_configuration(zitadel):
    configuration = IdentityConfiguration.model_validate(
        {
            "providers": [
                {
                    "name": "zitadel",
                    "issuer": zitadel.issuer,
                    "client_id": "abi",
                    "provisioning": "zitadel",
                    "admin": {"token": zitadel.admin_token},
                }
            ]
        }
    )
    from naas_abi_core.engine.call_context import as_service_account
    from naas_abi_core.services.identity.tests.identity_contract import bootstrapped_iam

    service = configuration.load(bootstrapped_iam())
    with as_service_account("engine"):
        user = service.provision_user(
            "zitadel", f" {email().title()} ", name="Eve Adams"
        )
        assert user.created and user.subject
        again = service.provision_user("zitadel", user.email)
        assert again.created is False and again.subject == user.subject
