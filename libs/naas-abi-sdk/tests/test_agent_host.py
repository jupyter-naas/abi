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

WORKSPACE = "abi:nexus:organization/o-1/nexus:workspace/ws-1"


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
        service_account="sa1",
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


def test_events_keep_a_chat_source_opt_out_and_refuse_other_keys():
    from naas_abi_sdk.agent_host import _hash

    async def scenario():
        docs, handler = Documents(), Handler()
        owner = host(docs, handler)
        key = _hash("agent", "id")
        await owner._submit("agent", key, "caller", request())
        run = owner.runs[key]
        await owner._event(run, {"event": "tool_response", "data": "a"})
        await owner._event(
            run, {"event": "tool_response", "data": "b", "chat_source": False}
        )
        await owner._event(
            run, {"event": "tool_response", "data": "c", "chat_source": True}
        )
        for bad in (
            {"event": "tool_response", "data": "d", "chat_source": "no"},
            {"event": "tool_response", "data": "e", "other": 1},
        ):
            with pytest.raises(RPCError, match="INVALID_STREAM"):
                await owner._event(run, bad)

        events = (await owner._view(run.data)).events
        assert [e.HasField("chat_source") for e in events] == [False, True, False]
        assert events[1].chat_source is False
        handler.finish.set()
        await run.task

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


def test_discovery_decides_who_may_poll_or_cancel_a_run():
    from naas_abi_sdk.agent_host import _hash

    async def scenario():
        docs, handler = Documents(), Handler()
        owner = host(docs, handler)
        key = _hash("agent", "id")
        await owner._submit("agent", key, "caller", request())
        cancel = pb.CancelRequest(invocation_id="id", output_format=2)

        # Without discovery's decision on the run, another caller cannot see it.
        owner._authorize = AsyncMock(return_value=("someone", False))
        msg, sent = _rpc(owner, "cancel", cancel)
        await owner._handle_operation("agent", "cancel", msg)
        assert (
            pb.CancelResponse.FromString(sent[0]).error.code == "INVOCATION_NOT_FOUND"
        )

        # Discovery allowed this caller to cancel it (discovery:CancelAgentRun).
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
        # The run's recorded owner went to discovery with the poll.
        assert owner._authorize.call_args.args[2:] == ("cancel", "id", "caller")

    asyncio.run(scenario())


def _token(identity="caller", expires_in=3600.0):
    """A service token's shape (a JWT); the provider never checks the signature."""
    import base64
    import json
    import time

    claims = {"sub": identity, "exp": time.time() + expires_in}
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=")
    return f"header.{body.decode()}.signature"


def authorizing(identity="caller", decided=False):
    """A host whose discovery authorizes every call, counting them."""
    from naas_abi_proto.discovery.v1 import discovery_pb2 as discovery_pb

    owner = host(Documents(), Handler())
    owner.session.lease_token = "l" * 32
    owner.session.client._call = AsyncMock(
        return_value=discovery_pb.AuthorizeAgentResponse(
            caller_identity=identity, run_authorized=decided
        )
    )
    return owner


def _ask(owner, agent, token, submit):
    headers = {"Nats-Auth-Token": token}
    if submit:
        return owner._authorize(agent, headers, "submit")
    return owner._authorize(agent, headers, "status", "id", "caller")


def test_polls_reuse_discovery_authorization_and_submits_always_ask():
    async def scenario():
        owner = authorizing(decided=True)
        token = _token()
        for _ in range(5):  # status and event polls
            assert await _ask(owner, "agent", token, False) == ("caller", True)
        assert owner.session.client._call.await_count == 1
        # Every submit asks discovery (it checks the provider is READY).
        await _ask(owner, "agent", token, True)
        await _ask(owner, "agent", token, True)
        assert owner.session.client._call.await_count == 3
        # Per caller token and agent.
        await _ask(owner, "other-agent", token, False)
        await _ask(owner, "agent", _token(expires_in=60), False)
        assert owner.session.client._call.await_count == 5
        await _ask(owner, "agent", token, False)
        assert owner.session.client._call.await_count == 5
        # The user is in the token; the run's owner went with the poll.
        sent = owner.session.client._call.call_args.args[1]
        assert sent.caller_token.startswith("header.") and sent.run_owner == "caller"
        assert not hasattr(sent, "caller_on_behalf_of")

    asyncio.run(scenario())


