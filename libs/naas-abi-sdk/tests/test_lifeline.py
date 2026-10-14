"""A NATS connection that closes for good stops the process that opted in."""

import asyncio
import logging
import shutil
import signal
import socket
import subprocess
import sys
import textwrap
import time

import pytest
from nats.errors import NoServersError

from naas_abi_sdk import lifeline
from naas_abi_sdk.transport import Transport

needs_broker = pytest.mark.skipif(
    shutil.which("nats-server") is None, reason="nats-server not installed"
)


@pytest.fixture(autouse=True)
def _log_only():
    """Every test starts and ends with the default: losses are only logged."""
    restore = lifeline.exit_on_connection_loss(None)
    yield
    restore()


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
    yield f"nats://127.0.0.1:{port}", process
    if process.poll() is None:
        process.terminate()
        process.wait(timeout=5)


def test_a_lost_connection_stops_a_process_that_opted_in():
    stops = []
    lifeline.exit_on_connection_loss(lambda: stops.append("stop"))

    asyncio.run(lifeline.Lifeline("abi-engine").closed())

    assert stops == ["stop"]


def test_a_connection_its_owner_closes_is_not_a_loss():
    stops = []
    lifeline.exit_on_connection_loss(lambda: stops.append("stop"))
    watched = lifeline.Lifeline("abi-engine")

    watched.closing = True
    asyncio.run(watched.closed())

    assert stops == []


class _Connection:
    """Calls ``closed_cb`` when closed, as nats-py does."""

    def __init__(self, closed_cb):
        self.closed_cb = closed_cb
        self.is_closed = False

    async def close(self):
        if not self.is_closed:
            self.is_closed = True
            await self.closed_cb()


def test_closing_through_the_lifeline_is_not_a_loss():
    stops = []
    lifeline.exit_on_connection_loss(lambda: stops.append("stop"))
    watched = lifeline.Lifeline("abi-engine")
    connection = _Connection(watched.closed)

    asyncio.run(watched.close(connection))

    assert connection.is_closed
    assert stops == []


def test_closing_a_connection_nats_already_closed_keeps_the_loss():
    stops = []
    lifeline.exit_on_connection_loss(lambda: stops.append("stop"))
    watched = lifeline.Lifeline("abi-bus:worker")
    connection = _Connection(watched.closed)

    async def scenario():
        connection.is_closed = True  # nats-py gave up; its closed_cb is still to run
        await watched.close(connection)  # the owner reacts to the closed connection
        await watched.closed()

    asyncio.run(scenario())

    assert stops == ["stop"]


def test_without_opting_in_a_loss_is_only_logged(caplog):
    with caplog.at_level(logging.ERROR, logger="naas_abi_sdk.lifeline"):
        asyncio.run(lifeline.Lifeline("abi-bus:worker").closed())

    assert "abi-bus:worker" in caplog.text


def test_only_the_first_loss_stops_the_process():
    stops = []
    lifeline.exit_on_connection_loss(lambda: stops.append("stop"))

    asyncio.run(lifeline.Lifeline("abi-engine").closed())
    asyncio.run(lifeline.Lifeline("abi-engine-ownership").closed())

    assert stops == ["stop"]


def test_restoring_brings_back_the_previous_behaviour():
    stops = []
    restore = lifeline.exit_on_connection_loss(lambda: stops.append("stop"))
    restore()

    asyncio.run(lifeline.Lifeline("abi-engine").closed())

    assert stops == []


def test_stopping_on_loss_applies_only_inside_its_block():
    stops = []

    async def scenario():
        async with lifeline.stopping_on_loss(lambda: stops.append("inside")):
            await lifeline.Lifeline("abi-engine").closed()
        await lifeline.Lifeline("abi-engine").closed()

    asyncio.run(scenario())

    assert stops == ["inside"]


def _run(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        capture_output=True,
        timeout=30,
        check=False,
    )


def test_stopping_sends_the_process_sigterm():
    result = _run(
        """
        import asyncio, time
        from naas_abi_sdk import lifeline
        lifeline.exit_on_connection_loss()
        asyncio.run(lifeline.Lifeline("abi-engine").closed())
        time.sleep(10)
        """
    )

    assert result.returncode == -signal.SIGTERM


def test_a_shutdown_that_hangs_ends_in_a_hard_exit():
    result = _run(
        """
        import asyncio, signal, time
        from naas_abi_sdk import lifeline
        lifeline.HARD_EXIT_SECONDS = 0.2
        signal.signal(signal.SIGTERM, lambda *_: None)  # a shutdown that never ends
        lifeline.exit_on_connection_loss()
        asyncio.run(lifeline.Lifeline("abi-engine").closed())
        time.sleep(10)
        """
    )

    assert result.returncode == 1


@needs_broker
def test_a_transport_whose_broker_goes_away_reports_the_loss(broker):
    url, server = broker
    stops = []

    async def scenario():
        transport = Transport(url, token="t", allow_reconnect=False)
        await transport.connect()
        lifeline.exit_on_connection_loss(lambda: stops.append("stop"))
        server.terminate()
        server.wait(timeout=5)
        deadline = time.monotonic() + 5
        while not stops and time.monotonic() < deadline:
            await asyncio.sleep(0.02)
        return transport

    transport = asyncio.run(scenario())

    assert stops == ["stop"]
    # A later call connects afresh instead of failing on the closed client.
    assert transport._connected is False


@needs_broker
def test_closing_a_transport_is_not_a_loss(broker):
    url, _ = broker
    stops = []

    async def scenario():
        transport = Transport(url, token="t")
        await transport.connect()
        lifeline.exit_on_connection_loss(lambda: stops.append("stop"))
        await transport.close()
        await asyncio.sleep(0.1)

    asyncio.run(scenario())

    assert stops == []


def test_a_transport_that_fails_to_connect_is_not_a_loss():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]  # nothing listens here
    stops = []

    async def scenario():
        lifeline.exit_on_connection_loss(lambda: stops.append("stop"))
        transport = Transport(
            f"nats://127.0.0.1:{port}",
            token="t",
            max_reconnect_attempts=1,
            reconnect_time_wait=0.01,
        )
        with pytest.raises(NoServersError):
            await transport.connect()
        await asyncio.sleep(0.1)

    asyncio.run(scenario())

    assert stops == []
