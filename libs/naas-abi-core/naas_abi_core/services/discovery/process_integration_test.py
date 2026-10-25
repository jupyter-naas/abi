"""Remote workflows and pipelines over NATS, end to end.

A real broker, the real discovery service, and SDK modules as they run in a project:
module ``a`` serves a workflow and a pipeline, module ``b`` (which depends on ``a``)
calls them, directly and as agent tools. Then a caller that is not ``b`` pushes on the
edges: tokens not bound to the instance, payloads above the broker's message size,
deadlines, and a SIGTERM while runs are in flight.

Requires ``nats-server``; ``ABI_REQUIRE_NATS_SERVER=1`` makes a missing one a failure.
"""

import asyncio
import os
import signal
import threading

import nats
import pytest
from naas_abi_core.engine.nats_auth import issue_service_token, module_key
from naas_abi_core.engine.nats_rpc_integration_test import SECRET, broker  # noqa: F401
from naas_abi_core.services.discovery.discovery_factory import start_discovery
from naas_abi_proto.process.v1 import process_pb2 as pb

pytestmark = [
    pytest.mark.integration,
    # Smaller than the 5 MiB payloads below, so they cannot travel in one message.
    pytest.mark.parametrize("broker", [1024 * 1024], indirect=True),
]

pytest.importorskip("pydantic")
pytest.importorskip("rdflib")
pytest.importorskip("langchain_core")

from naas_abi_sdk.discovery import (
    DiscoveryClient,
    DiscoveryConfiguration,
    ModuleProxy,
)
from naas_abi_sdk.module import BaseModule, ModuleDependencies, run_module
from naas_abi_sdk.pipeline import Pipeline, PipelineParameters
from naas_abi_sdk.process_host import process_subject
from naas_abi_sdk.service_token import ModuleToken
from naas_abi_sdk.transport import RPCError, Transport
from naas_abi_sdk.workflow import Workflow, WorkflowParameters
from rdflib import Graph, Literal, URIRef

MB = 1024 * 1024


def _module_token(module_id: str) -> ModuleToken:
    return ModuleToken(module_id, module_key(SECRET, module_id))


class Counted:
    runs = 0


class EchoParameters(WorkflowParameters):
    name: str


class EchoWorkflow(Workflow[EchoParameters]):
    """Greets by name."""

    async def run(self, parameters: EchoParameters):
        Counted.runs += 1
        return {"message": f"Hello, {parameters.name}!"}


class SleepParameters(WorkflowParameters):
    seconds: float


class SleepWorkflow(Workflow[SleepParameters]):
    """Waits, then says so."""

    running = 0
    cancelled = False

    async def run(self, parameters: SleepParameters):
        type(self).running += 1
        try:
            await asyncio.sleep(parameters.seconds)
            return {"slept": parameters.seconds}
        except asyncio.CancelledError:
            type(self).cancelled = True
            raise
        finally:
            type(self).running -= 1


class SizeParameters(WorkflowParameters):
    size: int


class BigWorkflow(Workflow[SizeParameters]):
    """Answers a result of the size asked."""

    async def run(self, parameters: SizeParameters):
        return {"data": "x" * parameters.size}


class LengthWorkflow(Workflow[EchoParameters]):
    """Measures its input."""

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
                    Literal(f"value {index}"),
                )
            )
        return graph


def _config() -> DiscoveryConfiguration:
    return DiscoveryConfiguration(startup_timeout=10, refresh_seconds=0.05)


