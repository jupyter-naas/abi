"""Tests for VectorStoreSecondaryAdapterNATSClient.

Structured like ObjectStorageSecondaryAdapterNATSClient_test.py: fast unit
tests need no network I/O at all, and a slower ``@pytest.mark.integration``
suite round-trips through a real NATS server (skipped cleanly when
Docker/testcontainers is unavailable -- confirmed unavailable in this
environment, so that suite self-skips here, which is expected).

Test coverage note (see the task's item 7): there is no
``tests/vector_store__secondary_adapter__generic_test.py`` -- the
adapter-agnostic contract lives in ``IVectorStorePort_test.py``'s
``GenericVectorStoreAdapterTest`` instead, the same base class
``QdrantAdapter_test.py``/``QdrantInMemoryAdapter_test.py`` already
subclass. Its ``adapter`` fixture shape (one function-scoped fixture
returning a ready-to-use ``IVectorStorePort``) plugs a NATS-backed pair in
cleanly, so this file parametrizes the client into it directly
(``TestVectorStoreSecondaryAdapterNATSClient`` below) rather than
duplicating a bespoke integration class -- preferred per the task's
instructions, and it buys genuine round-trip coverage (real similarity
search, real float precision) for free by wrapping a real
``QdrantInMemoryAdapter(storage_path=":memory:")`` server-side, the same way
the object_storage contract test wraps a real
``ObjectStorageSecondaryAdapterFS``.
"""

import asyncio
import time
from datetime import UTC, datetime, timedelta
from threading import Event as ThreadingEvent
from threading import Thread
from unittest.mock import AsyncMock

import naas_abi_core.services.vector_store.adapters.secondary.VectorStoreSecondaryAdapterNATSClient as _client_module
import nats
import numpy as np
import pytest
from naas_abi_core import logger
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.services.vector_store.adapters.primary.vector_store__primary_adapter__NATS import (
    VectorStorePrimaryAdapterNATS,
)
from naas_abi_core.services.vector_store.adapters.QdrantInMemoryAdapter import (
    QdrantInMemoryAdapter,
)
from naas_abi_core.services.vector_store.adapters.secondary.VectorStoreSecondaryAdapterNATSClient import (
    VectorStoreSecondaryAdapterNATSClient,
    _raise_for_error,
)
from naas_abi_core.services.vector_store.IVectorStorePort import VectorDocument
from naas_abi_core.services.vector_store.IVectorStorePort_test import (
    GenericVectorStoreAdapterTest,
)

JWT_SECRET = "test-shared-secret"


# ---------------------------------------------------------------------------
# Construction is lazy -- no network I/O until a method is actually called.
# ---------------------------------------------------------------------------


def test_init_is_lazy(monkeypatch):
    connect = AsyncMock()
    monkeypatch.setattr(nats, "connect", connect)
    VectorStoreSecondaryAdapterNATSClient("nats://127.0.0.1:4222", JWT_SECRET, "api")
    connect.assert_not_called()


def test_close_without_connecting_is_a_noop():
    client = VectorStoreSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    client.close()  # must not raise, must not connect


def test_context_manager_calls_close():
    closed = []
    client = VectorStoreSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    client.close = lambda: closed.append(True)  # type: ignore[method-assign]

    with client:
        pass

    assert closed == [True]


# ---------------------------------------------------------------------------
# close() is a deliberate exception to the "one port method, one RPC" rule --
# see VectorStoreSecondaryAdapterNATSClient.close's docstring: the adapter
# behind the primary server is shared across every caller, so this client
# must never ask the server to tear it down on its behalf.
# ---------------------------------------------------------------------------


def test_close_does_not_invoke_the_remote_rpc():
    client = VectorStoreSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("close() must not call the wire")

    client._call = _fail_if_called  # type: ignore[method-assign]

    client.close()  # must not raise -- proves _call was never invoked


# ---------------------------------------------------------------------------
# create_collection's **kwargs is out of scope for the v1 wire contract --
# rejected explicitly rather than silently dropped.
# ---------------------------------------------------------------------------


