"""Sessions a serving engine owns: their owner id, and how they outlive a handover."""

import asyncio
from unittest.mock import MagicMock

import nats
import pytest
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.engine.nats_sessions import (
    SessionHost,
    owned_by,
    session_owner,
    wait_for_sessions,
)
from naas_abi_core.engine.nats_test_server import native_nats_server, nats_server_binary
from naas_abi_core.engine.nats_transfer import TransferError, TransferHost
from naas_abi_proto.transfer.v1 import transfer_pb2 as pb
from naas_abi_sdk.transfer import Transfer, transfer_subject
from nats.errors import NoRespondersError

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


def test_a_service_with_transfers_ends_its_endpoints_first_and_its_transfers_last():
    from unittest.mock import AsyncMock

    from naas_abi_core.engine.nats_transfer import ServiceWithTransfers

    class Primary(ServiceWithTransfers):
        def __init__(self) -> None:
            self._service = MagicMock(stop=AsyncMock())
            self._transfer = MagicMock(
                stop_accepting=AsyncMock(),
                sessions_finished=AsyncMock(),
                stop=AsyncMock(),
            )
            self._dispatch = MagicMock()

    async def scenario():
        primary = Primary()
        service, transfer = primary._service, primary._transfer

        await primary.stop_accepting()
        service.stop.assert_awaited_once()
        transfer.stop_accepting.assert_awaited_once()
        transfer.stop.assert_not_awaited()
        # Requests already received still run on the domain's workers.
        primary._dispatch.close.assert_not_called()

        await primary.sessions_finished()
        transfer.sessions_finished.assert_awaited_once()

        await primary.stop()
        transfer.stop.assert_awaited_once()
        primary._dispatch.close.assert_called_once()
        service.stop.assert_awaited_once()

    asyncio.run(scenario())


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
