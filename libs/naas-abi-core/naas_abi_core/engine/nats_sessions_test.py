"""Sessions a serving engine owns: their owner id, and how they outlive a handover."""

import asyncio
from unittest.mock import MagicMock

import nats
import pytest
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.engine.nats_sessions import (
    ServicePrimary,
    SessionHost,
    owned_by,
    session_owner,
    stop_delivery,
    wait_for_sessions,
)
from naas_abi_core.engine.nats_test_server import native_nats_server, nats_server_binary
from naas_abi_core.engine.nats_tracing import add_traced_service
from naas_abi_core.engine.nats_transfer import TransferError, TransferHost
from naas_abi_proto.transfer.v1 import transfer_pb2 as pb
from naas_abi_sdk import no_responders
from naas_abi_sdk.transfer import Transfer, transfer_subject
from nats.errors import NoRespondersError
from nats.errors import TimeoutError as NATSTimeoutError

ENGINE = "0123456789abcdef0123456789abcdef"
SECRET = "sessions-test-secret-at-least-32-bytes"
PREFIX = "abi.svc.handover.v1.transfer"


async def no_frames(*args):
    if False:
        yield b""


# --- the owner id --------------------------------------------------------------------------


def test_session_hosts_built_for_an_engine_take_its_instance_id():
    from naas_abi_core.engine.nats_overflow import OverflowHost
    from naas_abi_core.services.model_registry.adapters.primary.model_registry_nats import (
        ModelRegistryNATS,
    )

    with owned_by(ENGINE):
        transfers = TransferHost("t", SECRET, no_frames, operations=("get",))
        overflow = OverflowHost(SECRET)
        models = ModelRegistryNATS(MagicMock(), SECRET)

    owners = {transfers.owner, overflow.owner, models.owner, models.transfer.owner}
    assert owners == {ENGINE}


def test_a_host_built_outside_an_engine_has_its_own_owner_id():
    one = TransferHost("t", SECRET, no_frames, operations=("get",))
    two = TransferHost("t", SECRET, no_frames, operations=("get",))

    assert one.owner != two.owner
    assert len(one.owner) == 32


def test_an_owner_id_is_one_the_transfer_subjects_accept():
    assert session_owner(ENGINE) == ENGINE
    assert transfer_subject(PREFIX, "read", f"{ENGINE}:x") == f"{PREFIX}.{ENGINE}.read"
    with pytest.raises(ValueError), owned_by("engine-1"):
        pass
    with pytest.raises(ValueError):
        TransferHost("t", SECRET, no_frames, operations=("get",), owner="ENGINE")


# --- the endpoints that own sessions -------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "naas_abi_core.engine.nats_transfer.TransferHost",
        "naas_abi_core.engine.nats_overflow.OverflowHost",
        "naas_abi_core.services.model_registry.adapters.primary.model_registry_nats.ModelRegistryNATS",
        "naas_abi_core.services.object_storage.adapters.primary.object_storage__primary_adapter__NATS.ObjectStoragePrimaryAdapterNATS",
        "naas_abi_core.services.dataset.adapters.primary.dataset__primary_adapter__NATS.DatasetPrimaryAdapterNATS",
        "naas_abi_core.services.triple_store.adapters.primary.triple_store__primary_adapter__NATS.TripleStorePrimaryAdapterNATS",
        "naas_abi_core.services.vector_store.adapters.primary.vector_store__primary_adapter__NATS.VectorStorePrimaryAdapterNATS",
        "naas_abi_core.services.activity_log.adapters.primary.activity_log__primary_adapter__NATS.ActivityLogPrimaryAdapterNATS",
        "naas_abi_core.services.event.adapters.primary.event__primary_adapter__NATS.EventPrimaryAdapterNATS",
    ],
)
def test_every_endpoint_with_sessions_hands_them_over(path):
    import importlib

    module, name = path.rsplit(".", 1)
    assert issubclass(getattr(importlib.import_module(module), name), SessionHost)


def kernel_primaries() -> list[str]:
    """Every kernel service's NATS primary adapter module, found on disk."""
    from pathlib import Path

    import naas_abi_core

    root = Path(naas_abi_core.__file__).parent
    return sorted(
        ".".join(path.relative_to(root.parent).with_suffix("").parts)
        for path in root.glob("services/*/*/primary/*__primary_adapter__NATS.py")
    )


def test_the_kernel_primaries_are_all_found():
    assert len(kernel_primaries()) >= 13


@pytest.mark.parametrize("module", kernel_primaries())
def test_every_kernel_primary_answers_the_calls_it_received_at_the_handover(module):
    import importlib

    primaries = [
        cls
        for name, cls in vars(importlib.import_module(module)).items()
        if name.endswith("PrimaryAdapterNATS") and cls.__module__ == module
    ]
    assert primaries
    for cls in primaries:
        assert issubclass(cls, ServicePrimary), cls.__name__


