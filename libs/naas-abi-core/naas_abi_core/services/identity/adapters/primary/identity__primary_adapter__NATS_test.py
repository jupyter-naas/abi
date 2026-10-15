"""Identity over a real broker: a client engine and an SDK module reach it."""

from __future__ import annotations

import asyncio
from urllib.parse import parse_qs, urlsplit

import pytest

from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.engine.nats_rpc_integration_test import (  # noqa: F401 - pytest fixture
    SECRET,
    broker,
)
from naas_abi_core.services.identity.adapters.primary.identity__primary_adapter__NATS import (
    IdentityPrimaryAdapterNATS,
)
from naas_abi_core.services.identity.adapters.secondary.IdentitySecondaryAdapterNATSClient import (
    IdentitySecondaryAdapterNATSClient,
)
from naas_abi_core.services.identity.IdentityPorts import (
    TokenRejectedError,
    UnknownProviderError,
)
from naas_abi_core.services.identity.tests.fake_idp import FakeIdP
from naas_abi_core.services.identity.tests.identity_contract import (
    Pkce,
    bootstrapped_iam,
    identity_service,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("broker", [1024 * 1024], indirect=True)
def test_a_client_engine_signs_users_in_through_the_serving_engine(broker):  # noqa: F811
    url, _ = broker
    with FakeIdP() as idp:
        iam = bootstrapped_iam()
        service = identity_service(idp, iam)

        async def scenario():
            import nats

            nc = await nats.connect(url)
            primary = IdentityPrimaryAdapterNATS(service, SECRET)
            await primary.start(nc)
            api = IdentitySecondaryAdapterNATSClient(url, SECRET, "api")
            module = IdentitySecondaryAdapterNATSClient(url, SECRET, "people")
            try:
                providers = await asyncio.to_thread(api.list_providers)
                assert [p.name for p in providers] == ["fake"]
                assert "secret" not in repr(providers)

                pkce = Pkce.new()
                authorize = await asyncio.to_thread(
                    lambda: api.authorization_url(
                        "fake",
                        redirect_uri=idp.redirect_uri,
                        state=pkce.state,
                        nonce=pkce.nonce,
                        code_challenge=pkce.challenge,
                    )
                )
                user = idp.create_user("alice@abi.test")
                callback = await asyncio.to_thread(idp.sign_in, authorize, user)
                code = parse_qs(urlsplit(callback).query)["code"][0]
                signed_in = await asyncio.to_thread(
                    lambda: api.exchange_code(
                        "fake",
                        code=code,
                        code_verifier=pkce.verifier,
                        redirect_uri=idp.redirect_uri,
                        nonce=pkce.nonce,
                    )
                )
                record = iam.store.find_user(idp.issuer, user.subject)
                assert record is not None
                assert signed_in.user.principal_id == record.id
                assert signed_in.tokens.refresh_token

                # A refused token keeps its reason across the wire.
                other = idp.issue_id_token(user.subject, audience="someone-else")
                with pytest.raises(TokenRejectedError) as refused:
                    await asyncio.to_thread(api.verify_token, other)
                assert refused.value.reason == "wrong_audience"

                # A module with no identity grant sees no provider at all.
                assert await asyncio.to_thread(module.list_providers) == []
                with pytest.raises(UnknownProviderError):
                    await asyncio.to_thread(
                        module.authenticate, signed_in.tokens.id_token or ""
                    )
            finally:
                api.close()
                module.close()
                await primary.stop()
                await nc.close()

        asyncio.run(scenario())


@pytest.mark.parametrize("broker", [1024 * 1024], indirect=True)
def test_sdk_modules_reach_identity_over_nats(broker):  # noqa: F811
    naas_abi_sdk = pytest.importorskip("naas_abi_sdk")
    del naas_abi_sdk
    from naas_abi_sdk.client import ABIClient
    from naas_abi_sdk.module import ModuleDependencies, ServicesProxy
    from naas_abi_sdk.services.errors import NotFound, TokenRejected

    url, _ = broker
    with FakeIdP() as idp:
        iam = bootstrapped_iam()
        service = identity_service(idp, iam)

        async def scenario():
            import nats

            nc = await nats.connect(url)
            primary = IdentityPrimaryAdapterNATS(service, SECRET)
            await primary.start(nc)
            client = ABIClient(url, issue_service_token("people", SECRET))
            try:
                identity = ServicesProxy(
                    client, ModuleDependencies(services=("identity",)), "people"
                ).identity
                listed = await identity.list_providers()
                assert listed["providers"] == []
                token = idp.issue_id_token(idp.create_user("bob@abi.test").subject)
                with pytest.raises(NotFound):
                    await identity.authenticate(token)
                expired = idp.issue_id_token("x", issued_at=0, lifetime=60)
                with pytest.raises((NotFound, TokenRejected)):
                    await identity.verify_token(expired)
            finally:
                await client.close()
                await primary.stop()
                await nc.close()

        asyncio.run(scenario())
