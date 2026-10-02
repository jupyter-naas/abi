import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor

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