def test_a_service_primary_lets_the_calls_it_received_finish_before_it_stops():
    from unittest.mock import AsyncMock

    class Primary(ServicePrimary):
        def __init__(self) -> None:
            self._service = MagicMock(
                stop_accepting=AsyncMock(),
                requests_finished=AsyncMock(),
                stop=AsyncMock(),
            )
            self._dispatch = MagicMock()

    async def scenario():
        primary = Primary()
        service = primary._service

        await primary.stop_accepting()
        service.stop_accepting.assert_awaited_once()
        service.stop.assert_not_awaited()
        # Calls already received still run on the domain's workers.
        primary._dispatch.close.assert_not_called()

        await primary.sessions_finished()
        service.requests_finished.assert_awaited_once()

        await primary.stop()
        service.stop.assert_awaited_once()
        primary._dispatch.close.assert_called_once()

    asyncio.run(scenario())


def test_a_service_with_transfers_ends_its_endpoints_first_and_its_transfers_last():
    from unittest.mock import AsyncMock

    from naas_abi_core.engine.nats_transfer import ServiceWithTransfers

    order: list[str] = []

    def step(name):
        return AsyncMock(side_effect=lambda: order.append(name))

    class Primary(ServiceWithTransfers):
        def __init__(self) -> None:
            self._service = MagicMock(
                stop_accepting=step("endpoints stop accepting"),
                requests_finished=step("calls answered"),
                stop=step("endpoints stopped"),
            )
            self._transfer = MagicMock(
                stop_accepting=step("open stops accepting"),
                sessions_finished=step("transfers finished"),
                stop=step("transfers stopped"),
            )
            self._dispatch = MagicMock()

    async def scenario():
        primary = Primary()

        await primary.stop_accepting()
        # Calls and transfers already received still run on the domain's workers.
        primary._dispatch.close.assert_not_called()
        await primary.sessions_finished()
        await primary.stop()
        primary._dispatch.close.assert_called_once()

    asyncio.run(scenario())
    assert order == [
        "open stops accepting",
        "endpoints stop accepting",
        "calls answered",
        "transfers finished",
        "transfers stopped",
        "endpoints stopped",
    ]


# --- waiting for sessions ------------------------------------------------------------------


class Host(SessionHost):
    def __init__(self) -> None:
        self.finished = asyncio.Event()

    async def stop_accepting(self) -> None:
        pass

    async def sessions_finished(self) -> None:
        await self.finished.wait()

    async def stop(self) -> None:
        pass


def test_waiting_ends_once_every_host_has_no_session_left():
    async def scenario():
        one, two = Host(), Host()
        waiting = asyncio.create_task(wait_for_sessions([one, two], 5))
        one.finished.set()
        await asyncio.sleep(0.05)
        assert not waiting.done()
        two.finished.set()
        assert await asyncio.wait_for(waiting, 1) is True

    asyncio.run(scenario())


def test_waiting_stops_at_the_deadline():
    async def scenario():
        loop = asyncio.get_running_loop()
        started = loop.time()
        assert await wait_for_sessions([Host()], 0.2) is False
        assert 0.2 <= loop.time() - started < 1

    asyncio.run(scenario())


def test_without_hosts_or_time_there_is_nothing_to_wait_for():
    async def scenario():
        assert await wait_for_sessions([], 5) is True
        assert await wait_for_sessions([Host()], 0) is False

    asyncio.run(scenario())


def test_waiting_covers_a_session_opened_on_a_host_already_done():
    """A call answered during the wait may park its reply on another host (an
    overflowing reply): the caller still reads it."""

    async def scenario():
        overflow, calls = Host(), Host()
        overflow.finished.set()
        waiting = asyncio.create_task(wait_for_sessions([overflow, calls], 5))
        await asyncio.sleep(0.05)
        overflow.finished.clear()  # the call parks its reply...
        calls.finished.set()  # ...and is answered
        await asyncio.sleep(0.1)
        assert not waiting.done()
        overflow.finished.set()  # the caller has read it
        assert await asyncio.wait_for(waiting, 1) is True

    asyncio.run(scenario())


# --- a transfer at the handover, over a real broker ----------------------------------------


@pytest.fixture
def broker(tmp_path):
    if nats_server_binary() is None:
        pytest.skip("nats-server is not installed")
    with native_nats_server(tmp_path) as url:
        yield url


def caller(nc):
    headers = {"Nats-Auth-Token": issue_service_token("caller", SECRET)}

    async def call(subject, request, response_type):
        reply = await nc.request(
            subject, request.SerializeToString(), headers=headers, timeout=2
        )
        response = response_type.FromString(reply.data)
        if response.HasField("error"):
            raise TransferError(response.error.code, response.error.message)
        return response

    return call


