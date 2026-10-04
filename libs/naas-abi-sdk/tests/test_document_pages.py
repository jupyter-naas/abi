"""Document pages bounded by size: max_bytes and cut pages."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.document.v1 import document_pb2 as pb
from naas_abi_proto.document.values import encode_data

from naas_abi_sdk.services import DocumentService

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc).isoformat()


def _doc(id: str) -> pb.Document:
    return pb.Document(
        id=id, data=encode_data({"n": 1}), created_at=NOW, updated_at=NOW, version=1
    )


def test_find_sends_max_bytes_and_a_short_page_keeps_its_cursor():
    client = AsyncMock()
    client.find.return_value = pb.FindResponse(items=[_doc("a")], cursor="next")
    service = DocumentService(client)

    page = asyncio.run(service.find("records", limit=10, max_bytes=4096))

    assert [d.id for d in page.items] == ["a"] and page.cursor == "next"
    assert client.find.call_args.args[0].max_bytes == 4096
    asyncio.run(service.find("records"))
    assert not client.find.call_args.args[0].HasField("max_bytes")


def test_iterate_follows_cut_pages_with_its_byte_budget():
    client = AsyncMock()
    client.find.side_effect = [
        pb.FindResponse(items=[_doc("a")], cursor="next"),  # cut short
        pb.FindResponse(items=[_doc("b"), _doc("c")]),
    ]
    service = DocumentService(client)

    async def scenario():
        return [d.id async for d in service.iterate("records", batch=10, max_bytes=100)]

    assert asyncio.run(scenario()) == ["a", "b", "c"]
    requests = [call.args[0] for call in client.find.call_args_list]
    assert [r.max_bytes for r in requests] == [100, 100]
    assert requests[1].cursor == "next"


@pytest.mark.parametrize("max_bytes", [0, -1, "1"])
def test_max_bytes_must_be_a_positive_integer(max_bytes):
    service = DocumentService(AsyncMock())

    with pytest.raises(ValueError):
        asyncio.run(service.find("records", max_bytes=max_bytes))
