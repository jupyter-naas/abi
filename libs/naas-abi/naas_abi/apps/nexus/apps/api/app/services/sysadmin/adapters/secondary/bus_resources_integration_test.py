"""BusResources against a real nats-server with JetStream."""

import asyncio
import shutil
import subprocess

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.bus_resources import (
    REDACTED,
    BusResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_integration_test import (
    _port,
    _wait_for,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    ServiceResourcesContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    InvalidResource,
    UnsupportedOperation,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures

pytestmark = pytest.mark.integration


class Broker:
    def __init__(self, url):
        self.url = url
        self.loop = asyncio.new_event_loop()

    def run(self, coro):
        return self.loop.run_until_complete(coro)


class OnLoop:
    """Runs an adapter on the broker's loop; contracts await the result with
    asyncio.run, so outcomes (errors included) are delivered when awaited."""

    def __init__(self, broker, adapter):
        self._broker, self._adapter = broker, adapter

    def __getattr__(self, name):
        method = getattr(self._adapter, name)
        if not callable(method):
            return method

        def call(*args, **kwargs):
            try:
                result = self._broker.run(method(*args, **kwargs))
            except BaseException as exc:  # noqa: BLE001 - re-raised when awaited
                error = exc

                async def failed():
                    raise error

                return failed()

            async def done():
                return result

            return done()

        return call


@pytest.fixture(scope="module")
def broker(tmp_path_factory):
    binary = shutil.which("nats-server")
    if binary is None:
        pytest.skip("nats-server is not installed")
    port = _port()
    process = subprocess.Popen(
        [
            binary,
            "-a",
            "127.0.0.1",
            "-p",
            str(port),
            "-js",
            "-sd",
            str(tmp_path_factory.mktemp("js")),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for(port)
        broker = Broker(f"nats://127.0.0.1:{port}")

        async def connect():
            import nats

            return await nats.connect(broker.url)

        broker.nc = broker.run(connect())
        yield broker
        broker.run(broker.nc.close())
        broker.loop.close()
    finally:
        process.terminate()
        process.wait(timeout=5)


async def _seed(nc):
    from nats.js.api import StreamConfig
    from nats.js.errors import NotFoundError

    js = nc.jetstream()
    for name in ("SEED", "KV_settings"):
        try:
            await js.delete_stream(name)
        except NotFoundError:
            pass
    await js.add_stream(StreamConfig(name="SEED", subjects=list(fixtures.SEED_ITEMS)))
    for subject, value in fixtures.SEED_ITEMS.items():
        await js.publish(subject, value, headers={"Nats-Auth-Token": "tok", "X-Trace": "t1"})
    kv = await js.create_key_value(bucket="settings")
    await kv.put("api_key", b"kv-value")


@pytest.fixture
def bus(broker):
    broker.run(_seed(broker.nc))

    async def connect():
        return broker.nc

    return OnLoop(broker, BusResources(connect))


class TestBusResourcesOnJetStream(ServiceResourcesContract):
    base = "SEED"

    @pytest.fixture
    def resources(self, bus):
        return bus


def test_streams_are_listed_with_their_kind(bus):
    page = asyncio.run(bus.list(""))
    streams = {e.id: e for e in page.entries}

    assert {"SEED", "KV_settings"} <= set(streams)
    assert streams["SEED"].kind == "container"
    assert streams["SEED"].attributes["messages"] == "3"
    assert streams["SEED"].attributes["subjects"] == "alpha, beta, gamma"
    assert streams["KV_settings"].attributes["kind"] == "kv"


def test_messages_are_newest_first_with_redacted_headers(bus):
    page = asyncio.run(bus.list("SEED"))

    assert [e.name for e in page.entries] == ["gamma", "beta", "alpha"]
    gamma = page.entries[0]
    assert (gamma.id, gamma.attributes["seq"]) == ("SEED/3", "3")
    assert gamma.attributes["header:Nats-Auth-Token"] == REDACTED
    assert gamma.attributes["header:X-Trace"] == "t1"
    assert "tok" not in repr(asyncio.run(bus.read("SEED/3")))


def test_key_value_revisions_are_read_only(bus):
    (revision,) = asyncio.run(bus.list("KV_settings")).entries

    assert "delete" not in revision.actions
    assert asyncio.run(bus.read(revision.id)).content.text == "kv-value"
    with pytest.raises(UnsupportedOperation):
        asyncio.run(bus.delete(revision.id))
    assert len(asyncio.run(bus.list("KV_settings")).entries) == 1


def test_streams_are_not_items_and_cannot_be_deleted(bus):
    with pytest.raises(InvalidResource):
        asyncio.run(bus.read("SEED"))
    with pytest.raises(UnsupportedOperation):
        asyncio.run(bus.delete("SEED"))
    with pytest.raises(UnsupportedOperation):
        asyncio.run(bus.write("SEED/9", b"x"))


def test_messages_and_streams_tell_what_they_hold(bus):
    streams = {e.id: e for e in asyncio.run(bus.list("")).entries}
    (gamma, *_) = asyncio.run(bus.list("SEED")).entries

    assert streams["SEED"].modified is not None
    assert streams["KV_settings"].attributes["read_only"] == "key-value bucket"
    assert (gamma.attributes["payload"], gamma.attributes["summary"]) == ("text", "third value")
    assert asyncio.run(bus.read(gamma.id)).view["subject"] == "gamma"
