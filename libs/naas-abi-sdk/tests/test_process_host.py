"""Workflows and pipelines served over NATS (extras: workflows, rdf, agents).

A real nats-server, a ``ProcessHost`` on it, and a ``ModuleProxy`` calling it with
tokens bound to the instance, as another module does. Discovery is a fake that
refuses what the real one would: a token bound to another instance, an undeclared
process.
"""

from __future__ import annotations

import asyncio
import base64
import json
import shutil
import socket
import subprocess
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("pydantic")
pytest.importorskip("rdflib")

from naas_abi_proto.discovery.v1 import discovery_pb2 as discovery_pb
from rdflib import Graph, Literal, URIRef

from naas_abi_sdk import process_host
from naas_abi_sdk.discovery import ModuleInstance, ModuleProxy, ProcessDescriptor
from naas_abi_sdk.pipeline import Pipeline, PipelineParameters
from naas_abi_sdk.process_host import ProcessHost
from naas_abi_sdk.transport import RPCError, Transport
from naas_abi_sdk.workflow import Workflow, WorkflowConfiguration, WorkflowParameters

pytestmark = pytest.mark.skipif(
    shutil.which("nats-server") is None, reason="nats-server not installed"
)

MB = 1024 * 1024
INSTANCE = "i-1"
PROJECT = "acme"


class EchoParameters(WorkflowParameters):
    name: str
    times: int = 1


class EchoWorkflow(Workflow[EchoParameters]):
    """Repeats a name."""

    runs = 0

    async def run(self, parameters: EchoParameters):
        type(self).runs += 1
        return {"echo": parameters.name * parameters.times}


class SleepParameters(WorkflowParameters):
    seconds: float = 0.0


class SleepWorkflow(Workflow[SleepParameters]):
    """Waits."""

    started = asyncio.Event
    cancelled = False
    running = 0
    peak = 0

    async def run(self, parameters: SleepParameters):
        cls = type(self)
        cls.running += 1
        cls.peak = max(cls.peak, cls.running)
        try:
            await asyncio.sleep(parameters.seconds)
            return {"slept": parameters.seconds}
        except asyncio.CancelledError:
            cls.cancelled = True
            raise
        finally:
            cls.running -= 1


class BrokenWorkflow(Workflow[WorkflowParameters]):
    runs = 0

    async def run(self, parameters: WorkflowParameters):
        type(self).runs += 1
        raise KeyError("the-secret-api-key")


class BytesWorkflow(Workflow[WorkflowParameters]):
    """Answers something JSON cannot hold."""

    async def run(self, parameters: WorkflowParameters):
        return {"data": b"bytes"}


class SizeParameters(WorkflowParameters):
    size: int


class BigWorkflow(Workflow[SizeParameters]):
    """Returns a result of the size asked, and echoes how long its input was."""

    async def run(self, parameters: SizeParameters):
        return {"data": "x" * parameters.size}


class LengthWorkflow(Workflow[EchoParameters]):
    async def run(self, parameters: EchoParameters):
        return {"length": len(parameters.name)}


class TriplesParameters(PipelineParameters):
    count: int = 3


class LoadPipeline(Pipeline[TriplesParameters]):
    """Loads triples."""

    async def run(self, parameters: TriplesParameters):
        graph = Graph()
        for index in range(parameters.count):
            graph.add(
                (
                    URIRef(f"http://example.org/s{index}"),
                    URIRef("http://example.org/p"),
                    Literal(f"value {index} é"),
                )
            )
        return graph


class NotAGraphPipeline(Pipeline[TriplesParameters]):
    async def run(self, parameters: TriplesParameters):
        return {"not": "a graph"}


WORKFLOWS = {
    "echo_workflow": EchoWorkflow,
    "sleep_workflow": SleepWorkflow,
    "broken_workflow": BrokenWorkflow,
    "bytes_workflow": BytesWorkflow,
    "big_workflow": BigWorkflow,
    "length_workflow": LengthWorkflow,
}
PIPELINES = {"load_pipeline": LoadPipeline, "not_a_graph_pipeline": NotAGraphPipeline}


