"""Durable workflows: descriptors, the decorator, the step journal, child runs, triggers.

No broker here (tests/test_workflows_integration.py has the real one); no pydantic
either: models are duck-typed, as the SDK does (``test_pydantic_models`` runs
with real pydantic when it is installed).
"""

import asyncio
import json
import subprocess
import sys
import threading
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import ClassVar

import pytest
from naas_abi_proto.discovery.v1 import discovery_pb2 as pb

from naas_abi_sdk import workflows
from naas_abi_sdk.job_host import JobHost
from naas_abi_sdk.jobs import (
    INPUT_HASH_HEADER,
    MAX_SCHEMA_BYTES,
    MAX_TRIGGER_INPUT_BYTES,
    Cron,
    Every,
    JobDescriptor,
    JobsMixin,
    JobsNotHosted,
    JobsSealed,
    NonRetryable,
    job,
    job_subjects,
    runs_collection,
)
from naas_abi_sdk.module import BaseModule, ModuleDependencies, module_descriptor
from naas_abi_sdk.services.errors import DocumentNotFound, VersionConflict
from naas_abi_sdk.services.models import Document, Page
from naas_abi_sdk.workflows import (
    ChildRunFailed,
    FlowContext,
    FlowRuntime,
    InvalidWorkflowInput,
    InvalidWorkflowOutput,
    SelfCall,
    StepKeyError,
    StepResultNotJSON,
    StepResultTooLarge,
    WorkflowCancelled,
    WorkflowProxy,
    WorkflowRun,
    WorkflowRunFailed,
    results_collection,
    steps_collection,
    workflow,
)

PROJECT, MODULE = "zen", "acme.flows"


class MemoryDocuments:
    """A document store with CAS, as much of ``find`` as the runtime uses."""

    def __init__(self):
        self.data: dict[tuple[str, str], Document] = {}

    async def ensure_collection(self, spec):
        return None

    async def get(self, collection, id):
        try:
            return self.data[(collection, id)]
        except KeyError:
            raise DocumentNotFound("NOT_FOUND", id) from None

    async def put(self, collection, id, data, *, if_version=None):
        current = self.data.get((collection, id))
        if if_version == 0 and current is not None:
            raise VersionConflict("VERSION_CONFLICT", id)
        if if_version and (current is None or current.version != if_version):
            raise VersionConflict("VERSION_CONFLICT", id)
        now = datetime.now(timezone.utc)
        doc = Document(
            id=id,
            data=json.loads(json.dumps(data)),
            created_at=current.created_at if current else now,
            updated_at=now,
            version=(current.version + 1) if current else 1,
        )
        self.data[(collection, id)] = doc
        return doc

    async def delete(self, collection, id, *, if_version=None):
        if (collection, id) not in self.data:
            raise DocumentNotFound("NOT_FOUND", id)
        del self.data[(collection, id)]

    async def find(
        self, collection, *, where=(), order_by=None, limit=100, cursor=None, **_
    ):
        def matches(data):
            for field, op, value in where:
                have = data.get(field)
                if op == "eq" and have != value:
                    return False
                if op == "in" and have not in value:
                    return False
                if op == "lt" and not (have is not None and have < value):
                    return False
            return True

        items = [d for (c, _), d in self.data.items() if c == collection]
        items = [d for d in items if matches(d.data)]
        if order_by:
            items.sort(key=lambda d: d.data.get(order_by[0], ""))
        return Page(items[:limit], None)

    async def count(self, collection, where=()):
        return len((await self.find(collection, where=where, limit=10**6)).items)

    def steps(self, run_id):
        prefix = f"{run_id}#"
        return {
            id[len(prefix) :]: d.data
            for (c, id), d in self.data.items()
            if c.startswith("workflow_steps_") and id.startswith(prefix)
        }

    def results(self, run_id):
        prefix = f"{run_id}#"
        return {
            id[len(prefix) :]: json.loads(d.data["result_json"])
            for (c, id), d in self.data.items()
            if c.startswith("workflow_results_") and id.startswith(prefix)
        }


# --- duck-typed models (what pydantic v2 offers, without pydantic) ---------------------


def model(name, fields, required=()):
    """A class with pydantic v2's ``model_json_schema``/``model_validate``/``model_dump``."""

    def validate(cls, data):
        if not isinstance(data, dict):
            raise TypeError(f"{name}: input must be an object")
        missing = [f for f in required if f not in data]
        if missing:
            raise ValueError(f"{name}: {missing[0]} field required")
        return cls(**{k: v for k, v in data.items() if k in fields})

    def init(self, **kwargs):
        self.__dict__.update(kwargs)

    return type(
        name,
        (),
        {
            "__init__": init,
            "model_json_schema": classmethod(
                lambda cls: {
                    "title": name,
                    "type": "object",
                    "properties": {f: {"type": t} for f, t in fields.items()},
                    "required": list(required),
                }
            ),
            "model_validate": classmethod(validate),
            "model_dump": lambda self, mode="python": dict(self.__dict__),
        },
    )


TweetsInput = model("TweetsInput", {"filter": "string"}, required=("filter",))
TweetsOutput = model("TweetsOutput", {"count": "integer"}, required=("count",))


# --- the decorator ---------------------------------------------------------------------


class Flows(BaseModule):
    module_id = MODULE
    dependencies = ModuleDependencies(services=("document",))

    @workflow(
        triggers=(Cron("0 0 * * * *", input={"filter": "db"}),),
        max_attempts=3,
        timeout=timedelta(minutes=5),
    )
    async def tweets(self, ctx: FlowContext, inp: TweetsInput) -> TweetsOutput:
        """Searches tweets."""
        n = await ctx.step("count", lambda: len(inp.filter))
        return TweetsOutput(count=n)

    @workflow(
        "raw",
        input_schema={"type": "object", "required": ["path"]},
        output_schema={"type": "object"},
    )
    async def raw_flow(self, ctx: FlowContext, inp: dict) -> dict:
        return {"path": inp["path"]}


def _bound(cls=Flows):
    module = object.__new__(cls)
    module._agent_handlers = {}
    return module


def test_workflow_declares_a_job_of_kind_workflow_with_schemas_from_annotations():
    by_name = {j.name: j for j in Flows.jobs}

    tweets = by_name["tweets"]
    assert tweets.kind == "workflow" and tweets.is_workflow
    assert tweets.description == "Searches tweets."
    assert tweets.max_attempts == 3 and tweets.timeout == timedelta(minutes=5)
    assert json.loads(tweets.input_schema)["required"] == ["filter"]
    assert json.loads(tweets.output_schema)["title"] == "TweetsOutput"
    assert tweets.triggers[0].input == {"filter": "db"}
    assert by_name["raw"].input_schema == json.dumps(
        {"required": ["path"], "type": "object"}, separators=(",", ":")
    )


def test_dict_workflows_default_to_an_object_input_and_take_explicit_schemas():
    class Plain(JobsMixin):
        @workflow()
        async def anything(self, ctx, inp: dict):
            return None

        @workflow(output_schema={"type": "array"})
        async def listing(self, ctx, inp) -> list:
            return []

        @workflow()
        async def nothing(self, ctx, inp) -> None:
            return None

    jobs = {j.name: j for j in Plain.jobs}

    assert json.loads(jobs["anything"].input_schema) == {"type": "object"}
    assert jobs["anything"].output_schema == ""  # unannotated: unspecified
    assert json.loads(jobs["listing"].output_schema) == {"type": "array"}
    assert json.loads(jobs["nothing"].output_schema) == {"type": "null"}


