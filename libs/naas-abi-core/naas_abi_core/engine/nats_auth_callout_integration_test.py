"""Modules confined by the broker: the engine answers nats-server's auth callout.

A real ``nats-server`` with ``auth_callout``, the engine's responder and IAM in
this process, and modules logging in with their service keys through the SDK
transport (docs/specs/rfcs/20261013_identity-and-authorization.md, §8.4).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import secrets
from datetime import UTC, datetime

import nats
import pytest
from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    as_service_account,
    use_call_context,
)
from naas_abi_core.engine.nats_auth_callout import AuthCallout
from naas_abi_core.engine.nats_broker_control import BrokerControl
from naas_abi_core.engine.nats_nkeys import KeyPair
from naas_abi_core.engine.nats_test_server import (
    native_nats_server,
    nats_server_binary,
)
from naas_abi_core.services.iam import broker
from naas_abi_core.services.iam.adapters.primary.iam__primary_adapter__NATS import (
    IAMPrimaryAdapterNATS,
)
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import (
    IAMStoreMemory,
)
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.modules import subject_token
from naas_abi_proto.iam.v1 import iam_pb2 as pb
from naas_abi_proto.keyvalue.v1 import keyvalue_pb2 as kv_pb
from naas_abi_sdk.bus import BusClient
from naas_abi_sdk.transport import RPCError, Transport

pytestmark = pytest.mark.skipif(
    nats_server_binary() is None, reason="nats-server is not installed"
)

KV_GET = "abi.svc.keyvalue.v1.get"
KV_SET = "abi.svc.keyvalue.v1.set"
# Small, so payloads above it are cheap to make: claim checks and overflow.
MAX_PAYLOAD = 64 * 1024
DOCUMENT = {
    "version": "2026-10-13",
    "statements": [
        {
            "effect": "Allow",
            "actions": ["keyvalue:*"],
            "resources": ["abi:*:*:keyvalue:*"],
        }
    ],
}


@pytest.fixture
def stack(tmp_path):
    """A broker asking the engine about every connection but its own."""
    engine_pw, auth_pw = secrets.token_urlsafe(16), secrets.token_urlsafe(16)
    issuer = KeyPair.create()
    config = (
        "authorization {\n  users = [\n"
        f'    {{ user: engine, password: "{engine_pw}", permissions: '
        '{ publish: { deny: ["$SYS.>"] }, subscribe: { deny: ["$SYS.>"] } } }\n'
        f'    {{ user: auth, password: "{auth_pw}", permissions: '
        '{ subscribe: "$SYS.REQ.USER.AUTH", allow_responses: true } }\n'
        "  ]\n"
        f"  auth_callout {{ issuer: {issuer.public_key}, auth_users: [engine, auth] }}\n"
        "}\n"
    )
    with native_nats_server(
        tmp_path, config=config, jetstream=True, max_payload=MAX_PAYLOAD
    ) as url:
        host = url.removeprefix("nats://")
        iam = IAMService(IAMStoreMemory())
        iam.bootstrap()
        yield {
            "url": url,
            "engine": f"nats://engine:{engine_pw}@{host}",
            "auth": f"nats://auth:{auth_pw}@{host}",
            "issuer": issuer,
            "iam": iam,
        }


def module(iam: IAMService, name: str) -> tuple[str, str]:
    """A module's account and a key for it."""
    with as_service_account("engine"):
        account = iam.create_service_account(name)
        return account.id, iam.create_key(account.id).value


def approve(iam: IAMService, account_id: str, name: str, document=DOCUMENT) -> None:
    project, module_id = name.split("/")[1:]
    with use_call_context(
        CallContext(principal=Principal(account_id, "service_account", name))
    ):
        iam.submit_manifest(module_id, project, document)
    with as_service_account("engine"):
        iam.approve_manifest(account_id)


def run(stack, scenario, **callout_options):
    async def main():
        from naas_abi_core.engine import nats_overflow
        from naas_abi_core.engine.nats_rpc import request_payload

        engine = await nats.connect(stack["engine"])
        callout = AuthCallout(
            stack["iam"], stack["issuer"].seed, stack["auth"], **callout_options
        )
        await callout.start()
        control = BrokerControl(stack["iam"], stack["iam"].verifier(), stack["engine"])
        await control.start()
        primary = IAMPrimaryAdapterNATS(stack["iam"], stack["iam"].verifier())
        await primary.start(engine)
        overflow = nats_overflow.OverflowHost(stack["iam"].verifier())
        await overflow.start(engine)
        nats_overflow.install(overflow)
        served: list[str] = []

        async def kernel(msg):  # a kernel service the engine serves
            served.append(msg.subject)
            if msg.subject == KV_SET:  # read the body, from its upload if overflowed
                request = kv_pb.SetRequest.FromString(await request_payload(msg))
                served.append(len(request.value))
            await msg.respond(b"")

        await engine.subscribe(KV_GET, cb=kernel)
        await engine.subscribe(KV_SET, cb=kernel)
        await engine.flush()
        try:
            return await scenario(served)
        finally:
            await overflow.stop()
            await primary.stop()
            await control.stop()
            await callout.stop()
            await engine.close()

    return asyncio.run(main())