def test_create_collection_rejects_kwargs_with_not_implemented():
    client = VectorStoreSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    with pytest.raises(NotImplementedError):
        client.create_collection("docs", 4, on_disk_payload=True)


# ---------------------------------------------------------------------------
# Error-code -> exception mapping. IVectorStorePort declares no typed
# exceptions (see VectorStorePrimaryAdapterNATS's module docstring), so
# every server-reported failure surfaces as a plain RuntimeError.
# ---------------------------------------------------------------------------


def test_raise_for_error_maps_internal_to_runtime_error():
    with pytest.raises(RuntimeError, match="INTERNAL"):
        _raise_for_error(common_pb2.CallError(code="INTERNAL", message="boom"))


def test_raise_for_error_maps_unauthenticated_to_runtime_error():
    with pytest.raises(RuntimeError, match="UNAUTHENTICATED"):
        _raise_for_error(
            common_pb2.CallError(code="UNAUTHENTICATED", message="no token")
        )


# ---------------------------------------------------------------------------
# Token issuance: issued once, reused, reissued only close to expiry.
# ---------------------------------------------------------------------------


def test_token_is_issued_once_and_reused(monkeypatch):
    calls: list[str] = []

    def fake_issue(identity: str, secret: str) -> str:
        calls.append(identity)
        return f"token-{len(calls)}"

    monkeypatch.setattr(_client_module, "issue_service_token", fake_issue)

    client = VectorStoreSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )

    assert client._current_token() == "token-1"
    assert client._current_token() == "token-1"
    assert calls == ["api"]


def test_token_is_reissued_when_close_to_expiry(monkeypatch):
    calls: list[str] = []

    def fake_issue(identity: str, secret: str) -> str:
        calls.append(identity)
        return f"token-{len(calls)}"

    monkeypatch.setattr(_client_module, "issue_service_token", fake_issue)

    client = VectorStoreSecondaryAdapterNATSClient(
        "nats://127.0.0.1:4222", JWT_SECRET, "api"
    )
    assert client._current_token() == "token-1"

    # Simulate the token being almost expired.
    client._token_expires_at = datetime.now(UTC) + timedelta(seconds=1)

    assert client._current_token() == "token-2"
    assert calls == ["api", "api"]


# ---------------------------------------------------------------------------
# Real round trip: a live NATS container, a real VectorStorePrimaryAdapterNATS
# wrapping a real QdrantInMemoryAdapter, and the client talking to it over
# the wire. Skips cleanly when Docker/testcontainers is unavailable.
# ---------------------------------------------------------------------------