def test_a_module_calls_another_modules_workflow_and_pipeline_over_nats(broker):  # noqa: F811
    started = asyncio.Event()
    # B runs in a thread of its own, on its own loop, as another process would: a
    # SIGTERM then reaches A's handler alone (a loop has one handler per signal).
    release_b, b_done = threading.Event(), threading.Event()
    from_b: dict = {}

    class A(BaseModule):
        module_id = "a"
        workflows = (EchoWorkflow, SleepWorkflow, BigWorkflow, LengthWorkflow)
        pipelines = (LoadPipeline,)

        async def run(self):
            started.set()
            await asyncio.Event().wait()

    class B(BaseModule):
        module_id = "b"
        dependencies = ModuleDependencies(modules=("a",))

        async def run(self):
            a = self.engine.modules["a"]
            from_b["workflow"] = await a.get_workflow("echo_workflow").run(
                {"name": "Ada"}
            )
            from_b["graph"] = await a.get_pipeline("load_pipeline").run({"count": 2})
            # What its agent does: the tools of the proxies, named as the process.
            tools = [
                *(await a.get_workflow("echo_workflow")).as_tools(),
                *(await a.get_pipeline("load_pipeline")).as_tools(),
            ]
            from_b["tools"] = {tool.name: tool.description for tool in tools}
            calls = [
                {
                    "name": tool.name,
                    "args": args,
                    "id": f"call-{tool.name}",
                    "type": "tool_call",
                }
                for tool, args in zip(tools, ({"name": "Grace"}, {"count": 1}))
            ]
            from_b["tool_messages"] = [
                await tool.ainvoke(call) for tool, call in zip(tools, calls)
            ]
            b_done.set()
            await asyncio.to_thread(release_b.wait)

    async def scenario():
        url, _ = broker
        nc = await nats.connect(url)
        primary = await start_discovery(nc, SECRET, lease_seconds=3)
        config = _config()
        # B first: it waits for A, as a dependent module does.
        b_task = asyncio.create_task(
            asyncio.to_thread(
                lambda: asyncio.run(
                    run_module(
                        B,
                        url=url,
                        token=_module_token("b"),
                        timeout=5,
                        discovery=config,
                    )
                )
            )
        )
        await asyncio.sleep(0.2)
        assert not b_done.is_set()
        a_task = asyncio.create_task(
            run_module(
                A, url=url, token=_module_token("a"), timeout=5, discovery=config
            )
        )
        tester = Transport(url, _module_token("tester"), timeout=5)
        client = DiscoveryClient(tester)
        try:
            await asyncio.wait_for(started.wait(), 15)
            await asyncio.wait_for(asyncio.to_thread(b_done.wait, 15), 20)
            assert b_done.is_set()

            assert from_b["workflow"] == {"message": "Hello, Ada!"}
            assert isinstance(from_b["graph"], Graph) and len(from_b["graph"]) == 2
            assert from_b["tools"] == {
                "echo_workflow": "Greets by name.",
                "load_pipeline": "Loads triples.",
            }
            workflow_message, pipeline_message = from_b["tool_messages"]
            assert "Hello, Grace!" in workflow_message.content
            assert "turtle" in pipeline_message.content

            # The registry shows what A declares.
            (instance,) = await client.get_module("a")
            assert {(p.kind, p.name) for p in instance.processes} == {
                ("workflow", "echo_workflow"),
                ("workflow", "sleep_workflow"),
                ("workflow", "big_workflow"),
                ("workflow", "length_workflow"),
                ("pipeline", "load_pipeline"),
            }
            a = ModuleProxy(client, "a")

            # -- unauthorized callers are refused before the handler runs ------
            runs = Counted.runs
            nc_peer = await nats.connect(url)
            try:
                request = pb.RunRequest(
                    name="echo_workflow", parameters_json=b'{"name": "x"}'
                ).SerializeToString()
                subject = process_subject(
                    "default", instance.instance_id, "workflow", "echo_workflow", "run"
                )
                for token in (
                    issue_service_token("stranger", SECRET),  # bound to nothing
                    issue_service_token(
                        "stranger", SECRET, audience="another-instance"
                    ),
                    "not-a-token",
                    "",
                ):
                    reply = await nc_peer.request(
                        subject, request, headers={"Nats-Auth-Token": token}, timeout=5
                    )
                    assert (
                        pb.RunResponse.FromString(reply.data).error.code
                        == "UNAUTHENTICATED"
                    )
                # The token bound to this instance, from a caller that is not B, works.
                bound = _module_token("stranger").for_audience(instance.instance_id)
                reply = await nc_peer.request(
                    subject, request, headers={"Nats-Auth-Token": bound}, timeout=5
                )
                assert pb.RunResponse.FromString(reply.data).result_json
            finally:
                await nc_peer.close()
            assert Counted.runs == runs + 1  # only the authorized call ran

            # -- an undeclared process: nothing serves it ---------------------
            with pytest.raises(RPCError) as error:
                await a.get_workflow("not_declared")
            assert error.value.code == "PROCESS_NOT_FOUND"
            with pytest.raises(RPCError) as error:  # a workflow's name is no pipeline's
                await a.get_pipeline("echo_workflow")
            assert error.value.code == "PROCESS_NOT_FOUND"

            # -- invalid parameters --------------------------------------------
            with pytest.raises(RPCError) as error:
                await a.get_workflow("echo_workflow").run({"nom": "Ada"})
            assert error.value.code == "INVALID_ARGUMENT"

            # -- payloads above the broker's message size ------------------
            assert await a.get_workflow("length_workflow").run(
                {"name": "n" * (5 * MB)}
            ) == {"length": 5 * MB}
            big = await a.get_workflow("big_workflow").run({"size": 5 * MB})
            assert len(big["data"]) == 5 * MB
            graph = await a.get_pipeline("load_pipeline").run({"count": 30_000})
            assert len(graph) == 30_000

            # -- the caller's deadline ----------------------------------------
            with pytest.raises(RPCError) as error:
                await a.get_workflow("sleep_workflow").run({"seconds": 60}, timeout=0.5)
            assert error.value.code == "DEADLINE_EXCEEDED"
            assert SleepWorkflow.cancelled
            assert SleepWorkflow.running == 0

            # -- SIGTERM finishes the runs in flight before A unregisters -----------
            loop = asyncio.get_running_loop()
            assert signal.SIGTERM in loop._signal_handlers  # A's: B has no handler here
            slow = asyncio.create_task(
                a.get_workflow("sleep_workflow").run({"seconds": 1.5})
            )
            big_result = asyncio.create_task(
                a.get_workflow("big_workflow").run({"size": 4 * MB})
            )
            while SleepWorkflow.running < 1:
                await asyncio.sleep(0.02)
            SleepWorkflow.cancelled = False  # the deadline above cut one run off
            os.kill(os.getpid(), signal.SIGTERM)

            async def status():
                try:
                    return (await client.get_module("a"))[0].status
                except RPCError as exc:
                    return exc.code

            deadline = loop.time() + 10
            while await status() != "DRAINING":
                assert loop.time() < deadline, "A never reported DRAINING"
                await asyncio.sleep(0.05)
            assert not slow.done()  # A is draining, and the run is still going
            # New calls find A unavailable.
            with pytest.raises(RPCError) as error:
                await a.get_workflow("echo_workflow").run({"name": "late"})
            assert error.value.code == "MODULE_UNAVAILABLE"
            # The run finished instead of being cut off, then A left.
            assert await slow == {"slept": 1.5}
            assert len((await big_result)["data"]) == 4 * MB
            assert not SleepWorkflow.cancelled
            assert await asyncio.wait_for(a_task, 15) is None
            with pytest.raises(RPCError) as error:
                await client.get_module("a")
            assert error.value.code == "MODULE_NOT_FOUND"
        finally:
            release_b.set()
            if not a_task.done():
                a_task.cancel()
            await asyncio.gather(a_task, return_exceptions=True)
            # B ends on its own once released (its thread cannot be cancelled).
            await asyncio.wait_for(asyncio.gather(b_task, return_exceptions=True), 30)
            await tester.close()
            await primary.stop()
            await nc.close()

    SleepWorkflow.cancelled = False
    Counted.runs = 0
    asyncio.run(asyncio.wait_for(scenario(), 120))
