import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.document.v1 import document_pb2 as pb
from naas_abi_proto.document.values import decode_data, encode_data, encode_value

from naas_abi_sdk.document import DocumentClient


def test_lossless_values():
    values = {
        "integer": 2**63 - 1,
        "bytes": b"\x00\xff",
        "date": datetime.now(timezone.utc),
        "nested": [{"$t": "user"}, None, True, 1.25, []],
    }
    assert (
        decode_data(pb.Data.FromString(encode_data(values).SerializeToString()))
        == values
    )
    for invalid in (float("nan"), datetime(2026, 1, 1), 2**63, object(), "\x00"):  # noqa: DTZ001 - exercise naive-date rejection
        with pytest.raises((ValueError, OverflowError)):
            encode_value(invalid)


def test_scoped_client_preserves_request_and_rejects_rebinding():
    transport = AsyncMock()
    client = DocumentClient(transport).for_namespace("modules.writer")
    request = pb.GetRequest(collection="state", id="one")
    asyncio.run(client.get(request))
    sent = transport.call.call_args.args[1]
    assert sent.namespace == "modules.writer"
    assert request.namespace == ""
    with pytest.raises(ValueError):
        client.for_namespace("other")
    with pytest.raises(ValueError):
        asyncio.run(client.get(pb.GetRequest(namespace="other")))