async def denied(transport: Transport, subject: str) -> bool:
    """True when the broker refuses this connection's request on ``subject``."""
    errors: list[str] = []
    nc = await transport.connect()
    nc._error_cb = _collect(errors)  # nats-py reports the violation here
    with contextlib.suppress(Exception):  # a refused publish gets no reply
        await nc.request(subject, b"", timeout=1)
    await asyncio.sleep(0.1)
    return any(
        "Permissions Violation" in e or "permissions violation" in e for e in errors
    )


def _collect(errors: list[str]):
    async def collect(error):
        errors.append(str(error))

    return collect


def test_an_unapproved_module_reaches_iam_only_then_its_approved_services(stack):
    iam = stack["iam"]
    account, key = module(iam, "module/default/people")

    async def scenario(served):
        transport = Transport(stack["url"], key, timeout=2)
        try:
            # Its key is exchanged over the connection the callout admitted.
            token = await transport.access_token()
            claims = iam.verifier().verify(token)
            assert claims.subject == account and claims.name == "module/default/people"
            # Refused at the broker before approval...
            assert await denied(transport, KV_GET)
            assert served == []
            # ...and by IAM: the service would refuse it too.
            with use_call_context(
                CallContext(
                    principal=Principal(account, "service_account", claims.name)
                )
            ):
                assert not iam.authorize(
                    "keyvalue:Get", "abi:-:-:keyvalue:key/x"
                ).allowed
            approve(iam, account, "module/default/people")
            # The connection keeps its permissions until it reconnects.
            await transport.reconnect()
            await (await transport.connect()).request(KV_GET, b"", timeout=2)
            assert served == [KV_GET]
        finally:
            await transport.close()

    run(stack, scenario)


def test_a_module_serves_its_own_hosting_subjects_only(stack):
    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    other, _ = module(iam, "module/default/billing")
    approve(iam, account, "module/default/people")

    async def scenario(served):
        transport = Transport(stack["url"], key, timeout=2)
        try:
            nc = await transport.connect()
            errors: list[str] = []
            nc._error_cb = _collect(errors)
            await nc.subscribe(
                f"abi.agent.default.{subject_token(account)}.i.h.v1.submit"
            )
            await nc.flush()
            assert errors == []
            await nc.subscribe(
                f"abi.agent.default.{subject_token(other)}.i.h.v1.submit"
            )
            await nc.flush()
            await asyncio.sleep(0.1)
            assert any("ermissions" in e for e in errors)
            # Nor may it call another module's agent: no InvokeAgent was approved.
            assert await denied(
                transport, f"abi.agent.default.{subject_token(other)}.i.h.v1.submit"
            )
            # Nor read replies sent to other connections: its own inboxes only.
            errors.clear()
            nc._error_cb = _collect(errors)
            await nc.subscribe("_INBOX.>")
            await nc.flush()
            await asyncio.sleep(0.1)
            assert any("ermissions" in e for e in errors)
        finally:
            await transport.close()

    run(stack, scenario)


def test_a_revoked_key_connects_and_exchanges_no_more(stack):
    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    approve(iam, account, "module/default/people")

    async def scenario(served):
        transport = Transport(stack["url"], key, timeout=2)
        try:
            await transport.access_token()
            with as_service_account("engine"):
                iam.revoke_key(account, key.split("_")[2])
            # The next exchange fails...
            nc = await transport.connect()
            reply = await nc.request(
                "abi.iam.v1.token",
                pb.TokenRequest(key=key).SerializeToString(),
                timeout=2,
            )
            assert (
                pb.TokenResponse.FromString(reply.data).error.code == "UNAUTHENTICATED"
            )
        finally:
            await transport.close()
        # ...and so does the next connection.
        with pytest.raises(Exception):
            await nats.connect(
                stack["url"],
                user="sa",
                password=key,
                allow_reconnect=False,
                max_reconnect_attempts=0,
            )

    run(stack, scenario)


def test_no_key_or_password_logs_in_and_no_module_signs_as_api(stack):
    iam = stack["iam"]
    _, key = module(iam, "module/default/people")

    async def scenario(served):
        for user, password in (
            ("sa", "abi_sk_aaaaaaaaaaaaaaaa_nope"),
            ("engine", "guess"),
        ):
            with pytest.raises(Exception):
                await nats.connect(
                    stack["url"],
                    user=user,
                    password=password,
                    allow_reconnect=False,
                    max_reconnect_attempts=0,
                )
        # A module's key only ever yields the module's own token.
        transport = Transport(stack["url"], key, timeout=2)
        try:
            claims = iam.verifier().verify(await transport.access_token())
            assert claims.name == "module/default/people"
            with pytest.raises(RPCError):
                await transport.call(
                    "abi.iam.v1.create_service_account",
                    pb.CreateServiceAccountRequest(name="api2"),
                    pb.CreateServiceAccountResponse,
                )
        finally:
            await transport.close()

    run(stack, scenario)


def test_no_module_publishes_iam_change_notices(stack):
    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    approve(iam, account, "module/default/people")

    async def scenario(served):
        transport = Transport(stack["url"], key, timeout=2)
        try:
            # It would drop every engine's IAM cache on each message.
            assert await denied(transport, "abi.iam.v1.changed")
            assert await denied(transport, "abi.iam.v1.anything_else")
        finally:
            await transport.close()

    run(stack, scenario)


# -- bus queues: the engine creates the streams ------------------------------------------