class _PrimaryAdapterServer:
    """Runs VectorStorePrimaryAdapterNATS on its own background event loop
    for as long as a test needs it -- the server-side mirror of the client's
    own background loop, since nats-py has no synchronous API on either
    side."""

    def __init__(self, nats_url: str, jwt_secret: str, wrapped_adapter) -> None:
        self._nats_url = nats_url
        self._jwt_secret = jwt_secret
        self._wrapped_adapter = wrapped_adapter
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: Thread | None = None
        self._nc: nats.NATS | None = None
        self._primary: VectorStorePrimaryAdapterNATS | None = None

    def start(self) -> None:
        ready = ThreadingEvent()
        errors: list[BaseException] = []

        def _run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            try:
                loop.run_until_complete(self._start_async())
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                ready.set()
            if not errors:
                loop.run_forever()
            loop.close()

        thread = Thread(
            target=_run, daemon=True, name="vector-store-nats-primary-test-loop"
        )
        thread.start()
        ready.wait(timeout=15)
        self._thread = thread
        if errors:
            raise errors[0]

    async def _start_async(self) -> None:
        self._nc = await nats.connect(self._nats_url)
        self._primary = VectorStorePrimaryAdapterNATS(
            self._wrapped_adapter, self._jwt_secret
        )
        await self._primary.start(self._nc)

    def stop(self) -> None:
        loop = self._loop
        if loop is None:
            return
        try:
            future = asyncio.run_coroutine_threadsafe(self._stop_async(), loop)
            future.result(timeout=5.0)
        except Exception as exc:  # noqa: BLE001
            # Best-effort teardown of a test-only harness -- the loop gets
            # stopped and the thread joined regardless, right below.
            logger.debug(f"test harness: error stopping NATS test server: {exc}")
        loop.call_soon_threadsafe(loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    async def _stop_async(self) -> None:
        if self._primary is not None:
            await self._primary.stop()
        if self._nc is not None:
            await self._nc.close()


@pytest.fixture(scope="session")
def nats_url():
    try:
        # Imported here, not at module level: testcontainers is a dev-only
        # dependency, absent from environments that don't run
        # `uv sync --all-extras` for this package -- see the identical
        # pattern in ObjectStorageSecondaryAdapterNATSClient_test.py.
        from testcontainers.core.container import DockerContainer

        with (
            DockerContainer("nats:2-alpine").with_exposed_ports(4222)
        ) as container:
            host = container.get_container_host_ip()
            port = container.get_exposed_port(4222)
            url = f"nats://{host}:{port}"

            deadline = time.time() + 30
            last_exc: Exception | None = None

            async def _probe() -> None:
                nc = await nats.connect(url, connect_timeout=2)
                await nc.close()

            while time.time() < deadline:
                try:
                    asyncio.run(_probe())
                    break
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    time.sleep(0.5)
            else:
                pytest.fail(f"NATS container did not become ready in time: {last_exc}")

            yield url
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Docker/Testcontainers unavailable: {exc}")


@pytest.mark.integration
class TestVectorStoreSecondaryAdapterNATSClient(GenericVectorStoreAdapterTest):
    """Round-trips the shared IVectorStorePort contract through a real
    primary adapter (wrapping a real in-memory Qdrant adapter) and the real
    client, over a live NATS server."""

    @pytest.fixture
    def adapter(self, nats_url):
        wrapped = QdrantInMemoryAdapter(storage_path=":memory:")
        server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
        server.start()

        client = VectorStoreSecondaryAdapterNATSClient(
            nats_url=nats_url,
            jwt_secret=JWT_SECRET,
            service_identity="api",
            timeout_seconds=10.0,
        )
        yield client
        client.close()
        server.stop()


@pytest.mark.integration
def test_wrong_secret_surfaces_as_runtime_error(nats_url):
    wrapped = QdrantInMemoryAdapter(storage_path=":memory:")
    server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
    server.start()
    client = VectorStoreSecondaryAdapterNATSClient(
        nats_url=nats_url,
        jwt_secret="a-completely-different-secret",
        service_identity="api",
        timeout_seconds=5.0,
    )
    try:
        with pytest.raises(RuntimeError, match="UNAUTHENTICATED"):
            client.create_collection("docs", 4)
    finally:
        client.close()
        server.stop()


@pytest.mark.integration
def test_search_round_trips_real_similarity_scores(nats_url):
    wrapped = QdrantInMemoryAdapter(storage_path=":memory:")
    server = _PrimaryAdapterServer(nats_url, JWT_SECRET, wrapped)
    server.start()
    client = VectorStoreSecondaryAdapterNATSClient(
        nats_url=nats_url,
        jwt_secret=JWT_SECRET,
        service_identity="api",
        timeout_seconds=10.0,
    )
    try:
        client.initialize()
        client.create_collection("docs", 3)
        client.store_vectors(
            "docs",
            [
                VectorDocument(
                    id="doc-1",
                    vector=np.array([1.0, 0.0, 0.0], dtype=np.float32),
                    metadata={"category": "a"},
                    payload={"raw": "x"},
                )
            ],
        )

        results = client.search(
            "docs",
            np.array([1.0, 0.0, 0.0], dtype=np.float32),
            k=1,
            include_vectors=True,
            include_metadata=True,
        )

        assert len(results) == 1
        assert results[0].id == "doc-1"
        assert results[0].score >= 0.99
        assert results[0].metadata == {"category": "a"}
    finally:
        client.close()
        server.stop()
