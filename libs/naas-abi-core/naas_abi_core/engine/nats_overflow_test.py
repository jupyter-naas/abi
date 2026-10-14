import asyncio
from types import SimpleNamespace

import pytest
from naas_abi_core.engine import nats_overflow
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    issue_service_token,
    verify_service_token,
)
from naas_abi_core.engine.nats_overflow import OverflowHost
from naas_abi_core.engine.nats_transfer import OPERATIONS, TransferError
from naas_abi_proto.transfer.v1 import transfer_pb2 as pb

SECRET = "overflow-test-secret-at-least-32-bytes"


def headers(identity="caller"):
    return {"Nats-Auth-Token": issue_service_token(identity, SECRET)}


class LoopbackNC:
    """A connection whose overflow subjects reach the host, as over the broker."""

    max_payload = 64 * 1024

    def __init__(self, host):
        self.host = host
        self.subjects = []

    async def request(self, subject, payload, headers=None, timeout=None):
        self.subjects.append(subject)
        operation = subject.rsplit(".", 1)[1]
        request = OPERATIONS[operation][0].FromString(payload)
        response = OPERATIONS[operation][1]()
        try:
            caller = verify_service_token(headers["Nats-Auth-Token"], SECRET)
            response = await self.host._execute(operation, request, caller, headers)
        except TransferError as exc:
            response.error.code, response.error.message = exc.code, str(exc)
        return SimpleNamespace(data=response.SerializeToString(), headers=None)


async def read_all(host, transfer_id, caller):
    data, sequence = bytearray(), 0
    while True:
        reply = await host._execute(
            "read", pb.ReadRequest(id=transfer_id, sequence=sequence), caller
        )
        if reply.done:
            return bytes(data)
        if reply.pending:
            await asyncio.sleep(0.01)
            continue
        data.extend(reply.data)
        sequence += 1


def test_a_parked_reply_is_read_by_its_caller_only_then_released():
    async def scenario():
        host = OverflowHost(SECRET, chunk_bytes=1024)
        reply = bytes(range(256)) * 20

        transfer_id = await host.park(headers("caller"), reply)

        assert host.parked_bytes == len(reply)
        with pytest.raises(TransferError, match="another caller"):
            await host._execute("read", pb.ReadRequest(id=transfer_id), "someone-else")
        assert await read_all(host, transfer_id, "caller") == reply
        await host._execute("close", pb.CloseRequest(id=transfer_id), "caller")
        assert host.parked_bytes == 0
        await host.stop()

    asyncio.run(scenario())


def test_parking_respects_the_value_cap_the_memory_budget_and_capacity():
    async def scenario():
        host = OverflowHost(
            SECRET, max_value_bytes=10, max_parked_bytes=15, max_sessions=2
        )

        with pytest.raises(TransferError) as too_large:
            await host.park(headers(), b"x" * 11)
        await host.park(headers(), b"x" * 10)
        with pytest.raises(TransferError) as over_budget:
            await host.park(headers(), b"x" * 6)
        await host.park(headers(), b"x" * 5)
        with pytest.raises(TransferError) as at_capacity:
            await host.park(headers(), b"x")

        assert too_large.value.code == "PAYLOAD_TOO_LARGE"
        assert over_budget.value.code == at_capacity.value.code == "RESOURCE_EXHAUSTED"
        await host.stop()
        assert host.parked_bytes == 0

    asyncio.run(scenario())


def test_an_abandoned_parked_reply_expires_and_frees_its_budget():
    async def scenario():
        host = OverflowHost(SECRET, idle_seconds=0.05)
        host.reaper = asyncio.create_task(host._expire())
        await host.park(headers(), b"never read")
        await asyncio.sleep(1.2)
        assert host.sessions == {} and host.parked_bytes == 0
        await host.stop()

    asyncio.run(scenario())


def test_an_invalid_token_cannot_park():
    async def scenario():
        host = OverflowHost(SECRET)
        with pytest.raises(InvalidServiceTokenError):
            await host.park({"Nats-Auth-Token": "forged"}, b"reply")
        assert host.sessions == {}

    asyncio.run(scenario())


def test_the_service_reads_an_upload_with_the_callers_token_then_closes_it():
    async def scenario():
        host = OverflowHost(SECRET, chunk_bytes=1024)
        host._nc = LoopbackNC(host)
        request = bytes(range(256)) * 30
        opened = await host._execute(
            "open", pb.OpenRequest(operation="request"), "caller"
        )
        for sequence, offset in enumerate(range(0, len(request), opened.chunk_bytes)):
            await host._execute(
                "write",
                pb.WriteRequest(
                    id=opened.id,
                    sequence=sequence,
                    data=request[offset : offset + opened.chunk_bytes],
                ),
                "caller",
            )

        assert await host.fetch(opened.id, headers("caller")) == request
        assert host.sessions == {}  # consumed: the caller's own close is a no-op
        with pytest.raises(TransferError, match="another caller"):
            other = await host._execute(
                "open", pb.OpenRequest(operation="request"), "caller"
            )
            await host.fetch(other.id, headers("someone-else"))
        await host.stop()

    asyncio.run(scenario())


def test_the_process_host_is_installed_and_removed():
    host = OverflowHost(SECRET)
    nats_overflow.install(host)
    try:
        assert nats_overflow.current() is host
    finally:
        nats_overflow.uninstall(host)
    assert nats_overflow.current() is None
