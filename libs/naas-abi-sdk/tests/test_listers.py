import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.discovery.v1 import discovery_pb2 as pb

from naas_abi_sdk.discovery import module_descriptor
from naas_abi_sdk.listers import (
    Listed,
    ListerHost,
    ListerQuery,
    check_listers,
    declared_listers,
    lister,
    lister_subject,
    page,
    run_lister,
)
from naas_abi_sdk.module import BaseModule

WS = "abi:nexus:organization/o-1/nexus:workspace/w-1"


def brief(name: str, where: str = WS) -> Listed:
    return Listed(f"{where}/demo_research:brief/{name}", name, label=name.title())


class Research(BaseModule):
    module_id = "demo.research"
    iam_catalog = {
        "resource_types": [{"name": "brief", "id": "path"}],
        "actions": [{"name": "ExportBrief", "level": "read", "resource_types": ["brief"]}],
    }

    @lister("brief")
    async def briefs(self, query: ListerQuery):
        assert query.service == "demo_research"
        return [brief("q3"), brief("q1"), brief("q2", "abi:nexus:workspace/w-9")]


def run(coroutine):
    return asyncio.run(coroutine)


def test_a_module_names_its_listers_in_its_descriptor():
    assert set(declared_listers(Research)) == {"brief"}
    descriptor = module_descriptor(Research, "demo.research", ())
    assert list(descriptor.listers) == ["brief"]
    module = Research.__new__(Research)
    module.__dict__["_lister_handlers"] = {}
    Research.expose_lister(module, "note", lambda query: [])
    assert set(declared_listers(module)) == {"brief", "note"}
    with pytest.raises(ValueError, match="already registered"):
        Research.expose_lister(module, "note", lambda query: [])


def test_a_lister_lists_a_type_of_the_catalog_only():
    check_listers(["brief"], Research.iam_catalog)
    with pytest.raises(ValueError, match="does not declare"):
        check_listers(["deal"], Research.iam_catalog)
    with pytest.raises(ValueError):
        check_listers(["brief"], None)


def test_a_page_is_in_the_container_sorted_after_the_name_and_searched():
    items = [brief("q3"), brief("q1"), brief("q2", "abi:nexus:workspace/w-9")]
    found = page(items, pb.ListerQuery(container=WS, limit=1))
    assert [i.id for i in found.items] == ["q1"] and found.more
    found = page(items, pb.ListerQuery(container=WS, after=brief("q1").name))
    assert [i.id for i in found.items] == ["q3"] and not found.more
    assert [i.id for i in page(items, pb.ListerQuery(container="abi:", text="Q2")).items] == [
        "q2"
    ]


def test_run_lister_answers_with_the_lister_or_an_error():
    module = Research.__new__(Research)
    handlers = declared_listers(module)
    query = pb.ListerQuery(service="demo_research", type="brief", container=WS)
    answer = run(run_lister(handlers, "demo_research", query))
    assert [i.label for i in answer.items] == ["Q1", "Q3"] and not answer.error.code
    other = pb.ListerQuery(service="demo_research", type="deal", container=WS)
    assert run(run_lister(handlers, "demo_research", other)).error.code == "NOT_FOUND"
    assert run(run_lister(handlers, "acme", query)).error.code == "NOT_FOUND"

    def broken(query):
        raise RuntimeError("down")

    assert run(run_lister({"brief": broken}, "demo_research", query)).error.code == (
        "LISTER_ERROR"
    )
    assert run(
        run_lister({"brief": lambda query: ["not listed"]}, "demo_research", query)
    ).error.code == "LISTER_ERROR"


def test_the_host_answers_on_its_instance_subject():
    async def scenario():
        nc = AsyncMock()
        session = SimpleNamespace(
            client=SimpleNamespace(
                project="acme", transport=SimpleNamespace(connect=AsyncMock(return_value=nc))
            ),
            service_account="01SA",
            instance_id="i-1",
        )
        module = Research.__new__(Research)
        host = ListerHost(session, "demo_research", declared_listers(module))
        await host.start()
        subject = nc.subscribe.call_args.args[0]
        assert subject == lister_subject("acme", "01SA", "i-1")
        assert subject == "abi.mod.acme.01SA.i-1.iam.list"
        replies = []
        msg = SimpleNamespace(
            data=pb.ListerQuery(
                service="demo_research", type="brief", container=WS
            ).SerializeToString(),
            reply="_INBOX.x",
            headers=None,
            _client=SimpleNamespace(publish=AsyncMock()),
        )

        async def fake_reply(message, data):
            replies.append(pb.ListerPage.FromString(data))

        import naas_abi_sdk.messages as messages

        original = messages.reply
        messages.reply = fake_reply
        try:
            await host._handle(msg)
            await host._handle(SimpleNamespace(data=b"\xff\xff", reply="_INBOX.y", headers=None))
        finally:
            messages.reply = original
        assert [i.id for i in replies[0].items] == ["q1", "q3"]
        assert replies[1].error.code == "INVALID_ARGUMENT"
        await host.close()

    run(scenario())
