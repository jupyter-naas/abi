"""Requests to the engine ride out a handover, against a real nats-server."""

import asyncio
import shutil
import socket
import subprocess
import time

import nats
import pytest
from naas_abi_proto.transfer.v1 import transfer_pb2 as pb
from nats.errors import NoRespondersError

from naas_abi_sdk import no_responders
from naas_abi_sdk.telemetry import TransferTrace
from naas_abi_sdk.transport import Transport

needs_broker = pytest.mark.skipif(
    shutil.which("nats-server") is None, reason="nats-server not installed"
)


@pytest.fixture
def broker():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    process = subprocess.Popen(
        ["nats-server", "-a", "127.0.0.1", "-p", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 5
    while True:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except OSError:
            assert time.monotonic() < deadline, "nats-server did not start"
            time.sleep(0.02)
    yield f"nats://127.0.0.1:{port}"
    process.terminate()
    process.wait(timeout=5)


@pytest.mark.parametrize(
    "subject",
    [
        "abi.svc.document.v1.get",
        "abi.svc.model_registry.v1.chat",
        "abi.discovery.default.v1.register",
    ],
)
def test_the_engine_serves_kernel_and_discovery_subjects(subject):
    assert no_responders.engine_served(subject)


@pytest.mark.parametrize(
    "subject",
    [
        "abi.discovery.default.v1.presence.0123456789abcdef0123456789abcdef",
        "abi.agent.default.0123.abcd.v1.submit",
        "abi.jobs.default.trigger.x.y",
        "_INBOX.abc",
    ],
)
def test_instance_subjects_are_not_engine_served(subject):
    assert not no_responders.engine_served(subject)


@pytest.mark.parametrize(
    ("subject", "resent"),
    [
        ("abi.svc.object_storage.v1.transfer.open", True),
        ("abi.svc.model_registry.v1.transfer.open", True),
        (
            "abi.svc.object_storage.v1.transfer.0123456789abcdef0123456789abcdef.read",
            False,
        ),
        ("abi.svc.dataset.v1.transfer.0123456789abcdef0123456789abcdef.close", False),
        ("abi.svc.document.v1.get", False),
    ],
)
def test_only_the_open_of_a_transfer_goes_to_the_queue_group(subject, resent):
    assert no_responders.transfer_open(subject) is resent


@needs_broker
def test_a_request_waits_for_the_next_engine_to_subscribe(broker):
    async def scenario():
        caller, engine = await nats.connect(broker), await nats.connect(broker)

        async def answer(msg):
            await msg.respond(b"pong")

        async def subscribe_later():
            await asyncio.sleep(0.3)
            await engine.subscribe("abi.svc.test.v1.ping", queue="q", cb=answer)
            await engine.flush()

        started = time.monotonic()
        late = asyncio.create_task(subscribe_later())
        reply = await no_responders.request(
            caller, "abi.svc.test.v1.ping", b"ping", headers={}, timeout=5
        )
        await late

        assert reply.data == b"pong"
        assert time.monotonic() - started >= 0.3
        await caller.close()
        await engine.close()

    asyncio.run(scenario())


@needs_broker
def test_nobody_serving_still_fails_after_the_retry_window(broker):
    async def scenario():
        nc = await nats.connect(broker)
        started = time.monotonic()
        with pytest.raises(NoRespondersError):
            await no_responders.request(
                nc,
                "abi.svc.test.v1.ping",
                b"ping",
                headers={},
                timeout=5,
                retry_seconds=0.3,
            )
        assert 0.2 <= time.monotonic() - started < 2
        await nc.close()

    asyncio.run(scenario())


@needs_broker
def test_the_retry_ends_before_the_callers_deadline(broker):
    # A caller whose deadline is inside the retry window still learns that
    # nobody serves the subject (a transfer open falls back on it), not a timeout.
    async def scenario():
        nc = await nats.connect(broker)
        started = time.monotonic()
        with pytest.raises(NoRespondersError):
            await asyncio.wait_for(
                no_responders.request(
                    nc, "abi.svc.test.v1.ping", b"ping", headers={}, timeout=1.0
                ),
                timeout=1.0,
            )
        assert time.monotonic() - started < 1.0
        await nc.close()

    asyncio.run(scenario())


@needs_broker
def test_an_instance_subject_fails_at_once(broker):
    async def scenario():
        nc = await nats.connect(broker)
        started = time.monotonic()
        with pytest.raises(NoRespondersError):
            await no_responders.request(
                nc, "abi.agent.p.i.d.v1.status", b"", headers={}, timeout=5
            )
        assert time.monotonic() - started < 0.2
        await nc.close()

    asyncio.run(scenario())


@needs_broker
def test_a_transfer_open_waits_for_the_next_engine_but_its_session_calls_do_not(
    broker,
):
    prefix = "abi.svc.test.v1.transfer"
    owner = "0123456789abcdef0123456789abcdef"

    async def scenario():
        transport, engine = (
            Transport(broker, "token", timeout=5),
            await nats.connect(broker),
        )

        async def answer(msg):
            await msg.respond(pb.OpenResponse(id=f"{owner}:1").SerializeToString())

        async def subscribe_later():
            await asyncio.sleep(0.3)
            await engine.subscribe(
                f"{prefix}.open", queue=f"{prefix}.owners", cb=answer
            )
            await engine.flush()

        try:
            late = asyncio.create_task(subscribe_later())
            opened = await transport.call(
                f"{prefix}.open",
                pb.OpenRequest(),
                pb.OpenResponse,
                transfer=TransferTrace(),
            )
            await late
            assert opened.id == f"{owner}:1"

            started = time.monotonic()
            with pytest.raises(NoRespondersError):
                await transport.call(
                    f"{prefix}.{owner}.read",
                    pb.ReadRequest(id=opened.id),
                    pb.ReadResponse,
                    transfer=TransferTrace(),
                )
            assert time.monotonic() - started < 0.2
        finally:
            await transport.close()
            await engine.close()

    asyncio.run(scenario())