TOPIC = "demo.inbox"
BUS = {
    "version": "2026-10-13",
    "statements": [
        {
            "effect": "Allow",
            "actions": ["bus:*"],
            "resources": [f"abi:-:-:bus:topic/{TOPIC}"],
        }
    ],
}


def test_a_module_uses_its_topic_queue_and_cannot_capture_other_subjects(stack):
    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    approve(iam, account, "module/default/people", BUS)
    stream = broker.bus_stream(TOPIC)

    async def scenario(served):
        transport = Transport(stack["url"], key, timeout=2)
        try:
            bus = BusClient(transport)
            big = os.urandom(3 * MAX_PAYLOAD)  # a claim check, under its topic
            await bus.enqueue(TOPIC, "a", b"small")
            await bus.enqueue(TOPIC, "a", big)
            queue = await bus.dequeue(TOPIC, "a")
            got = [m.data for m in await queue.fetch(2, timeout=5)]
            assert got == [b"small", big]
            # Its stream exists (the engine made it), and it may change none:
            # a stream's subjects travel in the body, which the broker never reads.
            capture = json.dumps(
                {"name": stream, "subjects": ["abi.iam.v1.token", "_INBOX.>"]}
            ).encode()
            nc = await transport.connect()
            for subject in (
                f"$JS.API.STREAM.UPDATE.{stream}",
                f"$JS.API.STREAM.CREATE.{stream}",
                "$JS.API.STREAM.CREATE.capture",
                f"$JS.API.STREAM.PURGE.{stream}",
            ):
                errors: list[str] = []
                nc._error_cb = _collect(errors)
                with contextlib.suppress(Exception):
                    await nc.request(subject, capture, timeout=1)
                await asyncio.sleep(0.1)
                assert any("ermissions" in e for e in errors), subject
            info = (
                await (await nats.connect(stack["engine"]))
                .jetstream()
                .stream_info(stream)
            )
            assert info.config.subjects == [f"{TOPIC}.>"]
            # Nor read the claim checks of a topic it was not granted.
            assert await denied(
                transport,
                f"$JS.API.DIRECT.GET.ABI_CLAIM_CHECKS."
                f"{broker.topic_claim_subjects('other.topic')[:-2]}.x.0",
            )
        finally:
            await transport.close()

    run(stack, scenario)


def test_a_topic_under_a_platform_root_is_refused_and_reaches_nothing(stack):
    from naas_abi_core.services.iam.policy import PolicyValidationError

    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    wide = {
        "version": "2026-10-13",
        "statements": [
            {
                "effect": "Allow",
                "actions": ["bus:*"],
                "resources": ["abi:-:-:bus:topic/abi"],
            }
        ],
    }
    with pytest.raises(PolicyValidationError):
        approve(iam, account, "module/default/people", wide)
    approve(iam, account, "module/default/people", BUS)

    async def scenario(served):
        transport = Transport(stack["url"], key, timeout=2)
        try:
            nc = await transport.connect()
            for subject in ("abi.>", "_INBOX.>", "$JS.>", ">"):
                errors: list[str] = []
                nc._error_cb = _collect(errors)
                await nc.subscribe(subject)
                await nc.flush()
                await asyncio.sleep(0.1)
                assert any("ermissions" in e for e in errors), subject
        finally:
            await transport.close()

    run(stack, scenario)


# -- payloads above the broker limit ----------------------------------------------------


def test_a_large_request_overflows_through_the_callout(stack):
    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    approve(iam, account, "module/default/people")

    async def scenario(served):
        transport = Transport(stack["url"], key, timeout=5)
        try:
            value = os.urandom(3 * MAX_PAYLOAD)
            await transport.call(
                KV_SET, kv_pb.SetRequest(key="k", value=value), kv_pb.SetResponse
            )
            assert served == [KV_SET, len(value)]
        finally:
            await transport.close()

    run(stack, scenario)


# -- jobs ---------------------------------------------------------------------------------


class Runs:
    """The job host's run records: a document store in memory."""

    def __init__(self):
        self.data = {}

    async def ensure_collection(self, spec):
        return None

    async def get(self, collection, id):
        from naas_abi_sdk.services.errors import DocumentNotFound

        try:
            return self.data[(collection, id)]
        except KeyError:
            raise DocumentNotFound("NOT_FOUND", id) from None

    async def put(self, collection, id, data, *, if_version=None):
        from naas_abi_sdk.services.errors import VersionConflict
        from naas_abi_sdk.services.models import Document

        current = self.data.get((collection, id))
        if if_version == 0 and current is not None:
            raise VersionConflict("VERSION_CONFLICT", id)
        if if_version and (current is None or current.version != if_version):
            raise VersionConflict("VERSION_CONFLICT", id)
        now = datetime.now(UTC)
        doc = Document(
            id=id,
            data=json.loads(json.dumps(data)),
            created_at=current.created_at if current else now,
            updated_at=now,
            version=(current.version + 1) if current else 1,
        )
        self.data[(collection, id)] = doc
        return doc

    async def find(self, collection, **kwargs):
        from types import SimpleNamespace

        return SimpleNamespace(items=[])

    async def count(self, collection, where=None):
        return 0

    async def delete(self, collection, id):
        self.data.pop((collection, id), None)