async def open_transfer(call) -> Transfer:
    opened = await call(
        f"{PREFIX}.open", pb.OpenRequest(operation="get"), pb.OpenResponse
    )
    transfer = Transfer(call, PREFIX, opened.id, opened.chunk_bytes)
    await transfer.start()
    return transfer


def test_a_transfer_open_at_the_handover_finishes_on_its_engine(broker):
    async def scenario():
        gate = asyncio.Event()

        async def frames(operation, metadata, source):
            yield b"first"
            await gate.wait()
            yield b"last"

        old_nc, new_nc, client_nc = [await nats.connect(broker) for _ in range(3)]
        old = TransferHost(PREFIX, SECRET, frames, operations=("get",))
        new = TransferHost(PREFIX, SECRET, frames, operations=("get",))
        call = caller(client_nc)
        try:
            await old.start(old_nc)
            transfer = await open_transfer(call)
            fragments = transfer.fragments()
            assert (await anext(fragments))[0] == b"first"

            await old.stop_accepting()
            await new.start(new_nc)
            # New transfers reach the next engine...
            reopened = await open_transfer(call)
            assert reopened.id.startswith(f"{new.owner}:")
            # ...while the one already open goes on with the old engine.
            finishing = asyncio.create_task(old.sessions_finished())
            gate.set()
            assert [data async for data, _ in fragments] == [b"last"]
            await asyncio.sleep(0.2)
            assert not finishing.done()
            await call(
                transfer_subject(PREFIX, "close", transfer.id),
                pb.CloseRequest(id=transfer.id),
                pb.CloseResponse,
            )
            await asyncio.wait_for(finishing, 2)
        finally:
            await old.stop()
            await new.stop()
            for nc in (old_nc, new_nc, client_nc):
                await nc.close()

    asyncio.run(scenario())


def test_a_stuck_transfer_is_closed_at_the_drain_deadline(broker):
    async def scenario():
        async def frames(operation, metadata, source):
            yield b"first"
            await asyncio.Event().wait()  # never ends
            yield b"never"

        host_nc, client_nc = [await nats.connect(broker) for _ in range(2)]
        host = TransferHost(PREFIX, SECRET, frames, operations=("get",))
        call = caller(client_nc)
        try:
            await host.start(host_nc)
            transfer = await open_transfer(call)
            assert (await anext(transfer.fragments()))[0] == b"first"

            await host.stop_accepting()
            loop = asyncio.get_running_loop()
            started = loop.time()
            assert await wait_for_sessions([host], 0.3) is False
            assert 0.3 <= loop.time() - started < 1.5
            await host.stop()

            assert not host.sessions
            with pytest.raises(NoRespondersError):
                await call(
                    transfer_subject(PREFIX, "read", transfer.id),
                    pb.ReadRequest(id=transfer.id, sequence=1),
                    pb.ReadResponse,
                )
        finally:
            await host.stop()
            for nc in (host_nc, client_nc):
                await nc.close()

    asyncio.run(scenario())


# --- one-shot calls at the handover, over a real broker ------------------------------------

CALLS = "abi.svc.handover.v1.echo"


