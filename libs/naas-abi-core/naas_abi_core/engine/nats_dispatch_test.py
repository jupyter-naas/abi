import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor

import pytest
from naas_abi_core.engine import nats_dispatch
from naas_abi_core.engine.nats_dispatch import DomainRPCDispatcher

# The container a call is made in: request data, carried as is.
WS = "abi:nexus:organization/org-1/nexus:workspace/ws-1"


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


def test_the_worker_runs_as_the_caller_given_and_only_for_that_call():
    from naas_abi_core.engine.call_context import (
        ANONYMOUS,
        CallContext,
        current_call_context,
        service_account,
        user,
    )
    from naas_abi_proto.common.v1 import common_pb2
    from naas_abi_proto.keyvalue.v1 import keyvalue_pb2

    caller = CallContext(principal=service_account("api"), on_behalf_of=user("usr-1"))
    request = keyvalue_pb2.GetRequest(
        context=common_pb2.CallContext(trace_id="trace-1", container=WS)
    )

    async def exercise():
        dispatcher = DomainRPCDispatcher("keyvalue", max_workers=1)
        try:
            seen = await dispatcher.call(
                lambda _: current_call_context(), request, caller
            )
            after = await dispatcher.call(lambda _: current_call_context(), request)
            return seen, after, current_call_context()
        finally:
            dispatcher.close()

    seen, after, outside = asyncio.run(exercise())
    assert seen == CallContext(
        principal=service_account("api"),
        on_behalf_of=user("usr-1"),
        container=WS,
        trace_id="trace-1",
    )
    # Neither the worker thread nor the event loop keeps it afterwards.
    assert after == ANONYMOUS and outside == ANONYMOUS


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