def test_a_module_runs_its_jobs_behind_the_callout_and_no_other_modules(stack):
    from naas_abi_sdk.broker_control import BrokerControl as BrokerControl_
    from naas_abi_sdk.job_host import JobHost
    from naas_abi_sdk.jobs import Every, JobDescriptor, job_subjects
    from naas_abi_sdk.module import ModuleDependencies
    from naas_abi_sdk.permissions import default_manifest

    iam = stack["iam"]
    people, people_key = module(iam, "module/default/people")
    approve(
        iam,
        people,
        "module/default/people",
        default_manifest(ModuleDependencies(), jobs=["nightly"]),
    )
    billing, billing_key = module(iam, "module/default/billing")
    approve(
        iam,
        billing,
        "module/default/billing",
        default_manifest(ModuleDependencies(), jobs=["invoice"]),
    )
    nightly = JobDescriptor("nightly", triggers=(Every("1h"),))
    ran: list[dict] = []

    async def scenario(served):
        done = asyncio.Event()

        async def handler(ctx):
            ran.append(ctx.payload)
            if len(ran) == 2:
                done.set()
            return {"ok": True}

        transport = Transport(stack["url"], people_key, timeout=5)
        other = Transport(stack["url"], billing_key, timeout=2)
        host = JobHost(
            transport,
            Runs(),
            "people",
            "default",
            {"nightly": (nightly, handler)},
            fetch_timeout_seconds=0.2,
            control=BrokerControl_(transport),
        )
        try:
            # Its stream (the engine made it), its consumer, its schedule.
            await host.start()
            await host.trigger("nightly", {"n": 1})
            # Above the broker limit: a claim check under its own jobs.
            await host.trigger("nightly", {"blob": "x" * (2 * MAX_PAYLOAD)})
            await asyncio.wait_for(done.wait(), 15)
            assert ran[0] == {"n": 1} and len(ran[1]["blob"]) == 2 * MAX_PAYLOAD
            # Another module triggers, schedules or cancels none of its jobs,
            # and reads none of its consumers or triggers.
            subjects = job_subjects("default", "people", "nightly")
            for subject in (
                subjects.trigger,
                subjects.schedule(0),
                subjects.cancel,
                f"$JS.API.CONSUMER.MSG.NEXT.ABI_JOBS_default.{subjects.consumer}",
                (
                    f"$JS.API.CONSUMER.CREATE.ABI_JOBS_default.{subjects.consumer}"
                    f".{subjects.trigger}"
                ),
                "$JS.API.STREAM.MSG.GET.ABI_JOBS_default",
                "$JS.API.STREAM.PURGE.ABI_JOBS_default",
            ):
                assert await denied(other, subject), subject
            # Nor write its own schedule (aimed at people's trigger, say): the
            # engine writes every module's schedules, aimed at its own trigger.
            invoice = job_subjects("default", "billing", "invoice")
            assert await denied(other, invoice.schedule(0))
            assert await denied(other, invoice.trigger)
            await asyncio.sleep(1)
            assert len(ran) == 2
        finally:
            await host.close()
            await other.close()
            await transport.close()

    run(stack, scenario)


# -- review round 2: nothing published on a module's behalf ------------------------------

FORBIDDEN = "abi.mod.default.OTHER"


def test_a_module_mints_no_reply_permission_by_writing_to_itself(stack):
    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    approve(iam, account, "module/default/people", BUS)

    async def scenario(served):
        engine = await nats.connect(stack["engine"])
        heard: list[str] = []

        async def overheard(msg):
            heard.append(msg.subject)

        await engine.subscribe(f"{FORBIDDEN}.>", cb=overheard)
        await engine.flush()
        transport = Transport(stack["url"], key, timeout=2)
        try:
            nc = await transport.connect()
            errors: list[str] = []
            nc._error_cb = _collect(errors)
            received: list[str] = []

            async def own(msg):
                received.append(msg.reply)

            inbox = f"_INBOX.{key.split('_')[2]}.loop"
            await nc.subscribe(inbox, cb=own)
            await nc.subscribe(f"{TOPIC}.loop", cb=own)
            # Messages it sends itself, through its inbox and through its topic,
            # with a reply subject it may not publish on.
            await nc.publish(inbox, b"x", reply=f"{FORBIDDEN}.a")
            await nc.publish(f"{TOPIC}.loop", b"x", reply=f"{FORBIDDEN}.b")
            await nc.flush()
            await asyncio.sleep(0.5)
            assert received == [f"{FORBIDDEN}.a", f"{FORBIDDEN}.b"]
            for reply in received:  # answering them grants nothing
                await nc.publish(reply, b"via-reply")
            await nc.flush()
            await asyncio.sleep(0.5)
            assert heard == []
            assert sum("ermissions" in e for e in errors) >= 2
        finally:
            await transport.close()
            await engine.close()

    run(stack, scenario)


