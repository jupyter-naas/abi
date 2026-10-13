import asyncio
import os
import socket
from uuid import uuid4

import nats
import pytest
from naas_abi_core.engine.nats_test_server import native_nats_server, nats_server_binary
from naas_abi_core.engine.ownership.ownership_factory import (
    create_engine_ownership,
    this_process,
)
from naas_abi_core.engine.ownership.ownership_service import (
    Claim,
    OwnershipTiming,
)


def test_this_process_describes_the_running_engine():
    me = this_process("v2")

    assert me.pid == os.getpid()
    assert me.host == socket.gethostname()
    assert me.rollout_id == "v2"
    assert me.started_at.endswith("+00:00")
    assert len(me.instance_id) == 32
    assert this_process().instance_id != me.instance_id


def test_this_process_holds_the_lease_under_the_engines_instance_id():
    engine_id = uuid4().hex

    assert this_process("v2", instance_id=engine_id).instance_id == engine_id


def test_this_process_reports_the_installed_core_version():
    from importlib.metadata import version

    assert this_process().version == version("naas-abi-core")


def test_an_ownership_over_jetstream_claims_and_releases(tmp_path):
    if nats_server_binary() is None:
        pytest.skip("nats-server is not installed")

    async def scenario(url):
        nc = await nats.connect(url)
        try:
            bucket = f"ABI_ENGINE_{uuid4().hex}"
            ownership = await create_engine_ownership(
                nc, this_process(), OwnershipTiming(lease_seconds=1), bucket=bucket
            )
            assert await ownership.claim() is Claim.SERVING
            assert (await ownership.lease.read()).holder == ownership.me
            await ownership.release()
            assert await ownership.lease.read() is None
        finally:
            await nc.close()

    with native_nats_server(tmp_path, jetstream=True) as url:
        asyncio.run(scenario(url))
