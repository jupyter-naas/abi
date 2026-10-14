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


def host(documents, handler, owner="owner", live=None):
    listed = (owner,) if live is None else live
    session = SimpleNamespace(
        instance_id=owner,
        descriptor=SimpleNamespace(module_id="provider", contract_major=1),
        client=SimpleNamespace(
            project="default",
            get_module=AsyncMock(
                return_value=[SimpleNamespace(instance_id=i) for i in listed]
            ),
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
        live = ("owner", "replica")
        a, b = host(docs, handler, live=live), host(docs, handler, "replica", live)
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
        replacement = host(docs, handler, "replacement", ("owner", "replacement"))
        existing = await replacement._submit("agent", "key", "caller", request())
        assert existing.data["status"] == "RUNNING"
        assert handler.calls == 0
        conflict = await replacement._submit("agent", "next", "caller", request("next"))
        assert conflict.data["error_code"] == "CONVERSATION_BUSY"

    asyncio.run(scenario())


def test_absent_discovery_owner_releases_the_conversation_claim():
    async def scenario():
        docs, handler = Documents(), Handler()
        docs.lose_running_reply = True
        original = host(docs, handler)
        with pytest.raises(ConnectionError):
            await original._submit("agent", "key", "caller", request())
        docs.lose_running_reply = False
        replacement = host(docs, handler, "replacement", ("replacement",))
        taken = await replacement._submit("agent", "next", "caller", request("next"))
        assert taken.data["status"] == "RUNNING"
        assert taken.data["owner"] == "replacement"
        await asyncio.sleep(0)
        assert handler.calls == 1
        abandoned = await docs.get(replacement.runs_collection, "key")
        assert abandoned.data["status"] == "FAILED"
        assert abandoned.data["error_code"] == "OWNER_GONE"
        again = await replacement._submit("agent", "key", "caller", request())
        assert again.data["status"] == "FAILED"
        assert handler.calls == 1
        handler.finish.set()
        await asyncio.gather(*(run.task for run in replacement.runs.values()))

    asyncio.run(scenario())


def test_discovery_lookup_failure_keeps_the_conversation_claim():
    async def scenario():
        docs, handler = Documents(), Handler()
        docs.lose_running_reply = True
        original = host(docs, handler)
        with pytest.raises(ConnectionError):
            await original._submit("agent", "key", "caller", request())
        docs.lose_running_reply = False
        replacement = host(docs, handler, "replacement", ())
        replacement.session.client.get_module.side_effect = RPCError(
            "UNAVAILABLE", "discovery down"
        )
        conflict = await replacement._submit("agent", "next", "caller", request("next"))
        assert conflict.data["error_code"] == "CONVERSATION_BUSY"
        assert handler.calls == 0

    asyncio.run(scenario())


def test_process_accepts_200_runs_and_rejects_the_next():
    async def scenario():
        from naas_abi_sdk.agent_host import MAX_ACTIVE_RUNS

        docs, handler = Documents(), Handler()
        owner = host(docs, handler)
        for i in range(MAX_ACTIVE_RUNS):
            await owner._submit(
                "agent",
                f"key-{i}",
                "caller",
                pb.SubmitRequest(
                    invocation_id=f"id-{i}",
                    thread_id=f"thread-{i}",
                    prompt="hello",
                    mode="invoke",
                    deadline_seconds=10,
                ),
            )
        assert len(owner.runs) == MAX_ACTIVE_RUNS
        with pytest.raises(RPCError, match="AGENT_BUSY"):
            await owner._submit(
                "agent",
                "overflow",
                "caller",
                pb.SubmitRequest(
                    invocation_id="overflow",
                    thread_id="thread-overflow",
                    prompt="hello",
                    mode="invoke",
                    deadline_seconds=10,
                ),
            )
        handler.finish.set()
        await asyncio.gather(*(run.task for run in list(owner.runs.values())))

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


def test_registering_again_under_the_same_id_keeps_the_endpoints():
    async def scenario():
        owner = host(Documents(), Handler())
        nc = AsyncMock()
        first = [AsyncMock() for _ in range(4)]  # submit, status, cancel, event
        nc.subscribe.side_effect = first
        owner.session.client.transport = SimpleNamespace(
            connect=AsyncMock(return_value=nc)
        )
        await owner._bind()
        # Discovery lost the lease and the session registered the same id again.
        await owner._bind()
        assert owner.subscriptions == first
        assert nc.subscribe.await_count == 4
        for sub in first:
            sub.drain.assert_not_awaited()
        # A different instance id still moves the endpoints.
        owner.session.instance_id = "moved"
        nc.subscribe.side_effect = [AsyncMock() for _ in range(4)]
        await owner._bind()
        assert nc.subscribe.await_count == 8
        for sub in first:
            sub.drain.assert_awaited_once()

    asyncio.run(scenario())


def test_no_deadline_agent_times_out_after_inactivity_and_releases_slot():
    async def scenario():
        docs, handler = Documents(), Handler()
        owner = host(docs, handler)
        owner.idle_timeout_seconds = 0.02
        req = request()
        req.deadline_seconds = 0
        await owner._submit("agent", "key", "caller", req)
        task = owner.runs["key"].task
        await asyncio.wait_for(task, 1)
        assert not owner.runs
        assert (await docs.get(owner.runs_collection, "key")).data[
            "status"
        ] == "TIMED_OUT"
        assert not any(c == owner.locks_collection for c, _ in docs.values)

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["invoke", "stream"])
def test_a_deadline_governs_a_run_that_reports_no_progress(mode):
    # Only invoke: a stream request runs it unstreamed too, with no events.
    class Slow:
        async def invoke(self, prompt, context):
            await asyncio.sleep(0.1)
            return "slow answer"

    async def scenario():
        docs = Documents()
        owner = host(docs, Slow())
        owner.idle_timeout_seconds = 0.02
        req = request()  # a 10 s deadline, far above the run's 0.1 s
        req.mode = mode
        await owner._submit("agent", "key", "caller", req)
        await asyncio.wait_for(owner.runs["key"].task, 1)
        done = (await docs.get(owner.runs_collection, "key")).data
        assert (done["status"], done["error_code"]) == ("SUCCEEDED", "")

    asyncio.run(scenario())


def test_active_stream_outlives_inactivity_budget():
    class StreamingHandler:
        async def stream_invoke(self, prompt, context):
            for _ in range(8):
                await asyncio.sleep(0.01)
                yield {"event": "message", "data": "token"}
            yield {"event": "done", "data": "[DONE]"}

    async def scenario():
        docs = Documents()
        owner = host(docs, StreamingHandler())
        owner.idle_timeout_seconds = 0.05
        req = request()
        req.mode, req.deadline_seconds = "stream", 0
        await owner._submit("agent", "key", "caller", req)
        await asyncio.wait_for(owner.runs["key"].task, 1)
        assert (await docs.get(owner.runs_collection, "key")).data[
            "status"
        ] == "SUCCEEDED"

    asyncio.run(scenario())


def test_records_carry_their_times_in_collections_named_by_project():
    from naas_abi_sdk.agent_host import (
        agent_events_collection,
        agent_runs_collection,
    )

    async def scenario():
        docs, handler = Documents(), Handler()
        owner = host(docs, handler)
        assert owner.runs_collection == agent_runs_collection("default")
        assert owner.events_collection == agent_events_collection("default")
        await owner._submit("agent", "key", "caller", request())
        running = (await docs.get(owner.runs_collection, "key")).data
        assert datetime.fromisoformat(running["submitted_at"]).tzinfo is not None
        assert "finished_at" not in running and "trace_id" in running
        run = owner.runs["key"]
        handler.finish.set()
        await run.task
        done = (await docs.get(owner.runs_collection, "key")).data
        assert done["status"] == "SUCCEEDED"
        assert done["finished_at"] >= done["submitted_at"]

    asyncio.run(scenario())


def _rpc(owner, operation, message):
    sent = []

    async def publish(subject, data, headers=None):
        sent.append(data)

    msg = SimpleNamespace(
        subject=f"abi.agent.default.owner.x.v1.{operation}",
        data=message.SerializeToString(),
        headers={"Nats-Auth-Token": "token"},
        reply="_INBOX.1",
        _client=SimpleNamespace(max_payload=1 << 20, publish=publish),
    )
    owner.session.client.transport = SimpleNamespace(
        connect=AsyncMock(return_value=SimpleNamespace(max_payload=1 << 20))
    )
    return msg, sent


def test_platform_admins_may_cancel_another_callers_run():
    from naas_abi_sdk.agent_host import _hash

    async def scenario():
        docs, handler = Documents(), Handler()
        owner = host(docs, handler)
        key = _hash("agent", "id")
        await owner._submit("agent", key, "caller", request())
        cancel = pb.CancelRequest(invocation_id="id", output_format=2)

        # Another caller is refused.
        owner._authorize = AsyncMock(return_value=("someone", False))
        msg, sent = _rpc(owner, "cancel", cancel)
        await owner._handle_operation("agent", "cancel", msg)
        assert pb.CancelResponse.FromString(sent[0]).error.code == "PERMISSION_DENIED"

        # A platform admin (discovery's admin identities) may cancel it.
        task = owner.runs[key].task
        owner._authorize = AsyncMock(return_value=("api", True))
        msg, sent = _rpc(owner, "cancel", cancel)
        await owner._handle_operation("agent", "cancel", msg)
        response = pb.CancelResponse.FromString(sent[0])
        assert not response.HasField("error"), response.error
        await task
        assert (await docs.get(owner.runs_collection, key)).data[
            "status"
        ] == "CANCELLED"

        # Admin rights cover cancelling only, not reading someone's output.
        status = pb.StatusRequest(invocation_id="id", output_format=2)
        msg, sent = _rpc(owner, "status", status)
        await owner._handle_operation("agent", "status", msg)
        assert pb.StatusResponse.FromString(sent[0]).error.code == "PERMISSION_DENIED"

    asyncio.run(scenario())


def _token(identity="caller", expires_in=3600.0):
    """A service token's shape (a JWT); the provider never checks the signature."""
    import base64
    import json
    import time

    claims = {"sub": identity, "exp": time.time() + expires_in}
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=")
    return f"header.{body.decode()}.signature"


def authorizing(identity="caller", admin=False):
    """A host whose discovery authorizes every call, counting them."""
    from naas_abi_proto.discovery.v1 import discovery_pb2 as discovery_pb

    owner = host(Documents(), Handler())
    owner.session.lease_token = "l" * 32
    owner.session.client._call = AsyncMock(
        return_value=discovery_pb.AuthorizeAgentResponse(
            caller_identity=identity, caller_admin=admin
        )
    )
    return owner


def test_polls_reuse_discovery_authorization_and_submits_always_ask():
    async def scenario():
        owner = authorizing(admin=True)
        token = _token()
        for _ in range(5):  # status and event polls
            assert await owner._authorize("agent", token, False) == ("caller", True)
        assert owner.session.client._call.await_count == 1
        # Every submit asks discovery (it checks the provider is READY).
        await owner._authorize("agent", token, True)
        await owner._authorize("agent", token, True)
        assert owner.session.client._call.await_count == 3
        # Per caller token and agent.
        await owner._authorize("other-agent", token, False)
        await owner._authorize("agent", _token(expires_in=60), False)
        assert owner.session.client._call.await_count == 5
        await owner._authorize("agent", token, False)
        assert owner.session.client._call.await_count == 5

    asyncio.run(scenario())


def test_an_authorization_ends_when_the_token_expires():
    async def scenario():
        owner = authorizing()
        expiring = _token(expires_in=0.05)
        await owner._authorize("agent", expiring, False)
        await owner._authorize("agent", expiring, False)
        assert owner.session.client._call.await_count == 1
        await asyncio.sleep(0.1)  # well within the reuse window
        await owner._authorize("agent", expiring, False)
        assert owner.session.client._call.await_count == 2

    asyncio.run(scenario())


def test_an_authorization_is_reused_for_a_short_window(monkeypatch):
    monkeypatch.setattr("naas_abi_sdk.agent_host.AUTHORIZATION_SECONDS", 0.05)

    async def scenario():
        owner = authorizing()
        lasting = _token()
        await owner._authorize("agent", lasting, False)
        await owner._authorize("agent", lasting, False)
        assert owner.session.client._call.await_count == 1
        await asyncio.sleep(0.1)
        await owner._authorize("agent", lasting, False)
        assert owner.session.client._call.await_count == 2

    asyncio.run(scenario())


def test_refusals_and_unreadable_tokens_are_never_reused():
    async def scenario():
        owner = authorizing()
        owner.session.client._call.side_effect = RPCError("UNAUTHENTICATED", "bad")
        for _ in range(2):
            with pytest.raises(RPCError, match="UNAUTHENTICATED"):
                await owner._authorize("agent", _token(), False)
        assert owner.session.client._call.await_count == 2

        owner = authorizing()
        for token in ("opaque", "a.bm90IGpzb24.c", _token(expires_in=-1)):
            await owner._authorize("agent", token, False)
            await owner._authorize("agent", token, False)
        assert owner.session.client._call.await_count == 6

    asyncio.run(scenario())


def test_remembered_authorizations_are_bounded(monkeypatch):
    monkeypatch.setattr("naas_abi_sdk.agent_host.MAX_AUTHORIZATIONS", 3)

    async def scenario():
        owner = authorizing()
        tokens = [_token(f"caller-{i}") for i in range(5)]
        for token in tokens:
            await owner._authorize("agent", token, False)
        assert len(owner._authorized) == 3
        # The most recent ones are kept.
        await owner._authorize("agent", tokens[-1], False)
        assert owner.session.client._call.await_count == 5

    asyncio.run(scenario())


def test_status_polls_over_rpc_reach_discovery_once():
    from naas_abi_sdk.agent_host import _hash

    async def scenario():
        owner = authorizing()
        docs = owner.documents
        key = _hash("agent", "id")
        await owner._submit("agent", key, "caller", request())
        token = _token()
        for _ in range(3):
            msg, sent = _rpc(
                owner, "status", pb.StatusRequest(invocation_id="id", output_format=2)
            )
            msg.headers["Nats-Auth-Token"] = token
            await owner._handle_operation("agent", "status", msg)
            assert pb.StatusResponse.FromString(sent[0]).invocation.status == "RUNNING"
        assert owner.session.client._call.await_count == 1
        owner.handlers["agent"].finish.set()
        await owner.runs[key].task
        assert (await docs.get(owner.runs_collection, key)).data["status"] == (
            "SUCCEEDED"
        )

    asyncio.run(scenario())


class Wire:
    """The owner's connection, recording what it publishes."""

    max_payload = 1024 * 1024

    def __init__(self, fail=False):
        self.published, self.fail = [], fail

    async def publish(self, subject, payload=b"", **kwargs):
        if self.fail:
            raise ConnectionError("broker gone")
        self.published.append((subject, pb.RunUpdate.FromString(payload)))


class Streaming:
    def __init__(self):
        self.go = asyncio.Event()

    async def stream_invoke(self, prompt, context):
        yield {"event": "message", "data": "small"}
        await self.go.wait()
        yield {"event": "message", "data": "x" * 40_000}  # above the inline bound


def watched(documents, handler, wire):
    owner = host(documents, handler)
    owner.session.client.transport = SimpleNamespace(
        connect=AsyncMock(return_value=wire)
    )
    return owner


def streaming_request(inbox, id="id"):
    req = request(id)
    req.mode, req.updates_inbox = "stream", inbox
    return req


def test_owner_pushes_committed_events_then_the_terminal_status():
    async def scenario():
        docs, wire, handler = Documents(), Wire(), Streaming()
        owner = watched(docs, handler, wire)
        await owner._submit("agent", "key", "caller", streaming_request("_INBOX.a.1"))
        # A second submit of the same invocation watches it too.
        await owner._submit("agent", "key", "caller", streaming_request("_INBOX.b.2"))
        handler.go.set()
        await asyncio.gather(*(r.task for r in owner.runs.values()))

        assert {subject for subject, _ in wire.published} == {
            "_INBOX.a.1",
            "_INBOX.b.2",
        }
        updates = [u for subject, u in wire.published if subject == "_INBOX.a.1"]
        events = [u.event for u in updates if u.HasField("event")]
        assert [(e.sequence, e.event) for e in events] == [
            (1, "message"),
            (2, "message"),
            (3, "done"),
        ]
        assert (events[0].data, events[0].parts) == ("small", 0)
        assert (events[1].data, events[1].parts) == ("", 5)  # read with EventRequest
        end = updates[-1]
        assert not end.HasField("event")
        assert (end.status, end.last_sequence) == ("SUCCEEDED", 3)
        # By then a status read reports the end, not FINALIZING.
        doc = await docs.get(owner.runs_collection, "key")
        assert (await owner._view(doc.data, 3)).status == "SUCCEEDED"

    asyncio.run(scenario())


def test_updates_go_only_to_an_inbox():
    async def scenario():
        owner = watched(Documents(), Handler(), Wire())
        with pytest.raises(RPCError, match="INVALID_ARGUMENT"):
            await owner._submit(
                "agent", "key", "caller", streaming_request("abi.svc.secret.v1.get")
            )

    asyncio.run(scenario())


def test_a_failed_push_never_fails_the_run():
    async def scenario():
        docs, handler = Documents(), Streaming()
        handler.go.set()
        owner = watched(docs, handler, Wire(fail=True))
        await owner._submit("agent", "key", "caller", streaming_request("_INBOX.a.1"))
        await asyncio.gather(*(r.task for r in owner.runs.values()))
        doc = await docs.get(owner.runs_collection, "key")
        assert doc.data["status"] == "SUCCEEDED"

    asyncio.run(scenario())


def test_drain_lets_a_live_run_finish():
    async def scenario():
        owner = host(Documents(), Handler())
        release = asyncio.Event()

        async def run():
            await release.wait()

        task = asyncio.create_task(run())
        owner.runs["key"] = SimpleNamespace(task=task)
        draining = asyncio.create_task(owner.drain(1))
        await asyncio.sleep(0)
        assert owner.closing is True
        assert not task.done()
        release.set()
        await draining
        assert task.done() and not task.cancelled()

    asyncio.run(scenario())


def _bound(owner):
    """Bind ``owner`` to a connection that records its subscription callbacks."""
    callbacks = {}

    async def subscribe(subject, cb=None, **kwargs):
        callbacks[subject.rsplit(".", 1)[-1]] = cb
        return AsyncMock()

    nc = SimpleNamespace(subscribe=subscribe, flush=AsyncMock())
    owner.session.client.transport = SimpleNamespace(connect=AsyncMock(return_value=nc))
    return callbacks


def test_calls_run_side_by_side_and_close_answers_them_first():
    async def scenario():
        owner = host(Documents(), Handler())
        callbacks = _bound(owner)
        await owner._bind()
        release, running = asyncio.Event(), []

        async def handle_operation(name, operation, msg):
            running.append(operation)
            await release.wait()

        owner._handle_operation = handle_operation
        for _ in range(3):
            # Returns at once: one call at a time would block here.
            await asyncio.wait_for(
                callbacks["status"](
                    SimpleNamespace(
                        subject="abi.agent.default.owner.agent.v1.status", headers={}
                    )
                ),
                timeout=1,
            )
        for _ in range(100):
            if len(running) == 3:
                break
            await asyncio.sleep(0.01)
        assert running == ["status"] * 3  # one at a time would leave two waiting
        closing = asyncio.create_task(owner.close())
        await asyncio.sleep(0.05)
        assert not closing.done()
        release.set()
        await asyncio.wait_for(closing, timeout=2)

    asyncio.run(scenario())