def test_the_engine_answers_no_reply_subject_but_an_inbox(stack):
    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    approve(iam, account, "module/default/people", BUS)
    stream = broker.bus_stream(TOPIC)

    async def scenario(served):
        engine = await nats.connect(stack["engine"])
        heard: list[str] = []

        async def overheard(msg):
            heard.append(msg.subject)

        await engine.subscribe(f"{FORBIDDEN}.>", cb=overheard)
        await engine.flush()
        transport = Transport(stack["url"], key, timeout=2)
        try:
            await BusClient(transport).enqueue(TOPIC, "a", b"kept")
            token = await transport.access_token()
            nc = await transport.connect()
            # An empty answer on the purge API would empty the stream: the
            # engine's IAM service drops such a request instead of running it.
            request = pb.FindServiceAccountRequest(name="api").SerializeToString()
            for reply in (f"$JS.API.STREAM.PURGE.{stream}", f"{FORBIDDEN}.c"):
                await nc.publish(
                    "abi.iam.v1.find_service_account",
                    request,
                    reply=reply,
                    headers={"Nats-Auth-Token": token},
                )
            await nc.flush()
            await asyncio.sleep(0.5)
            info = await engine.jetstream().stream_info(stream)
            assert info.state.messages == 1
            assert heard == []
            # Its own inbox is answered as ever.
            reply = await nc.request(
                "abi.iam.v1.find_service_account",
                request,
                headers={"Nats-Auth-Token": token},
                timeout=2,
            )
            assert reply.data is not None
        finally:
            await transport.close()
            await engine.close()

    run(stack, scenario)


def test_a_module_creates_no_consumer_or_stream_info_and_rolls_up_nothing(stack):
    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    approve(iam, account, "module/default/people", BUS)
    stream = broker.bus_stream(TOPIC)

    async def scenario(served):
        transport = Transport(stack["url"], key, timeout=2)
        try:
            await BusClient(transport).enqueue(TOPIC, "a", b"kept")
            nc = await transport.connect()
            push = {
                "stream_name": stream,
                "config": {
                    "name": "evil",
                    "durable_name": "evil",
                    "deliver_subject": KV_GET,
                    "filter_subject": f"{TOPIC}.x",
                    "ack_policy": "none",
                },
            }
            for subject in (
                f"$JS.API.CONSUMER.CREATE.{stream}.evil.{TOPIC}.x",
                f"$JS.API.CONSUMER.DURABLE.CREATE.{stream}.evil",
                f"$JS.API.CONSUMER.INFO.{stream}.evil",
                f"$JS.API.STREAM.INFO.{stream}",
                "$JS.API.STREAM.INFO.ABI_CLAIM_CHECKS",
            ):
                errors: list[str] = []
                nc._error_cb = _collect(errors)
                with contextlib.suppress(Exception):
                    await nc.request(subject, json.dumps(push).encode(), timeout=1)
                await asyncio.sleep(0.1)
                assert any("ermissions" in e for e in errors), subject
            await nc.publish(f"{TOPIC}.x", b"would be delivered to the KV service")
            await nc.flush()
            await asyncio.sleep(0.5)
            assert KV_GET not in served
        finally:
            await transport.close()

    run(stack, scenario)


def test_a_module_writes_nothing_into_the_jobs_stream(stack):
    # Schedules make the server allow rollups on the jobs stream: one
    # Nats-Rollup: all from a module would purge every module's jobs.
    from naas_abi_sdk.broker_control import BrokerControl as Control
    from naas_abi_sdk.jobs import job_subjects
    from naas_abi_sdk.module import ModuleDependencies
    from naas_abi_sdk.permissions import default_manifest

    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    approve(
        iam,
        account,
        "module/default/people",
        default_manifest(ModuleDependencies(), jobs=["nightly"]),
    )

    async def scenario(served):
        transport = Transport(stack["url"], key, timeout=2)
        try:
            control = Control(transport)
            subjects = job_subjects("default", "people", "nightly")
            trigger = {"project": "default", "module_id": "people", "job": "nightly"}
            first = await control.request("trigger", body="", headers={}, **trigger)
            # The engine stores it; a rollup header from the module is dropped.
            second = await control.request(
                "trigger",
                body="",
                headers={"Nats-Rollup": "all", "Nats-Msg-Id": "x"},
                **trigger,
            )
            assert second["seq"] == first["seq"] + 1
            for subject in (subjects.trigger, subjects.schedule(0), subjects.cancel):
                assert await denied(transport, subject), subject
            engine = await nats.connect(stack["engine"])
            info = await engine.jetstream().stream_info("ABI_JOBS_default")
            await engine.close()
            assert info.state.messages == 2
        finally:
            await transport.close()

    run(stack, scenario)


def test_the_engine_creates_only_what_a_module_is_granted(stack):
    from naas_abi_sdk.broker_control import BrokerControl as Control
    from naas_abi_sdk.broker_control import BrokerControlError
    from naas_abi_sdk.module import ModuleDependencies
    from naas_abi_sdk.permissions import default_manifest

    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    approve(iam, account, "module/default/people", BUS)
    billing, _ = module(iam, "module/default/billing")
    approve(
        iam,
        billing,
        "module/default/billing",
        default_manifest(ModuleDependencies(), jobs=["invoice"]),
    )

    async def scenario(served):
        transport = Transport(stack["url"], key, timeout=2)
        try:
            control = Control(transport)
            assert await control.request("ensure_queue", topic=TOPIC, routing_key="a")
            for operation, fields in (
                ("ensure_topic", {"topic": "other.topic"}),
                ("ensure_queue", {"topic": "abi.iam", "routing_key": "a"}),
                (
                    "ensure_job",
                    {
                        "project": "default",
                        "job": "invoice",  # billing's
                        "max_concurrency": 1,
                        "ack_wait_seconds": 30,
                    },
                ),
                (
                    "set_schedules",
                    {"project": "default", "job": "invoice", "schedules": []},
                ),
                (
                    "trigger",
                    {
                        "project": "default",
                        "module_id": "billing",
                        "job": "invoice",
                        "body": "",
                    },
                ),
                (
                    "cancel",
                    {
                        "project": "default",
                        "module_id": "billing",
                        "job": "invoice",
                        "run_id": "invoice:1",
                    },
                ),
            ):
                with pytest.raises(BrokerControlError):
                    await control.request(operation, **fields)
        finally:
            await transport.close()

    run(stack, scenario)


