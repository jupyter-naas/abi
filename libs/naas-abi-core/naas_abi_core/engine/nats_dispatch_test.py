import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor

import pytest
from naas_abi_core.engine import nats_dispatch
from naas_abi_core.engine.nats_dispatch import DomainRPCDispatcher


def test_nested_domains_progress_with_one_shared_worker_and_keep_context():
    identity = contextvars.ContextVar("caller", default="missing")

    async def exercise():
        loop = asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
        parent = DomainRPCDispatcher("parent", max_workers=1)
        child = DomainRPCDispatcher("child", max_workers=1)
        identity.set("caller")

        def outer(value):
            return asyncio.run_coroutine_threadsafe(
                child.call(lambda v: (v, identity.get()), value), loop
            ).result(timeout=2)

        try:
            assert await asyncio.wait_for(parent.call(outer, 42), timeout=3) == (
                42,
                "caller",
            )
        finally:
            parent.close()
            child.close()

    asyncio.run(exercise())


@pytest.fixture
def default_capacity():
    yield
    nats_dispatch.configure(nats_dispatch.DEFAULT_MAX_CONCURRENT_REQUESTS)


def test_a_dispatcher_has_a_worker_for_each_call_its_service_admits(default_capacity):
    assert nats_dispatch.DEFAULT_MAX_CONCURRENT_REQUESTS == 64
    assert DomainRPCDispatcher("document").max_workers == 64


def test_the_configured_capacity_sizes_the_dispatchers_created_next(default_capacity):
    nats_dispatch.configure(16)

    assert nats_dispatch.max_concurrent_requests() == 16
    assert DomainRPCDispatcher("document").max_workers == 16


def test_a_capacity_below_one_is_refused(default_capacity):
    with pytest.raises(ValueError):
        nats_dispatch.configure(0)
