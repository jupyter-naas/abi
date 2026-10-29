"""A remote module's lister, asked over NATS for IAM's listing as the caller."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi_core.engine import nats_runtime
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.engine.nats_rpc_integration_test import (  # noqa: F401 - pytest fixture
    broker,
)
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.adapters.secondary.listers__nats import (
    ListerInstance,
    NATSModuleListers,
)
from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.tests.iam_harness import (
    NEXUS,
    IAMHarness,
    name_in,
    statement,
    workspace,
)

pytest.importorskip("naas_abi_sdk")

BROKER = pytest.mark.parametrize("broker", [1024 * 1024], indirect=True)
WS1, WS2 = workspace("ws-1"), workspace("ws-2")
RESEARCH = ActionCatalog(
    service="demo_research",
    version=1,
    module="demo.research",
    resource_types=(ResourceType("brief", id="path", module_scope=True),),
    actions=(
        ActionSpec("ListBriefs", "list", ("brief",)),
        ActionSpec("ExportBrief", "read", ("brief",)),
    ),
)


def _brief(where: str, name: str):
    from naas_abi_sdk.listers import Listed

    return Listed(
        name_in(where, f"demo_research:brief/{name}"), name, label=name.upper()
    )


@pytest.fixture
def world(broker):  # noqa: F811 - imported pytest fixture
    from naas_abi_sdk.listers import ListerHost

    url, _ = broker
    iam = IAMService(IAMStoreMemory())
    iam.bootstrap()
    iam._register_catalog(NEXUS)
    with as_service_account("engine"):
        iam.register_catalog(RESEARCH)
    h = IAMHarness(iam)
    h.register("ws-1")
    h.register("ws-2")
    calls: list[str] = []

    def briefs(query):
        calls.append(query.container)
        if query.text == "boom":
            raise RuntimeError("the module's store is down")
        return [_brief(WS1, "q1"), _brief(WS1, "q2"), _brief(WS2, "q3")]

    connection = nats_runtime.get_connection(url)
    session = SimpleNamespace(
        client=SimpleNamespace(
            project="acme",
            transport=SimpleNamespace(connect=AsyncMock(return_value=connection)),
        ),
        service_account="01SA",
        instance_id="i-1",
    )
    host = ListerHost(session, "demo_research", {"brief": briefs})
    nats_runtime.run_coro(host.start())
    ready = [ListerInstance("demo.research", "01SA", "i-1", frozenset({"brief"}))]

    async def instances():
        return list(ready)

    directory = NATSModuleListers(
        nats_url=url,
        project="acme",
        token=lambda: "engine-token",
        host_token=lambda recipient: f"host-token-{recipient}",
        instances=instances,
    )
    iam.remote_listers = directory
    try:
        yield SimpleNamespace(h=h, ready=ready, calls=calls)
    finally:
        directory.close()
        nats_runtime.run_coro(host.close())
        nats_runtime.close()


@BROKER
def test_a_remote_modules_lister_is_asked_and_filtered_as_the_caller(world):
    h = world.h
    bob, stranger = h.user("bob"), h.user("stranger")
    h.grant(bob.id, statement("Allow", ["demo_research:ListBriefs"], [WS1 + "/*"]))
    with h.as_(bob):
        page = h.iam.list_resources("demo_research", "brief", scope=WS1)
        assert page.listed
        assert [(i.id, i.label) for i in page.items] == [("q1", "Q1"), ("q2", "Q2")]
        # Another workspace's: the module knows it, bob may not list it.
        assert h.iam.list_resources("demo_research", "brief", scope=WS2).items == ()
    with h.as_(stranger):
        page = h.iam.list_resources("demo_research", "brief", scope=WS1)
        assert page.listed and page.items == ()
    assert world.calls[0] == WS1


@BROKER
def test_a_remote_lister_that_fails_or_is_gone_offers_wildcards(world):
    h = world.h
    with as_service_account("engine"):
        failed = h.iam.list_resources("demo_research", "brief", scope=WS1, text="boom")
        assert failed.listed is False and failed.items == ()
        world.ready.clear()
        gone = h.iam.list_resources("demo_research", "brief", scope=WS1)
        assert gone.listed is False