@pytest.fixture(autouse=True)
def reset_counters():
    EchoWorkflow.runs = BrokenWorkflow.runs = 0
    SleepWorkflow.cancelled, SleepWorkflow.running, SleepWorkflow.peak = False, 0, 0


@pytest.fixture(autouse=True)
def fast_keepalive(monkeypatch):
    from naas_abi_sdk import app_streams

    monkeypatch.setattr(app_streams, "KEEPALIVE_SECONDS", 0.3)
    monkeypatch.setattr(app_streams, "LINGER_SECONDS", 0.2)


def _broker(tmp_path, *config_lines):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    command = ["nats-server", "-a", "127.0.0.1", "-p", str(port)]
    if config_lines:
        config = tmp_path / "nats.conf"
        config.write_text("\n".join(config_lines) + "\n")
        command += ["-c", str(config)]
    process = subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.05)
    return process, f"nats://127.0.0.1:{port}"


@pytest.fixture(params=[None, 65536], ids=["1MiB-broker", "64KiB-broker"])
def broker(request, tmp_path):
    lines = [f"max_payload: {request.param}"] if request.param else []
    process, url = _broker(tmp_path, *lines)
    yield url
    process.terminate()
    process.wait(timeout=5)


def _b64(value: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()


def bound_token(audience: str, lifetime: float = 60.0) -> str:
    """A caller's token as a JWT does carry its audience and expiry."""
    claims = {"sub": "caller", "aud": audience, "exp": time.time() + lifetime}
    return f"{_b64({'alg': 'none'})}.{_b64(claims)}.signature"


class Caller:
    """The caller's token source: a call to a module gets a token bound to it."""

    def __init__(self, audience_of=lambda audience: audience, lifetime=60.0):
        self.audience_of, self.lifetime = audience_of, lifetime
        self._issued: dict[str, tuple[float, str]] = {}

    def __call__(self) -> str:
        return bound_token("engine")

    def for_audience(self, audience: str) -> str:
        """One token per audience while it lasts, as ``ModuleToken`` caches them."""
        issued = self._issued.get(audience)
        if issued is None or time.time() >= issued[0]:
            token = bound_token(self.audience_of(audience), self.lifetime)
            issued = self._issued[audience] = (time.time() + self.lifetime, token)
        return issued[1]


class Fixed:
    """A token source that always sends the same token, whatever its expiry."""

    def __init__(self, token: str):
        self.token = token

    def __call__(self) -> str:
        return self.token

    def for_audience(self, audience: str) -> str:
        return self.token


class Discovery:
    """What the real service answers to ``authorize_process`` for this instance."""

    def __init__(self, declared):
        self.declared = set(declared)
        self.calls = 0
        self.refuse: str | None = None

    async def call(self, operation, request, response_type):
        assert operation == "authorize_process"
        self.calls += 1
        if self.refuse:
            raise RPCError(self.refuse, "refused")
        claims = json.loads(
            base64.urlsafe_b64decode(request.caller_token.split(".")[1] + "==")
        )
        if claims["aud"] != request.instance_id:
            raise RPCError("UNAUTHENTICATED", "Missing or invalid service token")
        if (request.process_kind, request.process_name) not in self.declared:
            raise RPCError("PROCESS_NOT_FOUND", request.process_name)
        return response_type(caller_identity=claims["sub"])


class World:
    def __init__(self, url, host, discovery, host_transport):
        self.url, self.host, self.discovery = url, host, discovery
        self.host_transport = host_transport
        self.transports = []

    def module(self, caller=None, status="READY", processes=None) -> ModuleProxy:
        """The calling side: a proxy of the module as discovery lists it."""
        transport = Transport(self.url, caller or Caller())
        self.transports.append(transport)
        listed = (
            processes
            if processes is not None
            else tuple(
                ProcessDescriptor(name, kind)
                for kind, name in sorted(self.discovery.declared, key=lambda k: k[::-1])
            )
        )
        instance = ModuleInstance(
            "acme.mod", INSTANCE, "0.0.0", 1, status, 0.0, (), processes=listed
        )
        return ModuleProxy(
            SimpleNamespace(
                project=PROJECT,
                transport=transport,
                get_module=AsyncMock(return_value=(instance,)),
            ),
            "acme.mod",
        )

    async def close(self):
        await self.host.close()
        for transport in [self.host_transport, *self.transports]:
            await transport.close()


async def serve(url, *, declared=None, workflows=None, pipelines=None, **options):
    workflows = WORKFLOWS if workflows is None else workflows
    pipelines = PIPELINES if pipelines is None else pipelines
    discovery = Discovery(
        declared
        if declared is not None
        else [("workflow", n) for n in workflows] + [("pipeline", n) for n in pipelines]
    )
    transport = Transport(url, "module-token")
    session = SimpleNamespace(
        instance_id=INSTANCE,
        lease_token="l" * 32,
        client=SimpleNamespace(
            transport=transport, project=PROJECT, _call=discovery.call
        ),
    )
    host = ProcessHost(
        session,
        {n: cls(WorkflowConfiguration()) for n, cls in workflows.items()},
        {n: cls(None) for n, cls in pipelines.items()},
        **options,
    )
    await host.start()
    return World(url, host, discovery, transport)


def run(scenario):
    asyncio.run(asyncio.wait_for(scenario(), 60))


# -- calls ---------------------------------------------------------------------


def test_a_module_runs_another_modules_workflow_and_pipeline(broker):
    async def scenario():
        world = await serve(broker)
        try:
            module = world.module()
            workflow = module.get_workflow("echo_workflow")
            assert await workflow.run({"name": "ab", "times": 2}) == {"echo": "abab"}
            # A pydantic model is as good as a dict.
            assert await workflow.run(EchoParameters(name="z")) == {"echo": "z"}
            graph = await module.get_pipeline("load_pipeline").run({"count": 4})
            assert isinstance(graph, Graph) and len(graph) == 4
            assert (
                URIRef("http://example.org/s3"),
                URIRef("http://example.org/p"),
                Literal("value 3 é"),
            ) in graph
            # Nothing to say is an empty graph, not an error.
            assert (
                len(await module.get_pipeline("load_pipeline").run({"count": 0})) == 0
            )
        finally:
            await world.close()

    run(scenario)


def test_describe_gives_the_parameter_schema_and_description(broker):
    async def scenario():
        world = await serve(broker)
        try:
            module = world.module()
            description = await module.get_workflow("echo_workflow").describe()
            assert description.kind == "workflow"
            assert description.description == "Repeats a name."
            assert set(description.parameters_schema["properties"]) == {"name", "times"}
            assert description.parameters_schema["required"] == ["name"]
            pipeline = await module.get_pipeline("load_pipeline").describe()
            assert (pipeline.kind, pipeline.description) == (
                "pipeline",
                "Loads triples.",
            )
            # Describing runs nothing.
            assert EchoWorkflow.runs == 0
        finally:
            await world.close()

    run(scenario)


def test_parameters_are_validated_into_the_model_before_anything_runs(broker):
    async def scenario():
        world = await serve(broker)
        try:
            workflow = world.module().get_workflow("echo_workflow")
            for bad in ({}, {"name": 3.5}, {"name": "a", "times": "many"}):
                with pytest.raises(RPCError) as error:
                    await workflow.run(bad)
                assert error.value.code == "INVALID_ARGUMENT"
            # The message names the fields, not the values given.
            with pytest.raises(RPCError, match="times") as error:
                await workflow.run({"name": "a", "times": "secret-value"})
            assert "secret-value" not in str(error.value)
            assert EchoWorkflow.runs == 0
        finally:
            await world.close()

    run(scenario)


def test_a_failing_process_is_one_attempt_and_leaks_nothing(broker):
    async def scenario():
        world = await serve(broker)
        try:
            module = world.module()
            with pytest.raises(RPCError) as error:
                await module.get_workflow("broken_workflow").run({})
            assert error.value.code == "PROCESS_ERROR"
            assert "the-secret-api-key" not in str(error.value)
            assert BrokenWorkflow.runs == 1  # never retried
            with pytest.raises(RPCError) as error:
                await module.get_workflow("bytes_workflow").run({})
            assert error.value.code == "PROCESS_ERROR"
            with pytest.raises(RPCError, match="rdflib Graph"):
                await module.get_pipeline("not_a_graph_pipeline").run({})
        finally:
            await world.close()

    run(scenario)


# -- authorization ----------------------------------------------------------------


def test_a_token_bound_to_another_instance_is_refused_before_the_process_runs(broker):
    async def scenario():
        world = await serve(broker)
        try:
            # The token a caller holds for some other instance of the module.
            stranger = world.module(Caller(audience_of=lambda _: "i-2"))
            with pytest.raises(RPCError) as error:
                await stranger.get_workflow("echo_workflow").run({"name": "a"})
            assert error.value.code == "UNAUTHENTICATED"
            with pytest.raises(RPCError) as error:
                await stranger.get_workflow("echo_workflow").describe()
            assert error.value.code == "UNAUTHENTICATED"
            assert EchoWorkflow.runs == 0
        finally:
            await world.close()

    run(scenario)


def test_an_undeclared_process_is_refused_before_the_process_runs(broker):
    async def scenario():
        # Served, but the registry does not declare it for this instance.
        world = await serve(broker, declared=[("workflow", "length_workflow")])
        try:
            module = world.module(
                processes=(ProcessDescriptor("echo_workflow", "workflow"),)
            )
            with pytest.raises(RPCError) as error:
                await module.get_workflow("echo_workflow").run({"name": "a"})
            assert error.value.code == "PROCESS_NOT_FOUND"
            assert EchoWorkflow.runs == 0
            # A workflow's name is not a pipeline's.
            other = world.module(
                processes=(ProcessDescriptor("length_workflow", "pipeline"),)
            )
            with pytest.raises(RPCError) as error:
                await other.get_pipeline("length_workflow").run({})
            assert error.value.code in ("PROCESS_NOT_FOUND", "MODULE_UNAVAILABLE")
        finally:
            await world.close()

    run(scenario)


def test_an_unauthorized_caller_makes_the_host_pull_nothing(broker, monkeypatch):
    async def scenario():
        world = await serve(broker)
        pulled = []
        original = process_host.pull_body

        def spy(*args, **kwargs):
            pulled.append(args)
            return original(*args, **kwargs)

        monkeypatch.setattr(process_host, "pull_body", spy)
        try:
            stranger = world.module(Caller(audience_of=lambda _: "i-2"))
            with pytest.raises(RPCError) as error:
                # Too large for one message on either broker.
                await stranger.get_workflow("length_workflow").run(
                    {"name": "n" * (2 * MB)}
                )
            assert error.value.code == "UNAUTHENTICATED"
            assert pulled == []
        finally:
            await world.close()

    run(scenario)


def test_discovery_answers_are_reused_for_five_seconds_never_past_the_token_and_refusals_never(
    broker,
):
    async def scenario():
        world = await serve(broker)
        try:
            workflow = world.module().get_workflow("echo_workflow")
            await workflow.run({"name": "a"})
            await workflow.run({"name": "a"})
            await workflow.run({"name": "a"})
            assert world.discovery.calls == 1
            # Another process asks again.
            await world.module().get_workflow("length_workflow").run({"name": "a"})
            assert world.discovery.calls == 2
            # A token that expires soon is not trusted past its expiry.
            token = bound_token(INSTANCE, lifetime=0.6)
            short = world.module(Fixed(token)).get_workflow("echo_workflow")
            await short.run({"name": "a"})
            await short.run({"name": "a"})
            assert world.discovery.calls == 3
            await asyncio.sleep(0.7)
            await short.run({"name": "a"})
            assert world.discovery.calls == 4
        finally:
            await world.close()

    run(scenario)


def test_a_refusal_is_not_remembered(broker):
    async def scenario():
        world = await serve(broker)
        try:
            workflow = world.module().get_workflow("echo_workflow")
            world.discovery.refuse = "PERMISSION_DENIED"
            with pytest.raises(RPCError) as error:
                await workflow.run({"name": "a"})
            assert error.value.code == "PERMISSION_DENIED"
            world.discovery.refuse = None
            assert await workflow.run({"name": "a"}) == {"echo": "a"}
            assert world.discovery.calls == 2
        finally:
            await world.close()

    run(scenario)


def test_concurrent_first_calls_with_one_token_ask_discovery_once(broker):
    async def scenario():
        world = await serve(broker)
        try:
            workflow = world.module().get_workflow("echo_workflow")
            await asyncio.gather(*(workflow.run({"name": "a"}) for _ in range(8)))
            assert world.discovery.calls == 1
        finally:
            await world.close()

    run(scenario)


def test_discovery_unreachable_is_unavailable_not_a_process_failure(broker):
    async def scenario():
        world = await serve(broker)
        try:

            async def down(*args, **kwargs):
                raise asyncio.TimeoutError()

            world.host.session.client._call = down
            with pytest.raises(RPCError) as error:
                await world.module().get_workflow("echo_workflow").run({"name": "a"})
            assert error.value.code == "UNAVAILABLE"
        finally:
            await world.close()

    run(scenario)


# -- lookup errors ----------------------------------------------------------------


def test_no_ready_instance_or_declaration(broker):
    async def scenario():
        world = await serve(broker)
        try:
            starting = world.module(status="STARTING").get_workflow("echo_workflow")
            with pytest.raises(RPCError) as error:
                await starting.run({"name": "a"})
            assert error.value.code == "MODULE_UNAVAILABLE"
            with pytest.raises(RPCError) as error:
                await world.module().get_workflow("nope")
            assert error.value.code == "PROCESS_NOT_FOUND"
            # A pipeline is not found under a workflow's name.
            with pytest.raises(RPCError) as error:
                await world.module().get_pipeline("echo_workflow")
            assert error.value.code == "PROCESS_NOT_FOUND"
            # Listed, but the instance is gone: nobody is subscribed.
            await world.host.close()
            with pytest.raises(RPCError) as error:
                await world.module().get_workflow("echo_workflow").run({"name": "a"})
            assert error.value.code == "MODULE_UNAVAILABLE"
        finally:
            await world.close()

    run(scenario)


def test_a_run_needs_a_dict_or_a_model_and_a_positive_deadline(broker):
    async def scenario():
        world = await serve(broker)
        try:
            workflow = world.module().get_workflow("echo_workflow")
            with pytest.raises(TypeError):
                await workflow.run("name")
            with pytest.raises(ValueError, match="JSON"):
                await workflow.run({"name": object()})
            for bad in (0, -1, float("nan"), float("inf")):
                with pytest.raises(ValueError, match="timeout"):
                    await workflow.run({"name": "a"}, timeout=bad)
        finally:
            await world.close()

    run(scenario)


# -- large payloads -----------------------------------------------------------------


def test_parameters_and_results_above_one_message_stream(broker):
    async def scenario():
        world = await serve(broker)
        try:
            module = world.module()
            # Parameters: 3 MiB in, above either broker's message size.
            assert await module.get_workflow("length_workflow").run(
                {"name": "n" * (3 * MB)}
            ) == {"length": 3 * MB}
            # A result of 5 MiB out, and one that fits.
            big = module.get_workflow("big_workflow")
            assert len((await big.run({"size": 5 * MB}))["data"]) == 5 * MB
            assert len((await big.run({"size": 10}))["data"]) == 10
            # A graph above the broker's message size.
            graph = await module.get_pipeline("load_pipeline").run({"count": 40_000})
            assert len(graph) == 40_000
            # The module is still serving.
            assert await module.get_workflow("echo_workflow").run({"name": "a"}) == {
                "echo": "a"
            }
        finally:
            await world.close()

    run(scenario)


def test_a_request_that_overflowed_is_refused(broker):
    """The engine's RPC overflow cannot carry a call to a module: it refuses a token
    bound to an instance. Such a request is answered with an error, not decoded."""
    from naas_abi_proto.process.v1 import process_pb2 as pb

    from naas_abi_sdk import overflow

    async def scenario():
        world = await serve(broker)
        try:
            nc = await world.host_transport.connect()
            reply = await nc.request(
                process_host.process_subject(
                    PROJECT, INSTANCE, "workflow", "echo_workflow", "run"
                ),
                b"",
                headers={
                    "Nats-Auth-Token": bound_token(INSTANCE),
                    overflow.REQUEST_HEADER: "0" * 32 + ":upload",
                },
                timeout=5,
            )
            assert (
                pb.RunResponse.FromString(reply.data).error.code == "PAYLOAD_TOO_LARGE"
            )
        finally:
            await world.close()

    run(scenario)


def test_a_body_inbox_that_is_not_an_inbox_is_refused(broker):
    from naas_abi_proto.process.v1 import process_pb2 as pb

    async def scenario():
        world = await serve(broker)
        try:
            module = world.module()
            transport = module.client.transport
            for inbox in ("abi.svc.keyvalue.v1.get", "_INBOX.>", "_INBOX_MODULES.a b"):
                with pytest.raises(RPCError) as error:
                    await transport.call(
                        process_host.process_subject(
                            PROJECT, INSTANCE, "workflow", "echo_workflow", "run"
                        ),
                        pb.RunRequest(
                            name="echo_workflow",
                            parameters_inbox=inbox,
                            parameters_bytes=10,
                        ),
                        pb.RunResponse,
                        instance_id=INSTANCE,
                    )
                assert error.value.code == "INVALID_ARGUMENT"
            assert EchoWorkflow.runs == 0
        finally:
            await world.close()

    run(scenario)


# -- deadlines --------------------------------------------------------------------


def test_a_run_is_cancelled_at_the_callers_deadline(broker):
    async def scenario():
        world = await serve(broker)
        try:
            workflow = world.module().get_workflow("sleep_workflow")
            started = time.monotonic()
            with pytest.raises(RPCError) as error:
                await workflow.run({"seconds": 30}, timeout=0.5)
            assert error.value.code == "DEADLINE_EXCEEDED"
            assert time.monotonic() - started < 5
            assert SleepWorkflow.cancelled  # the module stopped it, not just the caller
            assert await workflow.run({"seconds": 0}) == {"slept": 0.0}
        finally:
            await world.close()

    run(scenario)


def test_the_default_deadline_is_300_seconds(broker, monkeypatch):
    async def scenario():
        world = await serve(broker)
        seen = []
        original = process_host._within

        async def spy(coroutine, seconds, message):
            seen.append(seconds)
            return await original(coroutine, seconds, message)

        monkeypatch.setattr(process_host, "_within", spy)
        try:
            await world.module().get_workflow("echo_workflow").run({"name": "a"})
            assert 299 < seen[0] <= 300
            await (
                world.module()
                .get_workflow("echo_workflow")
                .run({"name": "a"}, timeout=42)
            )
            assert 41 < seen[1] <= 42
        finally:
            await world.close()

    run(scenario)


def test_a_timeout_the_process_raises_is_its_own_failure_not_the_deadline(broker):
    class Leaky(Workflow[WorkflowParameters]):
        async def run(self, parameters: WorkflowParameters):
            await asyncio.wait_for(asyncio.sleep(30), 0.05)

    async def scenario():
        world = await serve(broker, workflows={"leaky": Leaky}, pipelines={})
        try:
            with pytest.raises(RPCError) as error:
                await world.module().get_workflow("leaky").run({})
            assert error.value.code == "PROCESS_ERROR"
        finally:
            await world.close()

    run(scenario)


# -- concurrency and shutdown ---------------------------------------------------------


def test_runs_go_side_by_side_up_to_the_limit(broker):
    async def scenario():
        world = await serve(broker, max_concurrency=2)
        try:
            workflow = world.module().get_workflow("sleep_workflow")
            await asyncio.gather(*(workflow.run({"seconds": 0.2}) for _ in range(5)))
            assert SleepWorkflow.peak == 2
            # Describing never waits behind running calls.
            running = [
                asyncio.create_task(workflow.run({"seconds": 1})) for _ in range(2)
            ]
            await asyncio.sleep(0.3)
            started = time.monotonic()
            await workflow.describe()
            assert time.monotonic() - started < 0.5
            await asyncio.gather(*running)
        finally:
            await world.close()

    run(scenario)


def test_a_drain_finishes_the_runs_in_progress_and_takes_no_new_ones(broker):
    async def scenario():
        world = await serve(broker)
        try:
            module = world.module()
            workflow = module.get_workflow("sleep_workflow")
            await module.get_workflow("echo_workflow").run({"name": "warm"})
            inflight = asyncio.create_task(workflow.run({"seconds": 0.8}))
            big = asyncio.create_task(
                module.get_workflow("big_workflow").run({"size": 4 * MB})
            )
            await asyncio.sleep(0.3)
            assert SleepWorkflow.running == 1
            started = time.monotonic()
            await world.host.drain(10)
            # The drain waited for the run, which finished instead of being cut off.
            assert time.monotonic() - started >= 0.3
            assert await inflight == {"slept": 0.8}
            assert len((await big)["data"]) == 4 * MB
            assert not SleepWorkflow.cancelled
            # Nobody answers any more.
            with pytest.raises(RPCError) as error:
                await module.get_workflow("echo_workflow").run({"name": "late"})
            assert error.value.code == "MODULE_UNAVAILABLE"
        finally:
            await world.close()

    run(scenario)


def test_a_drain_gives_up_at_its_timeout_and_close_tells_the_caller(broker):
    async def scenario():
        world = await serve(broker)
        try:
            workflow = world.module().get_workflow("sleep_workflow")
            inflight = asyncio.create_task(workflow.run({"seconds": 30}))
            await asyncio.sleep(0.3)
            await world.host.drain(0.3)
            assert not inflight.done()
            await world.host.close()
            with pytest.raises(RPCError) as error:
                await asyncio.wait_for(inflight, 5)
            assert error.value.code == "CANCELLED"
            assert SleepWorkflow.cancelled
        finally:
            await world.close()

    run(scenario)


def test_a_closing_host_refuses_what_reaches_it(broker):
    async def scenario():
        world = await serve(broker)
        try:
            world.host.closing = True
            with pytest.raises(RPCError) as error:
                await world.module().get_workflow("echo_workflow").run({"name": "a"})
            assert error.value.code == "MODULE_UNAVAILABLE"
            with pytest.raises(RPCError) as error:
                await world.module().get_workflow("echo_workflow").describe()
            assert error.value.code == "MODULE_UNAVAILABLE"
            assert EchoWorkflow.runs == 0
        finally:
            await world.close()

    run(scenario)


# -- tools ------------------------------------------------------------------------


def test_remote_processes_are_agent_tools(broker):
    pytest.importorskip("langchain_core")

    async def scenario():
        world = await serve(broker)
        try:
            module = world.module()
            # The schema comes with the first await.
            with pytest.raises(RuntimeError, match="not loaded"):
                module.get_workflow("echo_workflow").as_tools()
            workflow = await module.get_workflow("echo_workflow")
            (tool,) = workflow.as_tools()
            assert tool.name == "echo_workflow"
            assert tool.description == "Repeats a name."
            assert set(tool.args_schema["properties"]) == {"name", "times"}
            assert await tool.ainvoke({"name": "ab", "times": 2}) == {"echo": "abab"}
            # Called from a thread, as a synchronous agent graph does.
            assert await asyncio.to_thread(tool.invoke, {"name": "c"}) == {"echo": "c"}
            (pipeline_tool,) = (await module.get_pipeline("load_pipeline")).as_tools()
            result = await pipeline_tool.ainvoke({"count": 2})
            assert result["format"] == "turtle"
            assert len(Graph().parse(data=result["data"], format="turtle")) == 2
            # A refused call raises, for the agent to see.
            with pytest.raises(RPCError, match="INVALID_ARGUMENT"):
                await tool.ainvoke({"times": 2})
        finally:
            await world.close()

    run(scenario)


def test_the_discovery_calls_name_the_instance_kind_and_process(broker):
    async def scenario():
        world = await serve(broker)
        seen = []
        original = world.host.session.client._call

        async def spy(operation, request, response_type):
            seen.append(request)
            return await original(operation, request, response_type)

        world.host.session.client._call = spy
        try:
            await world.module().get_pipeline("load_pipeline").run({})
            (request,) = seen
            assert isinstance(request, discovery_pb.AuthorizeProcessRequest)
            assert (
                request.instance_id,
                request.process_kind,
                request.process_name,
                request.lease_token,
            ) == (INSTANCE, "pipeline", "load_pipeline", "l" * 32)
            assert request.caller_token  # the caller's, bound to the instance
        finally:
            await world.close()

    run(scenario)