# -- review round 3: no message of a module's choosing lands where it is not granted -----


def _jobs_manifest(*names):
    from naas_abi_sdk.module import ModuleDependencies
    from naas_abi_sdk.permissions import default_manifest

    return default_manifest(ModuleDependencies(), jobs=list(names))


def test_a_forged_trigger_never_runs_another_modules_job(stack):
    """The reviewer's probe: a module stores a message with a forged
    ``Abi-Job-Trigger: event`` header under its own claim-check subject and asks
    JetStream for it with the reply subject set to another module's trigger.
    Direct gets are refused, a pub ack landing there is not the engine's: the
    victim's job runs for the engine's own trigger only."""
    from naas_abi_sdk.broker_control import BrokerControl as Control
    from naas_abi_sdk.job_host import JobHost
    from naas_abi_sdk.jobs import TRIGGER_HEADER, JobDescriptor, job_subjects

    iam = stack["iam"]
    victim, victim_key = module(iam, "module/default/victim")
    approve(iam, victim, "module/default/victim", _jobs_manifest("nightly"))
    attacker, attacker_key = module(iam, "module/default/people")
    approve(iam, attacker, "module/default/people", BUS)
    target = job_subjects("default", "victim", "nightly").trigger
    own_cc = broker.topic_claim_subjects(TOPIC)[:-2] + ".forged.0"
    ran: list[dict] = []

    async def scenario(served):
        async def handler(ctx):
            ran.append(ctx.payload)

        transport = Transport(stack["url"], victim_key, timeout=5)
        attack = Transport(stack["url"], attacker_key, timeout=2)
        host = JobHost(
            transport,
            Runs(),
            "victim",
            "default",
            {"nightly": (JobDescriptor("nightly"), handler)},
            fetch_timeout_seconds=0.2,
            control=Control(transport),
        )
        try:
            await host.start()
            await BusClient(attack).enqueue(TOPIC, "q", os.urandom(2 * MAX_PAYLOAD))
            nc = await attack.connect()
            forged = {TRIGGER_HEADER: "event"}
            await nc.publish(own_cc, b'{"forged": true}', headers=forged)
            await nc.flush()
            # Read back by direct get, answered onto the victim's trigger: refused.
            assert await denied(attack, f"$JS.API.DIRECT.GET.ABI_CLAIM_CHECKS.{own_cc}")
            await nc.publish(
                f"$JS.API.DIRECT.GET.ABI_CLAIM_CHECKS.{own_cc}", b"", reply=target
            )
            # A pub ack answered onto it (stored there, headerless): not sealed.
            await nc.publish(own_cc, b"{}", reply=target)
            await nc.flush()
            await asyncio.sleep(2)
            assert ran == []
            # The engine's own trigger runs.
            await host.trigger("nightly", {"real": True})
            for _ in range(50):
                if ran:
                    break
                await asyncio.sleep(0.1)
            assert ran == [{"real": True}]
        finally:
            await host.close()
            await attack.close()
            await transport.close()

    run(stack, scenario)


def test_the_engine_decides_each_request_on_its_resource(stack):
    from naas_abi_sdk.broker_control import BrokerControl as Control
    from naas_abi_sdk.broker_control import BrokerControlError

    iam = stack["iam"]
    billing, _ = module(iam, "module/default/billing")
    approve(iam, billing, "module/default/billing", _jobs_manifest("nightly", "secret"))
    account, key = module(iam, "module/default/people")
    approve(
        iam,
        account,
        "module/default/people",
        {
            "version": "2026-10-13",
            "statements": [
                {
                    "effect": "Allow",
                    "actions": ["discovery:TriggerJob"],
                    "resources": ["abi:-:-:discovery:job/default/billing/*"],
                },
                {
                    "effect": "Deny",
                    "actions": ["discovery:TriggerJob"],
                    "resources": ["abi:-:-:discovery:job/default/billing/secret"],
                },
            ],
        },
    )

    async def scenario(served):
        transport = Transport(stack["url"], key, timeout=2)
        try:
            control = Control(transport)
            names = {"project": "default", "module_id": "billing", "body": ""}
            assert await control.request("trigger", job="nightly", **names)
            with pytest.raises(BrokerControlError, match="not allowed"):
                await control.request("trigger", job="secret", **names)
        finally:
            await transport.close()

    run(stack, scenario)