class SlowEcho(ServicePrimary):
    """A kernel primary with one one-shot endpoint, whose calls wait for ``gate``."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.gate = asyncio.Event()
        self.received: list[bytes] = []
        self.cancelled: list[bytes] = []
        self._service = None
        self._dispatch = MagicMock()

    async def start(self, nc) -> None:
        self._service = await add_traced_service(nc, name="handover", version="1.0.0")
        await self._service.add_endpoint(name="echo", subject=CALLS, handler=self._echo)
        await nc.flush()  # subscribed at the broker

    async def _echo(self, request) -> None:
        self.received.append(request.data)
        try:
            await self.gate.wait()
        except asyncio.CancelledError:
            self.cancelled.append(request.data)
            raise
        await request.respond(self.name.encode() + b":" + request.data)


async def soon(done) -> None:
    from naas_abi_core.engine.nats_sessions import until

    await asyncio.wait_for(until(done), 5)


def test_a_queue_member_drained_under_load_loses_no_request(broker):
    """``Subscription.drain`` alone loses one now and then: its PING goes first."""

    async def drain_once() -> int:
        old_nc, new_nc, client_nc = [await nats.connect(broker) for _ in range(3)]

        async def answer(msg):
            await msg.respond(b"ok")

        old = await old_nc.subscribe(CALLS, queue="q", cb=answer)
        await new_nc.subscribe(CALLS, queue="q", cb=answer)
        for nc in (old_nc, new_nc):
            await nc.flush()
        lost, sending = [], asyncio.Event()
        sending.set()

        async def send():
            while sending.is_set():
                try:
                    await client_nc.request(CALLS, b"x", timeout=5)
                except NATSTimeoutError:
                    lost.append(1)

        senders = [asyncio.create_task(send()) for _ in range(64)]
        await asyncio.sleep(0.2)
        await stop_delivery([old])
        await old.drain()
        await asyncio.sleep(0.2)
        sending.clear()
        await asyncio.gather(*senders)
        for nc in (old_nc, new_nc, client_nc):
            await nc.close()
        return len(lost)

    async def scenario():
        return [await drain_once() for _ in range(5)]

    assert asyncio.run(scenario()) == [0] * 5


def test_calls_received_before_the_handover_are_answered_and_new_ones_go_to_the_next_engine(
    broker,
):
    async def scenario():
        old_nc, new_nc, client_nc = [await nats.connect(broker) for _ in range(3)]
        old, new = SlowEcho("old"), SlowEcho("new")
        new.gate.set()
        try:
            await old.start(old_nc)
            # One call is being handled, the next one is delivered behind it.
            running = asyncio.create_task(client_nc.request(CALLS, b"1", timeout=10))
            await soon(lambda: old.received == [b"1"])
            delivered = asyncio.create_task(client_nc.request(CALLS, b"2", timeout=10))
            await soon(lambda: old_nc.stats["in_msgs"] >= 2)

            await new.start(new_nc)  # the standby serves alongside
            await old.stop_accepting()
            # New calls reach the next engine...
            for n in range(3, 8):
                reply = await client_nc.request(CALLS, b"%d" % n, timeout=5)
                assert reply.data == b"new:%d" % n
            # ...while the old one answers the calls it received.
            finishing = asyncio.create_task(old.sessions_finished())
            await asyncio.sleep(0.2)
            assert not finishing.done()
            old.gate.set()
            assert (await running).data == b"old:1"
            assert (await delivered).data == b"old:2"
            await asyncio.wait_for(finishing, 5)
            assert old.received == [b"1", b"2"]
            assert old.cancelled == []
        finally:
            await old.stop()
            await new.stop()
            for nc in (old_nc, new_nc, client_nc):
                await nc.close()

    asyncio.run(scenario())


def test_a_call_sent_while_no_engine_serves_is_answered_by_the_next_one(broker):
    async def scenario():
        old_nc, new_nc, client_nc = [await nats.connect(broker) for _ in range(3)]
        old, new = SlowEcho("old"), SlowEcho("new")
        old.gate.set()
        new.gate.set()
        try:
            await old.start(old_nc)
            assert (await client_nc.request(CALLS, b"1", timeout=5)).data == b"old:1"

            await old.stop_accepting()
            asking = asyncio.create_task(
                no_responders.request(client_nc, CALLS, b"2", headers={}, timeout=5)
            )
            await asyncio.sleep(0.3)  # nobody answers: the caller sends it again
            assert not asking.done()
            await new.start(new_nc)

            assert (await asking).data == b"new:2"
            await asyncio.wait_for(old.sessions_finished(), 5)
        finally:
            await old.stop()
            await new.stop()
            for nc in (old_nc, new_nc, client_nc):
                await nc.close()

    asyncio.run(scenario())


def test_a_call_still_running_at_the_drain_deadline_is_cancelled(broker):
    async def scenario():
        host_nc, client_nc = [await nats.connect(broker) for _ in range(2)]
        old = SlowEcho("old")  # never answers
        try:
            await old.start(host_nc)
            running = asyncio.create_task(client_nc.request(CALLS, b"1", timeout=3))
            await soon(lambda: old.received == [b"1"])

            await old.stop_accepting()
            loop = asyncio.get_running_loop()
            started = loop.time()
            assert await wait_for_sessions([old], 0.3) is False
            assert 0.3 <= loop.time() - started < 1.5
            await old.stop()

            assert old.cancelled == [b"1"]
            with pytest.raises(NATSTimeoutError):
                await running
        finally:
            await old.stop()
            for nc in (host_nc, client_nc):
                await nc.close()

    asyncio.run(scenario())


def test_fencing_stops_the_calls_at_once(broker):
    async def scenario():
        host_nc, client_nc = [await nats.connect(broker) for _ in range(2)]
        old = SlowEcho("old")
        try:
            await old.start(host_nc)
            running = asyncio.create_task(client_nc.request(CALLS, b"1", timeout=3))
            await soon(lambda: old.received == [b"1"])

            await asyncio.wait_for(old.stop(), 1)  # no time to drain

            assert old.cancelled == [b"1"]
            with pytest.raises(NATSTimeoutError):
                await running
            with pytest.raises(NoRespondersError):
                await client_nc.request(CALLS, b"2", timeout=1)
        finally:
            await old.stop()
            for nc in (host_nc, client_nc):
                await nc.close()

    asyncio.run(scenario())
