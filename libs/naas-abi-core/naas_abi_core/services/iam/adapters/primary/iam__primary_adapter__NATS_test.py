"""The SDK's ``engine.services.iam`` against the engine's IAM, over a real broker."""

from __future__ import annotations

import asyncio

import pytest
from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    as_service_account,
    use_call_context,
)
from naas_abi_core.engine.nats_rpc_integration_test import (  # noqa: F401 - pytest fixture
    SECRET,
    broker,
)
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.adapters.primary.iam__primary_adapter__NATS import (
    IAMPrimaryAdapterNATS,
)
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.tests.iam_harness import document, statement

pytestmark = pytest.mark.integration
naas_abi_sdk = pytest.importorskip("naas_abi_sdk")

GRAPH = "abi:org-1:ws-1:triple_store:graph/g"


@pytest.mark.parametrize("broker", [1024 * 1024], indirect=True)
def test_sdk_modules_reach_iam_over_nats(broker):  # noqa: F811 - imported fixture
    from naas_abi_sdk.client import ABIClient
    from naas_abi_sdk.module import ModuleDependencies, ServicesProxy
    from naas_abi_sdk.services.errors import Conflict, NotFound, PermissionDenied

    url, _ = broker
    service = IAMService(IAMStoreMemory())
    service.bootstrap()
    # The module's account, with its manifest approved: its own collections.
    with as_service_account("engine"):
        account = service.create_service_account("module/acme/people")
    with use_call_context(
        CallContext(principal=Principal(account.id, "service_account", account.name))
    ):
        service.submit_manifest(
            "people",
            "acme",
            document(
                statement(
                    "Allow",
                    ["document:*"],
                    ["abi:-:-:document:collection/${module.id}/*"],
                )
            ),
        )
    with as_service_account("engine"):
        service.approve_manifest(account.id)

    async def scenario():
        import nats

        nc = await nats.connect(url)
        primary = IAMPrimaryAdapterNATS(service, SECRET)
        await primary.start(nc)
        engine = ABIClient(url, TEST_TOKENS.token("engine"))
        module = ABIClient(
            url, TEST_TOKENS.token("module/acme/people", subject=account.id)
        )
        try:
            # An administrator (the engine's policy) sets things up.
            admin = ServicesProxy(engine, ModuleDependencies(), "admin").iam
            bob = await admin.ensure_user("https://idp.example", "bob")
            policy = await admin.create_policy(
                "read graphs",
                document(
                    statement("Allow", ["iam:GetPolicy"], ["*"], sid="ReadPolicies")
                ),
            )
            assert policy["document"]["statements"][0]["sid"] == "ReadPolicies"
            attachment = await admin.attach_policy(
                roles.VIEWER, bob["id"], "abi:org-1:ws-1"
            )
            assert attachment["scope"] == "abi:org-1:ws-1"
            explanation = await admin.explain(
                "iam:ListAttachments",
                f"abi:org-1:ws-1:iam:attachment/x/{bob['id']}",
                principal_id=bob["id"],
            )
            assert explanation["allowed"] and explanation["statement"]["policy_id"] == (
                roles.VIEWER
            )
            with pytest.raises(Conflict):
                await admin.delete_policy(roles.VIEWER)

            # A module asks about itself: its own namespaces, not another's.
            iam = ServicesProxy(module, ModuleDependencies(), "people").iam
            own = "abi:-:-:document:collection/people/contacts"
            other = "abi:-:-:document:collection/billing/invoices"
            assert (await iam.authorize("document:Find", own)).allowed
            assert not (await iam.authorize("document:Find", other)).allowed
            assert (await iam.filter("document:Find", [other, own])).allowed == [own]
            with pytest.raises(NotFound):
                await iam.require("document:Find", other)
            # IAM's own operations need iam:* actions the module lacks.
            with pytest.raises(NotFound):
                await iam.create_policy(
                    "mine", document(statement("Allow", ["*"], ["*"]))
                )
            with pytest.raises((NotFound, PermissionDenied)):
                await iam.attach_policy(roles.PLATFORM_ADMIN, bob["id"])
        finally:
            await engine.close()
            await module.close()
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())