def test_unsupported_annotations_and_shapes_are_refused_when_declared():
    with pytest.raises(TypeError, match="pydantic model or a dict"):

        @workflow()
        async def numbers(self, ctx, inp: int):
            return None

    with pytest.raises(TypeError, match="must be async"):

        @workflow()
        def sync(self, ctx, inp: dict):
            return None

    with pytest.raises(TypeError, match=r"\(self, ctx, inp\)"):

        @workflow()
        async def two_params(self, ctx):
            return None

    with pytest.raises(TypeError, match="must be async"):

        class Sync(JobsMixin):
            @job()
            def nope(self, ctx):
                return None


def test_the_decorator_names_what_it_cannot_resolve():
    def local():
        class Hidden:
            pass

        async def handler(self, ctx, inp: "Hidden"):
            return None

        return handler

    with pytest.raises(TypeError, match="Cannot resolve the annotations"):
        workflow()(local())


def test_descriptor_round_trips_kind_schemas_and_trigger_inputs():
    descriptor = Flows.jobs[0]

    again = JobDescriptor.from_pb(descriptor.to_pb())

    assert again == descriptor
    assert again.kind == "workflow"
    assert again.triggers[0].input == {"filter": "db"}
    assert descriptor.to_pb().triggers[0].input == '{"filter":"db"}'


def test_descriptors_written_before_the_new_fields_decode_as_jobs():
    old = pb.JobDescriptor(
        name="legacy",
        contract_major=1,
        max_concurrency=1,
        max_attempts=1,
        triggers=[pb.JobTrigger(kind="every", spec="1h")],
    )
    # What an older module put on the wire: no kind, schemas or trigger input.
    decoded = JobDescriptor.from_pb(
        pb.JobDescriptor.FromString(old.SerializeToString())
    )

    assert decoded.kind == "job" and not decoded.is_workflow
    assert decoded.input_schema == decoded.output_schema == ""
    assert decoded.triggers[0].input is None


def test_descriptor_and_trigger_inputs_are_bounded():
    big = {"type": "object", "description": "x" * MAX_SCHEMA_BYTES}
    with pytest.raises(ValueError, match="input schema"):
        JobDescriptor("w", kind="workflow", input_schema=json.dumps(big))
    with pytest.raises(ValueError, match="JSON Schema object"):
        JobDescriptor("w", kind="workflow", input_schema="[1]")
    with pytest.raises(ValueError, match="kind"):
        JobDescriptor("w", kind="pipeline")
    with pytest.raises(ValueError, match="at most"):
        Cron("@daily", input={"x": "y" * MAX_TRIGGER_INPUT_BYTES})
    with pytest.raises(ValueError, match="JSON"):
        Every("1h", input={"x": object()})

    # The whole descriptor is capped too: 16 maximal inputs and two maximal schemas are not.
    def describe(input_size, schema_size):
        return JobDescriptor(
            "w",
            kind="workflow",
            triggers=tuple(
                Every("1h", input={"i": i, "x": "y" * input_size}) for i in range(16)
            ),
            input_schema=json.dumps({"description": "s" * schema_size}),
            output_schema=json.dumps({"description": "s" * schema_size}),
        )

    assert describe(1500, 10_000).to_pb().ByteSize() < 64 * 1024
    with pytest.raises(ValueError, match="describes itself in .* bytes; at most 65536"):
        describe(3000, 10_000)


def test_module_descriptor_lists_workflows_with_their_schemas():
    descriptor = module_descriptor(Flows, MODULE, ())

    tweets = next(j for j in descriptor.jobs if j.name == "tweets")
    assert tweets.kind == "workflow" and tweets.input_schema and tweets.output_schema


