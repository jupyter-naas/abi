import asyncio
import copy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.agent.v1 import agent_pb2 as pb

from naas_abi_sdk.agent_host import AgentHost
from naas_abi_sdk.services.errors import DocumentNotFound, VersionConflict
from naas_abi_sdk.services.models import Document
from naas_abi_sdk.transport import RPCError


class Documents:
    def __init__(self):
        self.values = {}
        self.lose_running_reply = False

    async def ensure_collection(self, spec):
        pass

    async def get(self, collection, id):
        await asyncio.sleep(0)
        if (collection, id) not in self.values:
            raise DocumentNotFound("DOCUMENT_NOT_FOUND", id)
        return copy.deepcopy(self.values[collection, id])

    async def put(self, collection, id, data, if_version=None):
        await asyncio.sleep(0)
        previous = self.values.get((collection, id))
        if if_version is not None and if_version != (
            previous.version if previous else 0
        ):
            raise VersionConflict("VERSION_CONFLICT", id)
        now = datetime.now(timezone.utc)
        doc = Document(
            id, copy.deepcopy(data), now, now, (previous.version if previous else 0) + 1
        )
        self.values[collection, id] = doc
        if self.lose_running_reply and data.get("status") == "RUNNING":
            raise ConnectionError("lost write acknowledgement")
        return copy.deepcopy(doc)

    async def delete(self, collection, id, if_version=None):
        doc = self.values[collection, id]
        if if_version != doc.version:
            raise VersionConflict("VERSION_CONFLICT", id)
        del self.values[collection, id]


class Handler:
    def __init__(self):
        self.calls = 0
        self.finish = asyncio.Event()

    async def invoke(self, prompt, context):
        self.calls += 1
        await self.finish.wait()
        return "result"


def host(documents, handler, owner="owner"):
    session = SimpleNamespace(
        instance_id=owner,
        descriptor=SimpleNamespace(module_id="provider", contract_major=1),
        client=SimpleNamespace(
            project="default",
            get_module=AsyncMock(return_value=[SimpleNamespace(instance_id=owner)]),
        ),
    )
    return AgentHost(session, documents, {"agent": handler})


def request(id="id", prompt="hello"):
    return pb.SubmitRequest(
        invocation_id=id,
        thread_id="thread",
        prompt=prompt,
        mode="invoke",
        deadline_seconds=10,
    )


def test_replicas_deduplicate_and_serialize_conversations():
    async def scenario():
        docs, handler = Documents(), Handler()
        a, b = host(docs, handler), host(docs, handler, "replica")
        first, second = await asyncio.gather(
            a._submit("agent", "key", "caller", request()),
            b._submit("agent", "key", "caller", request()),
        )
        assert first.data["owner"] == second.data["owner"]
        await asyncio.sleep(0)
        assert handler.calls == 1
        failed = await b._submit("agent", "other", "caller", request("other"))
        assert failed.data["error_code"] == "CONVERSATION_BUSY"
        with pytest.raises(RPCError, match="INVOCATION_CONFLICT"):
            await b._submit("agent", "key", "caller", request(prompt="different"))
        with pytest.raises(RPCError, match="PERMISSION_DENIED"):
            await b._submit("agent", "key", "other-caller", request())
        tasks = [r.task for h in (a, b) for r in h.runs.values()]
        handler.finish.set()
        await asyncio.gather(*tasks)
        completed = await b._submit("agent", "key", "caller", request())
        assert completed.data["status"] == "SUCCEEDED"
        assert handler.calls == 1

    asyncio.run(scenario())


def test_uncertain_ownership_write_never_replays_or_releases_claim():
    async def scenario():
        docs, handler = Documents(), Handler()
        docs.lose_running_reply = True
        original = host(docs, handler)
        with pytest.raises(ConnectionError):
            await original._submit("agent", "key", "caller", request())
        replacement = host(docs, handler, "replacement")
        existing = await replacement._submit("agent", "key", "caller", request())
        assert existing.data["status"] == "RUNNING"
        assert handler.calls == 0
        conflict = await replacement._submit("agent", "next", "caller", request("next"))
        assert conflict.data["error_code"] == "CONVERSATION_BUSY"

    asyncio.run(scenario())


