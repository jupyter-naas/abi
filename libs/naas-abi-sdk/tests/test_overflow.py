import asyncio

import pytest
from naas_abi_proto.transfer.v1 import transfer_pb2 as pb
from overflow_fakes import OWNER, FakeHost

from naas_abi_sdk import overflow


def test_upload_writes_the_payload_in_negotiated_chunks():
    host = FakeHost(chunk_bytes=4)

    transfer_id = asyncio.run(overflow.upload(host.call, b"0123456789", chunk_bytes=64))

    assert bytes(host.uploads[transfer_id]) == b"0123456789"
    assert host.subjects[0] == "abi.rpc.overflow.open"
    assert host.subjects[1] == f"abi.rpc.overflow.{OWNER}.write"
    assert host.closed == []  # the service reads it; the caller closes after the call


def test_download_reassembles_the_reply_and_closes_the_session():
    host = FakeHost(parked=b"the whole reply", chunk_bytes=4, pending=2)

    data = asyncio.run(overflow.download(host.call, f"{OWNER}:7", 15))

    assert data == b"the whole reply"
    assert host.closed == [f"{OWNER}:7"]


def test_download_refuses_a_reply_that_does_not_match_its_announced_size():
    host = FakeHost(parked=b"longer than announced", chunk_bytes=4)

    with pytest.raises(overflow.OverflowRefused, match="announced"):
        asyncio.run(overflow.download(host.call, f"{OWNER}:1", 5))
    assert host.closed == [f"{OWNER}:1"]


def test_values_above_the_cap_are_refused_before_any_exchange(monkeypatch):
    monkeypatch.setattr(overflow, "MAX_VALUE_BYTES", 8)
    host = FakeHost(parked=b"x" * 9)

    with pytest.raises(overflow.OverflowRefused) as upload:
        asyncio.run(overflow.upload(host.call, b"x" * 9, chunk_bytes=4))
    with pytest.raises(overflow.OverflowRefused) as download:
        asyncio.run(overflow.download(host.call, f"{OWNER}:1", 9))

    assert upload.value.code == download.value.code == "PAYLOAD_TOO_LARGE"
    assert host.subjects == [
        f"abi.rpc.overflow.{OWNER}.close"
    ]  # the parked reply is released


def test_a_failed_upload_closes_its_session():
    host = FakeHost(chunk_bytes=4)
    original = host.call

    async def failing(subject, request, response_type):
        if isinstance(request, pb.WriteRequest) and request.sequence == 1:
            raise ConnectionError("lost")
        return await original(subject, request, response_type)

    with pytest.raises(ConnectionError):
        asyncio.run(overflow.upload(failing, b"0123456789", chunk_bytes=4))
    assert host.closed == [f"{OWNER}:0"]


def test_chunk_size_stays_under_half_the_broker_limit():
    assert overflow.chunk_size(8 * 1024 * 1024) == 1024 * 1024
    assert overflow.chunk_size(64 * 1024) == 32 * 1024


def test_overflow_needs_room_for_one_kibibyte_chunks():
    assert overflow.possible(2048) and not overflow.possible(2047)