def test_no_module_makes_another_ones_trigger_a_duplicate(stack):
    from naas_abi_sdk.broker_control import BrokerControl as Control

    iam = stack["iam"]
    billing, billing_key = module(iam, "module/default/billing")
    approve(iam, billing, "module/default/billing", _jobs_manifest("nightly"))
    account, key = module(iam, "module/default/people")
    approve(
        iam,
        account,
        "module/default/people",
        {
            "version": "2026-10-13",
            "statements": [
                {
                    "effect": "Allow",
                    "actions": ["discovery:TriggerJob"],
                    "resources": ["abi:-:-:discovery:job/default/billing/*"],
                }
            ],
        },
    )

    async def scenario(served):
        people = Transport(stack["url"], key, timeout=2)
        owner = Transport(stack["url"], billing_key, timeout=2)
        try:
            trigger = {
                "project": "default",
                "module_id": "billing",
                "job": "nightly",
                "body": "",
                "headers": {"Nats-Msg-Id": "known-key"},
            }
            first = await Control(people).request("trigger", **trigger)
            again = await Control(people).request("trigger", **trigger)
            assert again["duplicate"] and again["seq"] == first["seq"]
            # billing's own trigger with the same id is billing's, stored.
            own = await Control(owner).request("trigger", **trigger)
            assert not own["duplicate"] and own["seq"] != first["seq"]
        finally:
            await people.close()
            await owner.close()

    run(stack, scenario)


def test_broker_control_does_nothing_for_a_reply_subject_but_an_inbox(stack):
    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    approve(iam, account, "module/default/people", _jobs_manifest("nightly"))

    async def scenario(served):
        transport = Transport(stack["url"], key, timeout=2)
        try:
            token = await transport.access_token()
            nc = await transport.connect()
            request = {
                "project": "default",
                "module_id": "people",
                "job": "nightly",
                "body": "",
            }
            for reply in (f"{FORBIDDEN}.x", None):
                await nc.publish(
                    "abi.broker.v1.trigger",
                    json.dumps(request).encode(),
                    reply=reply or "",
                    headers={"Nats-Auth-Token": token},
                )
            await nc.flush()
            await asyncio.sleep(0.5)
            engine = await nats.connect(stack["engine"])
            try:
                with contextlib.suppress(Exception):  # no stream: nothing stored
                    info = await engine.jetstream().stream_info("ABI_JOBS_default")
                    assert info.state.messages == 0
            finally:
                await engine.close()
        finally:
            await transport.close()

    run(stack, scenario)


def test_the_first_enqueue_creates_the_queue_even_with_a_subscriber(stack):
    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    approve(iam, account, "module/default/people", BUS)

    async def scenario(served):
        transport = Transport(stack["url"], key, timeout=2)
        try:
            bus = BusClient(transport)
            live = await bus.subscribe(TOPIC, "a")  # answers nothing, as ever
            await bus.enqueue(TOPIC, "a", b"queued")
            assert (await live.next_msg(timeout=2)).data == b"queued"
            queue = await bus.dequeue(TOPIC, "a")
            assert [m.data for m in await queue.fetch(1, timeout=5)] == [b"queued"]
        finally:
            await transport.close()

    run(stack, scenario)


def test_a_module_reads_the_claim_checks_of_what_it_is_granted_only(stack):
    from naas_abi_sdk.broker_control import BrokerControl as Control
    from naas_abi_sdk.broker_control import BrokerControlError

    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    approve(iam, account, "module/default/people", BUS)

    async def scenario(served):
        transport = Transport(stack["url"], key, timeout=2)
        try:
            control = Control(transport)
            other = broker.topic_claim_subjects("other.topic")[:-2] + ".x"
            with pytest.raises(BrokerControlError, match="not one the caller reads"):
                await control.read("read_claim_check", reference=other, index=0)
            mine = broker.topic_claim_subjects(TOPIC)[:-2] + ".missing"
            with pytest.raises(BrokerControlError, match="expired"):
                await control.read("read_claim_check", reference=mine, index=0)
        finally:
            await transport.close()

    run(stack, scenario)


def test_a_connection_renews_itself_before_its_permissions_expire(stack):
    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    approve(iam, account, "module/default/people")

    async def scenario(served):
        # The broker gives a connection 3 s; the transport reconnects every 1 s,
        # and the callout answers each time. Without it nats-py would close the
        # connection at expiry and never reconnect it.
        transport = Transport(
            stack["url"], key, timeout=2, renew_seconds=1, reconnect_time_wait=0.1
        )
        try:
            nc = await transport.connect()
            for _ in range(20):  # seven seconds: two lives of the broker's JWT
                await asyncio.sleep(0.37)
                for attempt in range(3):
                    try:
                        # A call that starts during a renewal waits for it; one
                        # in flight when it begins is lost, as in any reconnect.
                        nc = await transport.connect()
                        await nc.request(KV_GET, b"", timeout=1)
                        break
                    except Exception:
                        if attempt == 2:
                            raise
            assert not nc.is_closed
        finally:
            await transport.close()

    run(stack, scenario, user_ttl_seconds=3)


def test_a_revoked_key_loses_its_connection_within_the_ttl(stack):
    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    approve(iam, account, "module/default/people")

    async def scenario(served):
        transport = Transport(
            stack["url"], key, timeout=2, renew_seconds=1, reconnect_time_wait=0.1
        )
        try:
            nc = await transport.connect()
            await nc.request(KV_GET, b"", timeout=2)
            with as_service_account("engine"):
                iam.revoke_key(account, key.split("_")[2])
            await asyncio.sleep(5)  # the renewal is refused; no expiry gets past
            with pytest.raises(Exception):
                await nc.request(KV_GET, b"", timeout=1)
        finally:
            await transport.close()

    run(stack, scenario, user_ttl_seconds=3)