def test_an_authorization_ends_when_the_token_expires():
    async def scenario():
        owner = authorizing()
        expiring = _token(expires_in=0.05)
        await _ask(owner, "agent", expiring, False)
        await _ask(owner, "agent", expiring, False)
        assert owner.session.client._call.await_count == 1
        await asyncio.sleep(0.1)  # well within the reuse window
        await _ask(owner, "agent", expiring, False)
        assert owner.session.client._call.await_count == 2

    asyncio.run(scenario())


def test_an_authorization_is_reused_for_a_short_window(monkeypatch):
    monkeypatch.setattr("naas_abi_sdk.agent_host.AUTHORIZATION_SECONDS", 0.05)

    async def scenario():
        owner = authorizing()
        lasting = _token()
        await _ask(owner, "agent", lasting, False)
        await _ask(owner, "agent", lasting, False)
        assert owner.session.client._call.await_count == 1
        await asyncio.sleep(0.1)
        await _ask(owner, "agent", lasting, False)
        assert owner.session.client._call.await_count == 2

    asyncio.run(scenario())


def test_refusals_and_unreadable_tokens_are_never_reused():
    async def scenario():
        owner = authorizing()
        owner.session.client._call.side_effect = RPCError("UNAUTHENTICATED", "bad")
        for _ in range(2):
            with pytest.raises(RPCError, match="UNAUTHENTICATED"):
                await _ask(owner, "agent", _token(), False)
        assert owner.session.client._call.await_count == 2

        owner = authorizing()
        for token in ("opaque", "a.bm90IGpzb24.c", _token(expires_in=-1)):
            await _ask(owner, "agent", token, False)
            await _ask(owner, "agent", token, False)
        assert owner.session.client._call.await_count == 6

    asyncio.run(scenario())


def test_remembered_authorizations_are_bounded(monkeypatch):
    monkeypatch.setattr("naas_abi_sdk.agent_host.MAX_AUTHORIZATIONS", 3)

    async def scenario():
        owner = authorizing()
        tokens = [_token(f"caller-{i}") for i in range(5)]
        for token in tokens:
            await _ask(owner, "agent", token, False)
        assert len(owner._authorized) == 3
        # The most recent ones are kept.
        await _ask(owner, "agent", tokens[-1], False)
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
                        subject="abi.agent.default.owner.agent.v1.status",
                        headers={},
                        reply="_INBOX.caller.1",
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


# -- the delegation a run executes with ----------------------------------------


def _delegation_token(sub="caller", act="sa_module", aud="abi:delegated:agent"):
    import base64
    import json
    import time

    claims = {"sub": sub, "aud": aud, "exp": time.time() + 600}
    if act is not None:
        claims["act"] = {"sub": act}
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=")
    return f"header.{body.decode()}.signature"


class Seen:
    """A handler recording the context its run executes in."""

    def __init__(self):
        from naas_abi_sdk.call_context import current_call_context

        self.current = current_call_context
        self.contexts = []

    async def invoke(self, prompt, context):
        self.contexts.append(self.current())
        return "result"


def _delegated_request(token):
    submit = request()
    submit.delegated_token = token
    return submit


def test_a_run_executes_as_the_module_for_the_user_it_was_delegated():
    from naas_abi_sdk.call_context import user

    async def scenario():
        seen = Seen()
        owner = host(Documents(), seen)
        token = _delegation_token()
        doc = await owner._submit("agent", "key", "caller", _delegated_request(token))
        await owner.runs["key"].task
        [context] = seen.contexts
        assert context.principal.id == "sa_module"
        assert context.principal.kind == "service_account"
        assert context.on_behalf_of == user("caller")
        assert context.delegated_token == token
        assert doc.data["caller"] == "caller"
        # The token is a credential: it is never written to the run's record.
        stored = await owner.documents.get(owner.runs_collection, "key")
        assert token not in repr(stored.data)

    asyncio.run(scenario())


class OwnDocuments(Documents):
    """Documents recording whether each write carried a user's delegation."""

    def __init__(self):
        super().__init__()
        self.delegated: list[str] = []

    async def put(self, collection, id, data, if_version=None):
        from naas_abi_sdk.call_context import current_call_context

        if current_call_context().delegated_token:
            self.delegated.append(f"{collection}/{id}")
        return await super().put(collection, id, data, if_version=if_version)

    async def delete(self, collection, id, if_version=None):
        from naas_abi_sdk.call_context import current_call_context

        if current_call_context().delegated_token:
            self.delegated.append(f"delete {collection}/{id}")
        return await super().delete(collection, id, if_version=if_version)


class SeenStream(Seen):
    async def stream_invoke(self, prompt, context):
        self.contexts.append(self.current())
        yield {"event": "message", "data": "one"}
        self.contexts.append(self.current())
        yield {"event": "done", "data": "[DONE]"}