def test_cancellation_waits_for_started_task_and_releases_claim():
    async def scenario():
        docs, handler = Documents(), Handler()
        owner = host(docs, handler)
        await owner._submit("agent", "key", "caller", request())
        run = owner.runs["key"]
        await owner._cancel(run, "CANCELLED")
        await run.task
        assert (await docs.get(owner.runs_collection, "key")).data[
            "status"
        ] == "CANCELLED"
        assert not any(
            collection == owner.locks_collection for collection, _ in docs.values
        )

    asyncio.run(scenario())


def test_deadline_persists_timeout_only_after_execution_stops():
    async def scenario():
        docs, handler = Documents(), Handler()
        owner = host(docs, handler)
        await owner._submit("agent", "key", "caller", request())
        run = owner.runs["key"]
        await owner._deadline(run, 0)
        await run.task
        assert (await docs.get(owner.runs_collection, "key")).data[
            "status"
        ] == "TIMED_OUT"
        assert not any(
            collection == owner.locks_collection for collection, _ in docs.values
        )

    asyncio.run(scenario())


def test_event_pages_report_total_sequence_for_completed_invocations():
    async def scenario():
        owner = host(Documents(), Handler())
        data = {
            "agent_name": "agent",
            "invocation_id": "id",
            "thread_id": "thread",
            "owner": "owner",
            "status": "SUCCEEDED",
            "events": [{"event": "message", "data": str(i)} for i in range(70)],
        }
        first = await owner._view(data)
        second = await owner._view(data, 64)
        assert first.last_sequence == second.last_sequence == 70
        assert len(first.events) == 64 and len(second.events) == 6
        assert second.events[-1].sequence == 70

    asyncio.run(scenario())


def test_zero_deadline_leaves_execution_under_caller_control():
    async def scenario():
        docs, handler = Documents(), Handler()
        owner = host(docs, handler)
        submitted = request()
        submitted.deadline_seconds = 0
        owner._deadline = AsyncMock(side_effect=AssertionError("Unexpected deadline"))
        await owner._submit("agent", "key", "caller", submitted)
        await asyncio.sleep(0)
        assert handler.calls == 1
        owner._deadline.assert_not_called()
        handler.finish.set()
        await asyncio.gather(*(run.task for run in owner.runs.values()))
        assert any(
            doc.data.get("status") == "SUCCEEDED" for doc in docs.values.values()
        )

    asyncio.run(scenario())


def test_large_events_and_long_runs_preserve_output_in_bounded_documents():
    from naas_abi_sdk.agent_host import _hash

    async def scenario():
        docs, handler = Documents(), Handler()
        owner = host(docs, handler)
        key = _hash("agent", "id")
        await owner._submit("agent", key, "caller", request())
        run = owner.runs[key]
        large = "\N{SNOWMAN}" * 50000
        await owner._event(run, {"event": "call_model", "data": large})
        for _ in range(1025):
            await owner._event(run, {"event": "step", "data": "ok"})
        first = await owner._view(run.data)
        assert first.last_sequence == 1026
        assert first.events[0].parts > 1
        data = bytearray()
        for part in range(first.events[0].parts):
            data.extend(
                (await docs.get(owner.events_collection, f"{key}:1:{part}")).data[
                    "data"
                ]
            )
        assert data.decode() == large
        assert not run.data["events"]
        assert all(
            len(doc.data["data"]) <= 8192
            for doc in docs.values.values()
            if "data" in doc.data
        )
        await owner._view(run.data, 64)
        owner.session.client.get_module.assert_awaited_once()
        handler.finish.set()
        await run.task
        assert run.data["status"] == "SUCCEEDED"

    asyncio.run(scenario())


def test_failed_rebind_rolls_back_partial_subscriptions():
    async def scenario():
        owner = host(Documents(), Handler())
        previous, partial = AsyncMock(), AsyncMock()
        owner.subscriptions = [previous]
        nc = AsyncMock()
        nc.subscribe.side_effect = [partial, ConnectionError("subscription failed")]
        owner.session.client.transport = SimpleNamespace(
            connect=AsyncMock(return_value=nc)
        )
        with pytest.raises(ConnectionError):
            await owner._bind()
        assert owner.subscriptions == [previous]
        partial.unsubscribe.assert_awaited_once()
        previous.drain.assert_not_awaited()

    asyncio.run(scenario())