def test_a_narrowed_manifest_reaches_the_broker_at_the_next_renewal(stack):
    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    approve(iam, account, "module/default/people")

    async def scenario(served):
        transport = Transport(
            stack["url"], key, timeout=2, renew_seconds=1, reconnect_time_wait=0.1
        )
        try:
            nc = await transport.connect()
            await nc.request(KV_GET, b"", timeout=2)
            approve(
                iam,
                account,
                "module/default/people",
                {
                    "version": "2026-10-13",
                    "statements": [
                        {
                            "effect": "Allow",
                            "actions": ["document:*"],
                            "resources": ["abi:-:-:document:namespace/people"],
                        }
                    ],
                },
            )
            for _ in range(10):  # the next renewal, within a second or two
                await asyncio.sleep(1)
                if await denied(transport, KV_GET):
                    break
            else:
                raise AssertionError("the narrowed manifest never reached the broker")
        finally:
            await transport.close()

    run(stack, scenario, user_ttl_seconds=30)


def test_a_module_with_secret_grants_reads_no_signing_key(stack):
    from naas_abi_core.services.secret.adaptors.primary.secret__primary_adapter__NATS import (
        SecretPrimaryAdapterNATS,
    )
    from naas_abi_core.services.secret.SecretPorts import ISecretAdapter
    from naas_abi_proto.secret.v1 import secret_pb2

    class Secrets(ISecretAdapter):
        def __init__(self):
            self.values = {
                "iam/signing-keys/20261018-abcd1234": "PEM",
                "iam/job-trigger-seal": "seal",
                "idp/signing-key": "idp",
                "people/api-key": "mine",
            }

        def get(self, key, default=None):
            return self.values.get(key, default)

        def set(self, key, value):
            self.values[key] = value

        def remove(self, key):
            self.values.pop(key, None)

        def list(self):
            return dict(self.values)

    iam = stack["iam"]
    account, key = module(iam, "module/default/people")
    # What the default manifest used to grant: every secret.
    approve(
        iam,
        account,
        "module/default/people",
        {
            "version": "2026-10-13",
            "statements": [
                {
                    "effect": "Allow",
                    "actions": ["secret:*"],
                    "resources": ["abi:*:*:secret:*"],
                }
            ],
        },
    )
    secrets = Secrets()

    async def scenario(served):
        engine = await nats.connect(stack["engine"])
        primary = SecretPrimaryAdapterNATS(secrets, iam.verifier())
        await primary.start(engine)
        transport = Transport(stack["url"], key, timeout=3)
        try:
            for name in ("iam/signing-keys/20261018-abcd1234", "iam/job-trigger-seal"):
                with pytest.raises(RPCError) as refused:
                    await transport.call(
                        "abi.svc.secret.v1.get",
                        secret_pb2.GetRequest(key=name),
                        secret_pb2.GetResponse,
                    )
                assert refused.value.code == "PERMISSION_DENIED"
                with pytest.raises(RPCError):
                    await transport.call(
                        "abi.svc.secret.v1.set",
                        secret_pb2.SetRequest(key=name, value="mine"),
                        secret_pb2.SetResponse,
                    )
            assert secrets.values["iam/job-trigger-seal"] == "seal"
            listed = await transport.call(
                "abi.svc.secret.v1.list",
                secret_pb2.ListRequest(),
                secret_pb2.ListResponse,
            )
            assert {e.key for e in listed.found.entries} == {"people/api-key"}
            got = await transport.call(
                "abi.svc.secret.v1.get",
                secret_pb2.GetRequest(key="people/api-key"),
                secret_pb2.GetResponse,
            )
            assert got.found.value == "mine"
        finally:
            await transport.close()
            await primary.stop()
            await engine.close()

    run(stack, scenario)


def _bus_for(action: str) -> dict:
    return {
        "version": "2026-10-13",
        "statements": [
            {
                "effect": "Allow",
                "actions": [action],
                "resources": [f"abi:-:-:bus:topic/{TOPIC}"],
            }
        ],
    }


def test_bus_grants_follow_the_action_publish_is_not_consume(stack):
    from naas_abi_sdk.broker_control import BrokerControlError

    iam = stack["iam"]
    producer, producer_key = module(iam, "module/default/producer")
    consumer, consumer_key = module(iam, "module/default/consumer")
    approve(iam, producer, "module/default/producer", _bus_for("bus:Publish"))
    approve(iam, consumer, "module/default/consumer", _bus_for("bus:Consume"))
    stream = broker.bus_stream(TOPIC)
    durable = BusClient.consumer_name(TOPIC, "a")

    async def scenario(served):
        sending = Transport(stack["url"], producer_key, timeout=2)
        receiving = Transport(stack["url"], consumer_key, timeout=2)
        try:
            await BusClient(sending).enqueue(TOPIC, "a", b"work")
            # Publish-only: it may neither create the queue nor pull or
            # acknowledge anyone's work, wherever it aims the request.
            with pytest.raises(BrokerControlError):
                await BusClient(sending).dequeue(TOPIC, "a")
            for subject in (
                f"$JS.API.CONSUMER.MSG.NEXT.{stream}.{durable}",
                f"$JS.ACK.{stream}.{durable}.1.1.1.1.1",
            ):
                assert await denied(sending, subject), subject
            assert await denied(receiving, f"{TOPIC}.a")  # consume-only: no publish
            queue = await BusClient(receiving).dequeue(TOPIC, "a")
            assert [m.data for m in await queue.fetch(1, timeout=5)] == [b"work"]
        finally:
            await sending.close()
            await receiving.close()

    run(stack, scenario)