def test_jobs_and_workflows_import_without_nats_or_pydantic():
    code = (
        "import sys\n"
        "sys.modules['nats'] = None\n"  # `import nats` raises ImportError
        "sys.modules['pydantic'] = None\n"
        "import naas_abi_sdk.jobs, naas_abi_sdk.workflows\n"
        "from naas_abi_sdk.workflows import workflow, FlowContext\n"
        "import naas_abi_sdk\n"
        "naas_abi_sdk.workflow\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr


# --- the handler: validated input, dumped output ---------------------------------------


def test_the_handler_validates_the_input_and_dumps_the_output():
    module = _bound()
    handler = module._job_handlers["tweets"]
    docs = MemoryDocuments()
    ctx = _context(docs, payload={"filter": "db"})

    assert asyncio.run(handler(ctx)) == {"count": 2}
    assert docs.results("flow:1") == {"count": 2}

    with pytest.raises(InvalidWorkflowInput, match="filter field required"):
        asyncio.run(handler(_context(docs, payload={})))
    assert issubclass(InvalidWorkflowInput, NonRetryable)


def test_a_wrong_output_type_is_refused():
    module = _bound()
    module.declare_workflow("bad", _returns({"count": "x"}), output_type=TweetsOutput)

    assert asyncio.run(module._job_handlers["bad"](_context(MemoryDocuments()))) == {
        "count": "x"
    }  # a dict that validates is dumped

    module.declare_workflow("worse", _returns([1]), output_type=TweetsOutput)
    with pytest.raises(InvalidWorkflowOutput, match="TweetsOutput was expected"):
        asyncio.run(module._job_handlers["worse"](_context(MemoryDocuments())))
    module.declare_workflow("empty", _returns({}), output_type=TweetsOutput)
    with pytest.raises(InvalidWorkflowOutput, match="Invalid output"):
        asyncio.run(module._job_handlers["empty"](_context(MemoryDocuments())))


def _returns(value):
    async def handler(ctx, inp):
        return value

    return handler


def test_an_invalid_input_fails_the_run_without_retry():
    docs, host = MemoryDocuments(), None
    module = _bound()
    descriptor = next(j for j in Flows.jobs if j.name == "tweets")
    host = _host(docs, [(descriptor, module._job_handlers["tweets"])])
    msg = _Msg(payload={"nope": 1})

    asyncio.run(host.handle(descriptor, module._job_handlers["tweets"], msg))

    record = docs.data[(runs_collection(PROJECT), "tweets:7")].data
    assert record["status"] == "FAILED"  # max_attempts is 3: still no retry
    assert "InvalidWorkflowInput" in record["error"]
    assert msg.calls[-1] == ("term",)
    assert docs.steps("tweets:7") == {}


def test_a_workflow_run_sees_a_flow_context_and_notifies_waiters():
    docs = MemoryDocuments()
    seen = {}

    async def handler(ctx):
        seen["ctx"] = ctx
        await ctx.step("one", lambda: 1)
        return {"ok": True}

    descriptor = JobDescriptor("w", kind="workflow")
    host = _host(docs, [(descriptor, handler)])
    msg = _Msg(sequence=3)

    asyncio.run(host.handle(descriptor, handler, msg))

    assert isinstance(seen["ctx"], FlowContext)
    run_id = "w:3"
    assert docs.data[(runs_collection(PROJECT), run_id)].data["status"] == "SUCCEEDED"
    assert docs.steps(run_id)["one"]["status"] == "SUCCEEDED"
    subject, body = host.transport.connection.published[-1]
    assert subject == job_subjects(PROJECT, MODULE, "w").done
    assert json.loads(body) == {"run_id": run_id, "status": "SUCCEEDED"}


def test_retention_deletes_a_pruned_runs_journal():
    docs = MemoryDocuments()

    async def handler(ctx):
        await ctx.step("one", lambda: 1)

    descriptor = JobDescriptor("w", kind="workflow")
    host = _host(docs, [(descriptor, handler)])
    asyncio.run(host.handle(descriptor, handler, _Msg(sequence=3)))
    assert docs.steps("w:3") and docs.results("w:3")

    later = datetime.now(timezone.utc) + timedelta(days=30)
    assert asyncio.run(host.prune(later)) == 1

    assert not docs.steps("w:3") and not docs.results("w:3")


# --- the runtime declaration -----------------------------------------------------------


def test_a_workflow_can_be_declared_at_runtime_before_the_host_starts():
    module = _bound()
    declared = module.declare_workflow(
        "pipeline.x",
        _returns({"count": 3}),
        input_type=TweetsInput,
        output_type=TweetsOutput,
        description="Bridged.",
        max_concurrency=2,
    )

    assert declared.kind == "workflow" and declared.max_concurrency == 2
    assert (
        module.jobs[-1] is declared and Flows.jobs[-1] is not declared
    )  # per instance
    assert json.loads(declared.input_schema)["title"] == "TweetsInput"
    assert asyncio.run(
        module._job_handlers["pipeline.x"](
            _context(MemoryDocuments(), payload={"filter": "q"})
        )
    ) == {"count": 3}
    assert module.workflow_spec("pipeline.x").output_type is TweetsOutput
    assert module.missing_job_handlers() == set()

    with pytest.raises(ValueError, match="Duplicate job names"):
        module.declare_workflow("pipeline.x", _returns({}))
    with pytest.raises(ValueError, match="Duplicate job names"):
        module.declare_job(JobDescriptor("tweets"), _returns(None))

    async def plain(ctx):
        return None

    module.declare_job(JobDescriptor("plain"), plain)
    assert module._job_handlers["plain"] is plain
    module._bind_job_host(SimpleNamespace(), None)  # the host started
    with pytest.raises(JobsSealed):
        module.declare_workflow("late", _returns({}))


def _fake_client(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr("naas_abi_sdk.module.ABIClient", lambda *a, **k: client)


def _session(monkeypatch, registered):
    class Session:
        def __init__(self, client, descriptor, rollout_id="", rollout_modules=()):
            self.descriptor = descriptor
            self.rollout_id, self.instance_id = rollout_id, "instance"
            self.initialized = self.draining = False
            self.status, self.task = "STARTING", None
            self.drain_requested = asyncio.Event()

        async def start(self):
            registered.append(self.descriptor)

        async def renew(self):
            if self.initialized and self.status == "STARTING":
                self.status = "READY"

        async def close(self):
            pass

    class Host:
        def __init__(self, *args, **kwargs):
            pass

        async def start(self):
            pass

        async def drain(self, timeout):
            pass

        async def close(self):
            pass

    monkeypatch.setattr("naas_abi_sdk.module.DiscoverySession", Session)
    monkeypatch.setattr("naas_abi_sdk.job_host.JobHost", Host)


def test_run_module_registers_the_jobs_declared_in_on_load(monkeypatch):
    from naas_abi_sdk.discovery import DiscoveryConfiguration
    from naas_abi_sdk.module import run_module

    registered: list = []
    _fake_client(monkeypatch)
    _session(monkeypatch, registered)

    class Bridge(BaseModule):
        module_id = "acme.bridge"
        dependencies = ModuleDependencies(services=("document",))

        def on_load(self):
            self.declare_workflow(
                "pipeline.x", _returns({}), input_schema={"type": "object"}
            )

        async def run(self):
            return "ran"

    result = asyncio.run(
        run_module(
            Bridge, url="nats://unused", token="t", discovery=DiscoveryConfiguration()
        )
    )

    assert result == "ran"
    assert [(j.name, j.kind) for j in registered[0].jobs] == [
        ("pipeline.x", "workflow")
    ]


def test_run_module_refuses_jobs_declared_after_registration(monkeypatch):
    from naas_abi_sdk.discovery import DiscoveryConfiguration
    from naas_abi_sdk.module import run_module

    _fake_client(monkeypatch)
    _session(monkeypatch, [])

    class Late(BaseModule):
        module_id = "acme.late"
        dependencies = ModuleDependencies(services=("document",))

        def on_initialized(self):
            self.declare_workflow("late", _returns({}))

        async def run(self):
            return None

    with pytest.raises(ValueError, match="declared after the module registered"):
        asyncio.run(
            run_module(
                Late,
                url="nats://unused",
                token="t",
                discovery=DiscoveryConfiguration(),
            )
        )


# --- trigger inputs --------------------------------------------------------------------


def test_trigger_inputs_are_the_schedule_body_and_part_of_its_identity():
    plain = Every("1h")
    with_input = Every("1h", input={"b": 2, "a": 1})
    reordered = Every("1h", input={"a": 1, "b": 2})
    changed = Every("1h", input={"a": 1, "b": 3})

    assert plain.body == b"{}" and INPUT_HASH_HEADER not in plain.headers()
    assert with_input.body == b'{"a":1,"b":2}'  # canonical: replicas agree
    assert with_input == reordered and hash(with_input) == hash(reordered)
    assert (
        with_input.headers()[INPUT_HASH_HEADER]
        == reordered.headers()[INPUT_HASH_HEADER]
    )
    assert (
        with_input.headers()[INPUT_HASH_HEADER] != changed.headers()[INPUT_HASH_HEADER]
    )
    # An empty input is no input: no header, so a schedule from before inputs
    # existed is still the same schedule (and its interval keeps running).
    assert Every("1h", input={}).headers() == plain.headers()
    cron = Cron("0 0 6 * * *", time_zone="UTC", input={"k": "v"})
    assert cron.headers()["Nats-Schedule-Time-Zone"] == "UTC"
    assert cron.headers()[INPUT_HASH_HEADER] and cron.body == b'{"k":"v"}'


class _Js:
    """The schedule messages of a jobs stream, as ``_ensure_schedule`` reads them."""

    def __init__(self):
        self.messages: dict[str, SimpleNamespace] = {}
        self.sequence = 0
        self.published: list[tuple[str, bytes]] = []

    async def get_last_msg(self, stream, subject):
        from nats.js.errors import NotFoundError

        if subject not in self.messages:
            raise NotFoundError
        return self.messages[subject]

    async def publish(self, subject, body, headers=None, stream=None):
        self.sequence += 1
        self.messages[subject] = SimpleNamespace(
            seq=self.sequence, headers=dict(headers), data=body
        )
        self.published.append((subject, body))

    async def purge_stream(self, stream, subject=None):
        self.messages.pop(subject, None)


def test_a_changed_trigger_input_republishes_only_that_schedule():
    js = _Js()
    jobs = [
        (
            JobDescriptor(
                "w",
                kind="workflow",
                triggers=(
                    Every("1h", input={"n": 1}),
                    Every("2h"),
                    Cron("@daily", input={"k": 1}),
                ),
            ),
            None,
        )
    ]
    host = _host(MemoryDocuments(), jobs)
    descriptor = jobs[0][0]
    asyncio.run(host.reconcile_schedules(js, descriptor))
    first = {s: m.seq for s, m in js.messages.items()}
    assert sorted(first.values()) == [1, 2, 3]
    assert [b for _, b in js.published] == [b'{"n":1}', b"{}", b'{"k":1}']

    asyncio.run(host.reconcile_schedules(js, descriptor))  # a restart: nothing changes
    assert {s: m.seq for s, m in js.messages.items()} == first

    changed = JobDescriptor(
        "w",
        kind="workflow",
        triggers=(
            Every("1h", input={"n": 2}),
            Every("2h"),
            Cron("@daily", input={"k": 1}),
        ),
    )
    asyncio.run(host.reconcile_schedules(js, changed))

    after = {s: m.seq for s, m in js.messages.items()}
    subjects = job_subjects(PROJECT, MODULE, "w")
    assert after[subjects.schedule(0)] > first[subjects.schedule(0)]
    assert after[subjects.schedule(1)] == first[subjects.schedule(1)]
    assert after[subjects.schedule(2)] == first[subjects.schedule(2)]
    assert js.messages[subjects.schedule(0)].data == b'{"n":2}'


def test_a_schedule_from_before_inputs_existed_is_not_republished():
    js = _Js()
    descriptor = JobDescriptor("w", triggers=(Every("1h"),))
    host = _host(MemoryDocuments(), [(descriptor, None)])
    subject = job_subjects(PROJECT, MODULE, "w").schedule(0)
    # What the previous release published: no input header.
    js.messages[subject] = SimpleNamespace(
        seq=9,
        headers={
            "Nats-Schedule": "@every 1h",
            "Nats-Schedule-Target": job_subjects(PROJECT, MODULE, "w").trigger,
            "Nats-Schedule-TTL": "3600s",
            "Abi-Job-Trigger": "schedule",
        },
        data=b"{}",
    )

    asyncio.run(host.reconcile_schedules(js, descriptor))

    assert js.published == [] and js.messages[subject].seq == 9


# --- the step journal ------------------------------------------------------------------


class _Connection:
    def __init__(self):
        self.published: list[tuple[str, bytes]] = []

    async def publish(self, subject, data=b"", **kwargs):
        self.published.append((subject, data))


class _Transport:
    def __init__(self):
        self.connection = _Connection()

    async def connect(self):
        return self.connection


class _Msg:
    def __init__(self, sequence=7, attempt=1, payload=None, trigger="manual"):
        from naas_abi_sdk.jobs import TRIGGER_HEADER

        self.data = json.dumps(payload or {}).encode()
        self.headers = {TRIGGER_HEADER: trigger}
        self.metadata = SimpleNamespace(
            sequence=SimpleNamespace(stream=sequence), num_delivered=attempt
        )
        self.calls: list[tuple] = []

    async def ack(self):
        self.calls.append(("ack",))

    async def nak(self, delay=None):
        self.calls.append(("nak", delay))

    async def term(self):
        self.calls.append(("term",))

    async def in_progress(self):
        self.calls.append(("in_progress",))


def _host(documents, jobs, **kwargs):
    return JobHost(
        transport=_Transport(),
        documents=documents,
        module_id=MODULE,
        project=PROJECT,
        handlers={d.name: (d, h) for d, h in jobs},
        instance_id="i-1",
        **kwargs,
    )


class _Outcomes:
    """Stands in for ``CompletionNotices``: child runs end when the test says."""

    def __init__(self):
        self.records: dict[str, dict] = {}
        self.waited: list[str] = []
        self.journal_at_wait: dict[str, dict] = {}
        self.docs = None

    async def wait(self, run, *, timeout=None):
        self.waited.append(run.run_id)
        if self.docs is not None:
            self.journal_at_wait[run.run_id] = {
                k: v.get("child") for k, v in self.docs.steps("flow:1").items()
            }
        while run.run_id not in self.records:
            await asyncio.sleep(0.005)
        return self.records[run.run_id]

    async def close(self):
        pass


class _FakeProxy:
    triggers: ClassVar[list[dict]] = []

    def __init__(self, transport, project, module_id, descriptor, documents=None):
        self.module_id, self.descriptor = module_id, descriptor

    async def trigger(self, payload=None, *, idempotency_key=None):
        sequence = 100 + len(_FakeProxy.triggers)
        _FakeProxy.triggers.append(
            {
                "module": self.module_id,
                "workflow": self.descriptor.name,
                "payload": payload,
                "key": idempotency_key,
            }
        )
        cancelled: list[str] = []
        return SimpleNamespace(
            run_id=f"{self.descriptor.name}:{sequence}",
            duplicate=False,
            module_id=self.module_id,
            cancel=lambda: _record(cancelled, "cancel"),
            cancelled=cancelled,
        )


async def _record(into, value):
    into.append(value)


@pytest.fixture(autouse=True)
def _fresh_proxy(monkeypatch):
    _FakeProxy.triggers = []
    monkeypatch.setattr(workflows, "JobProxy", _FakeProxy)


def _context(docs, *, run_id="flow:1", fired_at="t1", payload=None, outcomes=None):
    runtime = FlowRuntime(
        _Transport(),
        docs,
        MODULE,
        PROJECT,
        module_documents=lambda module_id: docs,
        poll_seconds=0.05,
    )
    ctx = FlowContext(
        run_id,
        "flow",
        1,
        {"kind": "manual"},
        payload or {},
        runtime=runtime,
        fired_at=fired_at,
    )
    if outcomes is not None:
        outcomes.docs = docs
        ctx._notices = outcomes
    return ctx


def test_a_journaled_step_returns_its_result_without_calling_the_function_again():
    docs = MemoryDocuments()
    calls = []

    async def fetch(n):
        calls.append(n)
        return TweetsOutput(count=n)

    first = asyncio.run(_context(docs).step("fetch", fetch, 2))
    # A later attempt of the same run: a new context, the same journal.
    again = asyncio.run(_context(docs).step("fetch", fetch, 99))

    assert (
        first == again == {"count": 2}
    )  # the JSON a replay returns, also the first time
    assert calls == [2]
    summary = docs.steps("flow:1")["fetch"]
    assert summary["status"] == "SUCCEEDED" and summary["attempt"] == 1
    assert summary["kind"] == "step" and summary["duration_ms"] >= 0
    assert summary["started_at"] and summary["finished_at"] and "result" not in summary
    assert docs.results("flow:1") == {"fetch": {"count": 2}}


def test_sync_functions_run_in_a_thread_and_kwargs_pass_through():
    docs = MemoryDocuments()
    threads = []

    def work(a, *, b):
        threads.append(threading.current_thread())
        return a + b

    assert asyncio.run(_context(docs).step("sum", work, 1, b=2)) == 3
    assert threads[0] is not threading.main_thread()


def test_a_failed_step_is_recorded_retried_locally_then_raised():
    docs = MemoryDocuments()
    attempts = []

    async def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("boom")
        return "ok"

    assert (
        asyncio.run(_context(docs).step("flaky", flaky, retries=2, backoff=0)) == "ok"
    )
    assert docs.steps("flow:1")["flaky"]["attempt"] == 3

    async def broken():
        raise RuntimeError("always")

    with pytest.raises(RuntimeError, match="always"):
        asyncio.run(
            _context(docs).step("broken", broken, retries=1, backoff=lambda n: 0)
        )
    broken_summary = docs.steps("flow:1")["broken"]
    assert broken_summary["status"] == "FAILED" and broken_summary["attempt"] == 2
    assert broken_summary["error"] == "RuntimeError: always"
    # A retry of the run runs it again; attempts keep counting.
    with pytest.raises(RuntimeError):
        asyncio.run(_context(docs).step("broken", broken))
    assert docs.steps("flow:1")["broken"]["attempt"] == 3


def test_non_retryable_errors_are_not_retried_locally():
    docs = MemoryDocuments()
    attempts = []

    async def bad():
        attempts.append(1)
        raise InvalidWorkflowInput("no")

    with pytest.raises(InvalidWorkflowInput):
        asyncio.run(_context(docs).step("bad", bad, retries=5, backoff=0))
    assert attempts == [1]


def test_step_keys_are_unique_per_run_and_checked():
    docs = MemoryDocuments()

    async def scenario():
        ctx = _context(docs)
        await ctx.step("a", lambda: 1)
        with pytest.raises(StepKeyError, match="used twice"):
            await ctx.step("a", lambda: 2)
        await ctx.map("m", [1, 2], lambda x: x)
        with pytest.raises(StepKeyError, match="used twice"):
            await ctx.step("m", lambda: 0)
        with pytest.raises(StepKeyError, match="used twice"):
            await ctx.step("m[0]", lambda: 0)
        for bad in ("", "x" * 201, "a\x00b", 3):
            with pytest.raises(StepKeyError):
                await ctx.step(bad, lambda: 0)

    asyncio.run(scenario())
    assert docs.results("flow:1")["a"] == 1  # the duplicate did not run


def test_a_step_result_is_capped_json():
    docs = MemoryDocuments()
    ctx = _context(docs)

    with pytest.raises(StepResultTooLarge, match="object storage") as caught:
        asyncio.run(ctx.step("big", lambda: "x" * (256 * 1024)))
    assert "262146 bytes" in str(caught.value)
    assert docs.steps("flow:1")["big"]["status"] == "FAILED"
    assert "big" not in docs.results("flow:1")
    with pytest.raises(StepResultNotJSON, match="not JSON"):
        asyncio.run(_context(docs).step("object", lambda: object()))
    with pytest.raises(StepResultNotJSON):
        asyncio.run(_context(docs).step("nan", lambda: float("nan")))
    assert (
        asyncio.run(_context(docs).step("limit", lambda: "x" * (256 * 1024 - 2)))
        is not None
    )


def test_map_journals_each_item_bounds_concurrency_and_keeps_order():
    docs = MemoryDocuments()
    running = []
    peak = []

    async def double(x):
        running.append(x)
        peak.append(len(running))
        await asyncio.sleep(0.01)
        running.remove(x)
        return x * 2

    results = asyncio.run(_context(docs).map("m", range(7), double, concurrency=3))

    assert results == [0, 2, 4, 6, 8, 10, 12] and max(peak) == 3
    assert sorted(docs.steps("flow:1")) == sorted(f"m[{i}]" for i in range(7))
    # A replay returns every item from the journal.
    again = asyncio.run(
        _context(docs).map("m", range(7), lambda x: pytest.fail("ran again"))
    )
    assert again == results


def test_map_stops_at_the_first_failure_and_keeps_what_finished():
    docs = MemoryDocuments()

    async def work(x):
        if x == 1:
            raise ValueError("item 1")
        await asyncio.sleep(0.2 if x else 0)
        return x

    with pytest.raises(ValueError, match="item 1"):
        asyncio.run(_context(docs).map("m", [0, 1, 2, 3], work, concurrency=4))

    steps = docs.steps("flow:1")
    assert steps["m[1]"]["status"] == "FAILED"
    assert steps["m[0]"]["status"] == "SUCCEEDED"
    assert steps["m[2]"]["status"] == "RUNNING"  # stopped; it runs again with the run


def test_a_journal_from_another_trigger_of_the_same_run_id_is_ignored():
    docs = MemoryDocuments()
    calls = []

    def work():
        calls.append(1)
        return len(calls)

    assert asyncio.run(_context(docs, fired_at="old").step("a", work)) == 1
    # The jobs stream was recreated: sequence 1 is a new trigger.
    assert asyncio.run(_context(docs, fired_at="new").step("a", work)) == 2
    assert asyncio.run(_context(docs, fired_at="new").step("a", work)) == 2
    assert calls == [1, 1]


def test_cancelling_the_run_stops_a_waiting_step():
    docs = MemoryDocuments()

    async def scenario():
        ctx = _context(docs)

        async def forever():
            await asyncio.sleep(60)

        task = asyncio.create_task(ctx.step("slow", forever))
        await asyncio.sleep(0.05)
        ctx.cancelled.set()
        with pytest.raises(WorkflowCancelled):
            await task
        with pytest.raises(WorkflowCancelled):  # nothing new starts
            await ctx.step("next", lambda: 1)

    asyncio.run(scenario())
    assert docs.steps("flow:1")["slow"]["status"] == "CANCELLED"
    assert "next" not in docs.steps("flow:1")


def test_the_step_summary_is_readable_without_results():
    docs = MemoryDocuments()

    async def scenario():
        ctx = _context(docs)
        await ctx.step("first", lambda: {"big": "x" * 1000})
        await ctx.step("second", lambda: 2)
        return await ctx.steps()

    summary = asyncio.run(scenario())

    assert [s["key"] for s in summary] == ["first", "second"]
    assert all(
        {"key", "kind", "status", "attempt", "started_at", "finished_at", "duration_ms"}
        <= set(s)
        for s in summary
    )
    assert "x" * 100 not in json.dumps(summary) and summary[0]["result_bytes"] > 1000


# --- child runs ------------------------------------------------------------------------


def test_a_child_run_is_journaled_before_waiting_and_a_replay_reattaches_to_it():
    docs, outcomes = MemoryDocuments(), _Outcomes()
    outcomes.records["child:100"] = {"status": "SUCCEEDED", "result": {"n": 5}}

    first = asyncio.run(
        _context(docs, outcomes=outcomes).call("acme.child", "child", {"x": 1}, key="c")
    )

    assert first == {"n": 5}
    assert (
        _FakeProxy.triggers
        == [
            {
                "module": "acme.child",
                "workflow": "child",
                "payload": {"x": 1},
                "key": "flow:1/c/1",  # run, step key and attempt: one trigger in the dedup window
            }
        ]
    )
    # The child's run id was in the journal when the parent started waiting.
    assert outcomes.journal_at_wait["child:100"]["c"] == {
        "module_id": "acme.child",
        "workflow": "child",
        "run_id": "child:100",
    }
    assert docs.steps("flow:1")["c"]["kind"] == "call"

    # The parent died mid-wait: its journal says RUNNING with a child.
    key = (steps_collection(PROJECT), "flow:1#c")
    running = docs.data[key].data | {"status": "RUNNING", "finished_at": ""}
    docs.data[key] = replace(docs.data[key], data=running)
    del docs.data[(results_collection(PROJECT), "flow:1#c")]
    outcomes2 = _Outcomes()
    outcomes2.records["child:100"] = {"status": "SUCCEEDED", "result": {"n": 6}}

    again = asyncio.run(
        _context(docs, outcomes=outcomes2).call(
            "acme.child", "child", {"x": 1}, key="c"
        )
    )

    assert (
        again == {"n": 6} and len(_FakeProxy.triggers) == 1
    )  # re-attached, not triggered
    assert outcomes2.waited == ["child:100"]
    # A finished child step is not even waited for.
    outcomes3 = _Outcomes()
    assert asyncio.run(
        _context(docs, outcomes=outcomes3).call(
            "acme.child", "child", {"x": 1}, key="c"
        )
    ) == {"n": 6}
    assert outcomes3.waited == [] and len(_FakeProxy.triggers) == 1


def test_a_failed_child_fails_the_step_and_the_next_attempt_starts_a_new_child():
    docs, outcomes = MemoryDocuments(), _Outcomes()
    outcomes.records["child:100"] = {"status": "FAILED", "error": "ValueError: no"}

    with pytest.raises(ChildRunFailed, match="ended FAILED: ValueError: no"):
        asyncio.run(
            _context(docs, outcomes=outcomes).call("acme.child", "child", key="c")
        )
    assert docs.steps("flow:1")["c"]["status"] == "FAILED"

    outcomes.records["child:101"] = {"status": "SUCCEEDED", "result": 1}
    assert (
        asyncio.run(
            _context(docs, outcomes=outcomes).call("acme.child", "child", key="c")
        )
        == 1
    )
    assert [t["key"] for t in _FakeProxy.triggers] == ["flow:1/c/1", "flow:1/c/2"]
    assert docs.steps("flow:1")["c"]["attempt"] == 2


def test_a_start_that_never_journaled_its_child_repeats_the_idempotency_key():
    docs, outcomes = MemoryDocuments(), _Outcomes()
    outcomes.records["child:100"] = {"status": "SUCCEEDED", "result": 1}
    outcomes.records["child:101"] = {"status": "SUCCEEDED", "result": 1}

    async def crash_before_journaling_the_child():
        ctx = _context(docs, outcomes=outcomes)
        original = ctx._journal.set_child

        async def die(key, child):
            raise RuntimeError("host died")

        ctx._journal.set_child = die
        with pytest.raises(RuntimeError):
            await ctx.call("acme.child", "child", key="c")
        ctx._journal.set_child = original

    asyncio.run(crash_before_journaling_the_child())
    asyncio.run(_context(docs, outcomes=outcomes).call("acme.child", "child", key="c"))

    # Same attempt number: inside the 2 minute window JetStream drops the second trigger.
    assert [t["key"] for t in _FakeProxy.triggers] == ["flow:1/c/1", "flow:1/c/1"]


def test_map_call_starts_children_with_bounded_concurrency_and_keeps_order():
    docs, outcomes = MemoryDocuments(), _Outcomes()

    async def scenario():
        ctx = _context(docs, outcomes=outcomes)
        task = asyncio.create_task(
            ctx.map_call(
                "fan",
                "acme.child",
                "child",
                [{"i": i} for i in range(5)],
                concurrency=2,
            )
        )
        await asyncio.sleep(0.05)
        assert len(_FakeProxy.triggers) == 2  # two in flight, three waiting
        for n in range(100, 105):
            outcomes.records[f"child:{n}"] = {"status": "SUCCEEDED", "result": {"n": n}}
        return await task

    results = asyncio.run(scenario())

    assert [r["n"] for r in results] == [100, 101, 102, 103, 104]
    assert [t["payload"]["i"] for t in _FakeProxy.triggers] == [0, 1, 2, 3, 4]
    assert sorted(docs.steps("flow:1")) == sorted(f"fan[{i}]" for i in range(5))


def test_a_workflow_cannot_call_itself():
    docs = MemoryDocuments()
    ctx = _context(docs)

    with pytest.raises(SelfCall, match="cannot call itself"):
        asyncio.run(ctx.call(MODULE, "flow", {}))
    with pytest.raises(SelfCall):
        asyncio.run(_context(docs).map_call("fan", MODULE, "flow", [{}]))
    assert _FakeProxy.triggers == []
    assert issubclass(SelfCall, NonRetryable)
    # Another workflow of the same module, or the same name elsewhere, is fine.
    outcomes = _Outcomes()
    outcomes.records["other:100"] = {"status": "SUCCEEDED", "result": 1}
    outcomes.records["flow:101"] = {"status": "SUCCEEDED", "result": 2}
    assert (
        asyncio.run(_context(docs, outcomes=outcomes).call(MODULE, "other", key="a"))
        == 1
    )
    assert (
        asyncio.run(
            _context(docs, outcomes=outcomes).call("acme.other", "flow", key="b")
        )
        == 2
    )


def test_cancelling_a_parent_cancels_its_running_children():
    docs, outcomes = MemoryDocuments(), _Outcomes()
    runs = []

    async def scenario():
        ctx = _context(docs, outcomes=outcomes)
        task = asyncio.create_task(
            ctx.map_call("fan", "acme.child", "child", [{}, {}], concurrency=2)
        )
        await asyncio.sleep(0.05)
        runs.extend(ctx._children.values())
        ctx.cancelled.set()  # the host got the cancel
        with pytest.raises(WorkflowCancelled):
            await task
        await ctx.finish("CANCELLED")
        return ctx

    ctx = asyncio.run(scenario())

    assert len(runs) == 2 and all(run.cancelled == ["cancel"] for run in runs)
    assert {docs.steps("flow:1")[f"fan[{i}]"]["status"] for i in range(2)} == {
        "CANCELLED"
    }
    assert ctx._children == {}


def test_a_shutdown_or_timeout_does_not_cancel_the_children():
    docs, outcomes = MemoryDocuments(), _Outcomes()

    async def scenario():
        ctx = _context(docs, outcomes=outcomes)
        task = asyncio.create_task(ctx.call("acme.child", "child", key="c"))
        await asyncio.sleep(0.05)
        run = next(iter(ctx._children.values()))
        ctx.cancelled.set()
        with pytest.raises(WorkflowCancelled):
            await task
        await ctx.finish("FAILED")  # interrupted by shutdown: retried, re-attaches
        return run

    run = asyncio.run(scenario())

    assert run.cancelled == []
    assert docs.steps("flow:1")["c"]["status"] == "RUNNING"


# --- completion notices ----------------------------------------------------------------


class _NoticeConnection:
    max_payload = 1 << 20

    def __init__(self):
        self.callbacks = {}
        self.unsubscribed = []

    async def subscribe(self, subject, cb=None, **kwargs):
        self.callbacks[subject] = cb
        return SimpleNamespace(unsubscribe=lambda: _record(self.unsubscribed, subject))

    async def flush(self, timeout=None):
        return None


class _NoticeTransport:
    def __init__(self, fail=False):
        self.nc, self.fail = _NoticeConnection(), fail

    async def connect(self):
        if self.fail:
            raise RuntimeError("broker down")
        return self.nc


class _Run:
    """A JobRun whose record the test controls."""

    def __init__(self, transport, record):
        self.transport, self.project = transport, PROJECT
        self.module_id, self.job, self.run_id = "acme.child", "child", "child:5"
        self.record, self.reads = record, 0

    async def status(self):
        self.reads += 1
        return self.record


def test_a_completion_notice_wakes_a_waiter_before_its_slow_poll():
    transport = _NoticeTransport()
    run = _Run(transport, {"status": "RUNNING"})
    notices = workflows.CompletionNotices(transport, poll_seconds=30)
    subject = job_subjects(PROJECT, "acme.child", "child").done

    async def scenario():
        waiter = asyncio.create_task(notices.wait(run, timeout=5))
        await asyncio.sleep(0.05)
        assert run.reads == 1  # nothing to read until something happens
        run.record = {"status": "SUCCEEDED", "result": 1}
        # Another run's notice does not wake it; its own does.
        await transport.nc.callbacks[subject](
            SimpleNamespace(data=b'{"run_id": "other:1"}')
        )
        await asyncio.sleep(0.05)
        assert run.reads == 1
        await transport.nc.callbacks[subject](
            SimpleNamespace(data=b'{"run_id": "child:5", "status": "SUCCEEDED"}')
        )
        record = await asyncio.wait_for(waiter, 2)
        await notices.close()
        return record

    assert asyncio.run(scenario())["status"] == "SUCCEEDED"
    assert transport.nc.unsubscribed == [subject]


def test_waiters_fall_back_to_polling_when_notices_are_lost_or_unavailable():
    for transport in (_NoticeTransport(), _NoticeTransport(fail=True)):
        run = _Run(transport, {"status": "RUNNING"})
        notices = workflows.CompletionNotices(transport, poll_seconds=0.02)

        async def scenario(run=run, notices=notices):
            waiter = asyncio.create_task(notices.wait(run, timeout=5))
            await asyncio.sleep(0.1)
            run.record = {"status": "FAILED", "error": "x"}  # no notice ever comes
            return await asyncio.wait_for(waiter, 2)

        assert asyncio.run(scenario())["status"] == "FAILED"
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(
            workflows.CompletionNotices(_NoticeTransport(), poll_seconds=0.01).wait(
                _Run(_NoticeTransport(), {"status": "RUNNING"}), timeout=0.1
            )
        )


# --- the caller side -------------------------------------------------------------------


def _proxy(descriptor=None, **kwargs):
    descriptor = descriptor or Flows.jobs[0]
    return WorkflowProxy(
        _Transport(), PROJECT, MODULE, descriptor, MemoryDocuments(), **kwargs
    )


def test_a_proxy_starts_runs_with_dict_or_model_inputs():
    proxy = _proxy(input_type=TweetsInput, output_type=TweetsOutput)

    run = asyncio.run(proxy.start(TweetsInput(filter="db"), idempotency_key="k"))
    assert isinstance(run, WorkflowRun)
    assert _FakeProxy.triggers[-1]["payload"] == {"filter": "db"}
    assert _FakeProxy.triggers[-1]["key"] == "k"
    asyncio.run(proxy.start({"filter": "sql"}))
    assert _FakeProxy.triggers[-1]["payload"] == {"filter": "sql"}
    with pytest.raises(ValueError, match="filter field required"):
        asyncio.run(proxy.start({}))  # checked before anything is sent
    with pytest.raises(TypeError, match="dict or a model"):
        asyncio.run(_proxy().start([1]))
    assert json.loads(proxy.descriptor.input_schema) == proxy.input_schema
    assert proxy.output_schema["title"] == "TweetsOutput"
    assert proxy.name == "tweets"


class _Finished:
    """A JobRun that is already over, for WorkflowRun."""

    def __init__(self, docs, record, run_id="tweets:9"):
        self.transport, self.project = _Transport(), PROJECT
        self.module_id, self.job, self.run_id = MODULE, "tweets", run_id
        self.record, self.duplicate, self._docs_ = record, False, docs
        self.cancels = 0

    async def status(self):
        return self.record

    def _docs(self):
        return self._docs_

    async def cancel(self):
        self.cancels += 1


def test_a_workflow_run_reports_status_result_steps_and_cancels():
    docs = MemoryDocuments()
    asyncio.run(_context(docs, run_id="tweets:9").step("fetch", lambda: [1, 2]))
    done = _Finished(docs, {"status": "SUCCEEDED", "result": {"count": 2}})
    run = WorkflowRun(done, output_type=TweetsOutput, poll_seconds=0.01)

    assert run.run_id == "tweets:9" and run.workflow == "tweets" and not run.duplicate
    assert asyncio.run(run.status())["status"] == "SUCCEEDED"
    assert asyncio.run(run.wait(timeout=2))["result"] == {"count": 2}
    output = asyncio.run(run.result(timeout=2))
    assert isinstance(output, TweetsOutput) and output.count == 2
    steps = asyncio.run(run.steps())
    assert [(s["key"], s["status"]) for s in steps] == [("fetch", "SUCCEEDED")]
    asyncio.run(run.cancel())
    assert done.cancels == 1

    untyped = WorkflowRun(
        _Finished(docs, {"status": "SUCCEEDED", "result": {"count": 2}})
    )
    assert asyncio.run(untyped.result()) == {"count": 2}


def test_a_failed_or_truncated_run_has_no_output():
    docs = MemoryDocuments()
    failed = WorkflowRun(
        _Finished(docs, {"status": "FAILED", "error": "ValueError: x"})
    )
    with pytest.raises(
        WorkflowRunFailed, match="ended FAILED: ValueError: x"
    ) as caught:
        asyncio.run(failed.result(timeout=2))
    assert caught.value.status == "FAILED" and caught.value.run_id == "tweets:9"
    truncated = WorkflowRun(
        _Finished(
            docs, {"status": "SUCCEEDED", "result": {"truncated": True, "preview": "{"}}
        )
    )
    with pytest.raises(WorkflowRunFailed, match="reference"):
        asyncio.run(truncated.result(timeout=2))


def test_the_client_and_module_proxy_resolve_workflows_by_name():
    from naas_abi_sdk.client import ABIClient
    from naas_abi_sdk.discovery import ModuleProxy
    from naas_abi_sdk.transport import RPCError

    client = ABIClient("nats://unused", "t")
    proxy = client.get_workflow(
        "acme.flows", "tweets", project="zen", output_type=TweetsOutput
    )
    assert isinstance(proxy, WorkflowProxy)
    assert (proxy.module_id, proxy.project, proxy.name) == (
        "acme.flows",
        "zen",
        "tweets",
    )
    assert proxy.descriptor.kind == "workflow" and proxy.output_type is TweetsOutput
    # get_job keeps working on workflows.
    assert client.get_job("acme.flows", "tweets", project="zen").name == "tweets"

    instance = SimpleNamespace(
        jobs=(
            JobDescriptor("plain"),
            *(JobDescriptor.from_pb(j.to_pb()) for j in Flows.jobs),
        )
    )
    module = ModuleProxy.__new__(ModuleProxy)
    module.client = SimpleNamespace(transport=_Transport(), project="zen")
    module.module_id = "acme.flows"

    async def ready_instances():
        return (instance,)

    module.ready_instances = ready_instances
    found = asyncio.run(module.get_workflow("tweets", input_type=TweetsInput))
    assert found.descriptor.is_workflow and found.input_type is TweetsInput
    assert asyncio.run(module.get_job("tweets")).name == "tweets"
    for missing in ("plain", "nope"):  # a plain job is not a workflow
        with pytest.raises(RPCError) as caught:
            asyncio.run(module.get_workflow(missing))
        assert caught.value.code == "WORKFLOW_NOT_FOUND"


def test_a_module_reaches_its_own_workflows_through_its_bound_host():
    module = _bound()
    with pytest.raises(JobsNotHosted):
        module.get_workflow("tweets")

    docs = MemoryDocuments()
    host_loop = asyncio.new_event_loop()
    thread = threading.Thread(target=host_loop.run_forever, daemon=True)
    thread.start()
    seen = {}

    class Proxy(_FakeProxy):
        async def trigger(self, payload=None, *, idempotency_key=None):
            seen["loop"] = asyncio.get_running_loop()
            return await super().trigger(payload, idempotency_key=idempotency_key)

    workflows.JobProxy = Proxy
    try:
        host = SimpleNamespace(
            handlers={j.name: (j, None) for j in Flows.jobs},
            transport=_Transport(),
            project=PROJECT,
            module_id=MODULE,
            documents=docs,
            workflow_poll_seconds=0.01,
        )
        module._bind_job_host(host, host_loop)
        proxy = module.get_workflow("tweets")
        # Typed by the module's own declaration, and usable from any loop.
        assert proxy.input_type is TweetsInput and proxy.output_type is TweetsOutput
        run = asyncio.run(proxy.start({"filter": "db"}))
        assert seen["loop"] is host_loop
        assert run.module_id == MODULE
        with pytest.raises(ValueError, match="no workflow named"):
            module.get_workflow("nope")
        with pytest.raises(ValueError, match="no workflow named"):
            module.get_workflow("raw_flow")  # declared as 'raw'
    finally:
        host_loop.call_soon_threadsafe(host_loop.stop)
        thread.join(5)
        host_loop.close()


def test_pydantic_models():
    pydantic = pytest.importorskip("pydantic")

    class Query(pydantic.BaseModel):
        term: str
        limit: int = 10

    class Found(pydantic.BaseModel):
        titles: list[str]

    class Searches(JobsMixin):
        @workflow()
        async def search(self, ctx, inp: Query) -> Found:
            return Found(titles=[inp.term] * inp.limit)

    descriptor = Searches.jobs[0]
    assert json.loads(descriptor.input_schema)["required"] == ["term"]
    handler = object.__new__(Searches)._job_handlers["search"]
    out = asyncio.run(
        handler(_context(MemoryDocuments(), payload={"term": "t", "limit": 2}))
    )
    assert out == {"titles": ["t", "t"]}
    with pytest.raises(InvalidWorkflowInput, match="term"):
        asyncio.run(handler(_context(MemoryDocuments(), payload={"limit": 2})))


# --- review fixes ----------------------------------------------------------------------


def test_a_new_attempt_does_not_inherit_the_child_of_a_failed_one():
    docs, outcomes = MemoryDocuments(), _Outcomes()
    outcomes.records["child:100"] = {"status": "FAILED", "error": "x"}
    with pytest.raises(ChildRunFailed):
        asyncio.run(
            _context(docs, outcomes=outcomes).call("acme.child", "child", key="c")
        )
    assert docs.steps("flow:1")["c"]["child"]["run_id"] == "child:100"

    # The next attempt starts, and its host dies before it journals the new child.
    async def die_before_journaling():
        ctx = _context(docs, outcomes=outcomes)

        async def die(key, child):
            raise RuntimeError("host died")

        ctx._journal.set_child = die
        with pytest.raises(RuntimeError):
            await ctx.call("acme.child", "child", key="c")

    asyncio.run(die_before_journaling())
    stuck = docs.steps("flow:1")["c"]
    assert stuck["status"] == "RUNNING" and "child" not in stuck  # not the failed run

    outcomes.records["child:102"] = {"status": "SUCCEEDED", "result": 7}
    # The replay triggers a child; it does not wait for the failed one again.
    assert (
        asyncio.run(
            _context(docs, outcomes=outcomes).call("acme.child", "child", key="c")
        )
        == 7
    )
    assert len(_FakeProxy.triggers) == 3
    assert "child:100" not in outcomes.waited[1:]


def test_step_keys_have_no_control_characters():
    docs = MemoryDocuments()
    for bad in ("a\nb", "a\rb", "a\tb", "a\x7fb", "a\x1fb"):
        with pytest.raises(StepKeyError, match="control characters"):
            asyncio.run(_context(docs).step(bad, lambda: 1))
        with pytest.raises(StepKeyError, match="control characters"):
            asyncio.run(
                _context(docs, outcomes=_Outcomes()).map_call(
                    bad, "acme.child", "child", [{}]
                )
            )
    assert _FakeProxy.triggers == []
    assert asyncio.run(_context(docs).step("file name.csv/é", lambda: 1)) == 1


def test_a_typed_workflow_can_skip():
    module = _bound()
    docs = MemoryDocuments()

    async def nothing_to_do(ctx, inp):
        ctx.skip("nothing new")

    module.declare_workflow(
        "quiet", nothing_to_do, input_type=TweetsInput, output_type=TweetsOutput
    )
    descriptor = next(j for j in module.jobs if j.name == "quiet")
    handler = module._job_handlers["quiet"]
    host = _host(docs, [(descriptor, handler)])

    asyncio.run(
        host.handle(descriptor, handler, _Msg(sequence=4, payload={"filter": "db"}))
    )

    record = docs.data[(runs_collection(PROJECT), "quiet:4")].data
    assert record["status"] == "SKIPPED" and record["skip_reason"] == "nothing new"
    assert record["result"] is None
    # Without skip(), None is still not a TweetsOutput.
    module.declare_workflow("lazy", _returns(None), output_type=TweetsOutput)
    with pytest.raises(InvalidWorkflowOutput):
        asyncio.run(module._job_handlers["lazy"](_context(docs)))


def test_a_skipped_run_has_no_output_for_result_and_for_a_parent():
    docs = MemoryDocuments()
    skipped = WorkflowRun(
        _Finished(docs, {"status": "SKIPPED", "result": None}), output_type=TweetsOutput
    )
    assert asyncio.run(skipped.result(timeout=2)) is None  # not model_validate(None)

    outcomes = _Outcomes()
    outcomes.records["child:100"] = {"status": "SKIPPED", "result": None}
    assert (
        asyncio.run(
            _context(docs, outcomes=outcomes).call("acme.child", "child", key="c")
        )
        is None
    )
    assert docs.steps("flow:1")["c"]["status"] == "SUCCEEDED"


def test_a_model_of_another_class_is_not_the_output_type():
    Other = model("Other", {"count": "integer"})

    module = _bound()
    module.declare_workflow("wrong", _returns(Other(count=1)), output_type=TweetsOutput)

    with pytest.raises(
        InvalidWorkflowOutput, match="TweetsOutput was expected, got Other"
    ):
        asyncio.run(module._job_handlers["wrong"](_context(MemoryDocuments())))


def test_a_failing_journal_cleanup_leaves_the_run_for_the_next_pass(monkeypatch):
    docs = MemoryDocuments()

    async def handler(ctx):
        await ctx.step("one", lambda: 1)

    descriptor = JobDescriptor("w", kind="workflow")
    host = _host(docs, [(descriptor, handler)])
    asyncio.run(host.handle(descriptor, handler, _Msg(sequence=3)))
    later = datetime.now(timezone.utc) + timedelta(days=30)

    from naas_abi_sdk import job_host as job_host_module

    real = job_host_module.delete_steps

    async def broken(*args):
        raise RuntimeError("store hiccup")

    monkeypatch.setattr(job_host_module, "delete_steps", broken)
    with pytest.raises(RuntimeError):
        asyncio.run(host.prune(later))
    # The record is still there: its journal is not orphaned.
    assert (runs_collection(PROJECT), "w:3") in docs.data and docs.steps("w:3")

    monkeypatch.setattr(job_host_module, "delete_steps", real)
    assert asyncio.run(host.prune(later)) == 1
    assert not docs.steps("w:3") and (runs_collection(PROJECT), "w:3") not in docs.data