@pytest.mark.parametrize("mode", ["invoke", "stream"])
def test_the_hosts_own_records_are_never_the_users(mode):
    """The run, its events and its claim are the module's records, which a user
    holds no right to: only the handler's calls carry the delegation."""

    async def scenario():
        seen, docs = SeenStream(), OwnDocuments()
        owner = host(docs, seen)
        token = _delegation_token()
        submit = _delegated_request(token)
        submit.mode = mode
        await owner._submit("agent", "key", "caller", submit)
        await owner.runs["key"].task
        assert seen.contexts and all(c.delegated_token == token for c in seen.contexts)
        assert docs.delegated == []
        stored = await docs.get(owner.runs_collection, "key")
        assert stored.data["status"] == "SUCCEEDED"

    asyncio.run(scenario())


def test_a_streaming_handler_keeps_one_context_across_its_steps():
    """What a handler sets before a yield is there after it, and every step
    (its first included) runs for the user; the host's writes never do."""
    import contextvars

    marker = contextvars.ContextVar("marker", default="unset")

    class Stateful(Seen):
        async def stream_invoke(self, prompt, context):
            marker.set("set before the first yield")
            self.contexts.append(self.current())
            yield {"event": "message", "data": "one"}
            self.contexts.append(self.current())
            self.after = marker.get()
            yield {"event": "done", "data": "[DONE]"}

    async def scenario():
        seen, docs = Stateful(), OwnDocuments()
        owner = host(docs, seen)
        token = _delegation_token()
        submit = _delegated_request(token)
        submit.mode = "stream"
        await owner._submit("agent", "key", "caller", submit)
        await owner.runs["key"].task
        assert seen.after == "set before the first yield"
        assert [c.delegated_token for c in seen.contexts] == [token, token]
        assert docs.delegated == []
        stored = await docs.get(owner.runs_collection, "key")
        assert stored.data["status"] == "SUCCEEDED"

    asyncio.run(scenario())


def test_a_streaming_handler_that_raises_fails_the_run():
    class Broken:
        async def stream_invoke(self, prompt, context):
            yield {"event": "message", "data": "one"}
            raise RuntimeError("boom")

    async def scenario():
        docs = Documents()
        owner = host(docs, Broken())
        submit = request()
        submit.mode = "stream"
        await owner._submit("agent", "key", "caller", submit)
        await owner.runs["key"].task
        stored = await docs.get(owner.runs_collection, "key")
        assert stored.data["status"] == "FAILED"

    asyncio.run(scenario())


def test_a_delegated_run_is_in_the_container_of_its_submit():
    async def scenario():
        seen = Seen()
        owner = host(Documents(), seen)
        submit = _delegated_request(_delegation_token())
        submit.context.container = WORKSPACE
        await owner._submit("agent", "key", "caller", submit)
        await owner.runs["key"].task
        [context] = seen.contexts
        assert context.container == WORKSPACE and context.user is not None

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "token",
    [
        "",
        "garbage",
        "a.b.c",
        _delegation_token(sub="someone-else"),  # not the run's owner
        _delegation_token(aud="abi:nats"),  # not a delegation
        _delegation_token(aud="abi:session"),
        _delegation_token(act=None),  # names no module
    ],
)
def test_a_delegation_that_is_not_for_the_run_owner_is_dropped(token):
    async def scenario():
        seen = Seen()
        owner = host(Documents(), seen)
        await owner._submit("agent", "key", "caller", _delegated_request(token))
        await owner.runs["key"].task
        [context] = seen.contexts
        assert context.delegated_token is None and context.user is None

    asyncio.run(scenario())


ULID = "01J8Z3K5M7N9P2Q4R6S8T0V2WX"


def test_a_delegation_names_this_hosts_own_account_or_is_dropped():
    """A submitter may hand over a delegation made for another module (it is
    verified by the engine, but it is not this host's to carry): only one that
    names this host's own account as the actor becomes the run's context."""

    async def scenario(actor, kept):
        seen = Seen()
        owner = host(Documents(), seen)
        owner.session.service_account = ULID
        token = _delegation_token(act=actor)
        await owner._submit("agent", "key", "caller", _delegated_request(token))
        await owner.runs["key"].task
        [context] = seen.contexts
        assert (context.delegated_token == token) is kept
        assert (context.user is not None) is kept

    asyncio.run(scenario(f"sa_{ULID}", True))
    asyncio.run(scenario("sa_01J8Z3K5M7N9P2Q4R6S8T0V2WY", False))
    asyncio.run(scenario("engine", False))
