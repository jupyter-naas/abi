import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi_core.services.discovery.adapters.secondary.discovery_jetstream import (
    JetStreamRegistry,
)
from naas_abi_core.services.discovery.discovery_ports import RevisionConflict
from nats.js.errors import KeyWrongLastSequenceError, NotFoundError


def test_leader_reads_and_cas_conflicts_are_not_replayed():
    async def scenario():
        js, bucket = AsyncMock(), AsyncMock()
        registry = JetStreamRegistry(js, bucket, "test")
        js.get_msg.return_value = SimpleNamespace(data=b"snapshot", seq=7)
        assert await registry.read() == (b"snapshot", 7)
        assert js.get_msg.call_args.kwargs["direct"] is False
        bucket.update.side_effect = KeyWrongLastSequenceError()
        with pytest.raises(RevisionConflict):
            await registry.compare_and_swap(b"new", 7)
        bucket.update.assert_awaited_once_with("registry", b"new", last=7)
        js.get_msg.side_effect = NotFoundError()
        assert await registry.read() == (b"", 0)

    asyncio.run(scenario())
