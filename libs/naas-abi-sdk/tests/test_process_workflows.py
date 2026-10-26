"""Workflow and Pipeline classes as durable workflows: descriptors, inputs, results
and clashes (extras: workflows, rdf, agents for ``as_tools``).

No broker: the host's own behaviour is in ``test_jobs_integration.py`` and
``test_workflows_integration.py``.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import timedelta
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import MagicMock

import pytest

pytest.importorskip("pydantic")
pytest.importorskip("rdflib")

from pydantic import BaseModel
from rdflib import Graph, Literal, URIRef

from naas_abi_sdk.discovery import DiscoveryConfiguration, module_descriptor
from naas_abi_sdk.jobs import (
    Cron,
    Every,
    JobDescriptor,
    JobSettings,
    OnEvent,
    job,
    process_workflow_name,
)
from naas_abi_sdk.module import BaseModule, ModuleDependencies, run_module
from naas_abi_sdk.pipeline import Pipeline, PipelineParameters
from naas_abi_sdk.process_workflows import (
    GRAPH_OUTPUT_SCHEMA,
    MAX_DESCRIPTION_BYTES,
    encode_process_result,
)
from naas_abi_sdk.workflow import Workflow, WorkflowParameters
from naas_abi_sdk.workflows import InvalidWorkflowInput, WorkflowProxy, workflow

JOB_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,255}")


class GreetParameters(WorkflowParameters):
    name: str
    times: int = 1


class Greeting(BaseModel):
    message: str


class GreetWorkflow(Workflow[GreetParameters]):
    """Greets someone.

    A second line, kept in the description.
    """

    job = JobSettings(
        triggers=(OnEvent(subject="greet.requested"),),
        timeout=timedelta(minutes=5),
        max_attempts=3,
        max_concurrency=4,
    )

    async def run(self, parameters: GreetParameters) -> Greeting:
        return Greeting(message=parameters.name * parameters.times)


class IngestParameters(PipelineParameters):
    count: int = 2


class IngestPipeline(Pipeline[IngestParameters]):
    """Loads triples."""

    job = JobSettings(triggers=(Every("1h"),))

    async def run(self, parameters: IngestParameters) -> Graph:
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


class PlainWorkflow(Workflow[WorkflowParameters]):
    """Declares no job."""

    async def run(self, parameters: WorkflowParameters):
        return {"ok": True}


def module_of(*, workflows=(), pipelines=(), **attributes) -> type[BaseModule]:
    return type(
        "ABIModule",
        (BaseModule,),
        {
            "module_id": "acme.flows",
            "workflows": tuple(workflows),
            "pipelines": tuple(pipelines),
            **attributes,
        },
    )


def declared(module_type: type[BaseModule], *, build=True) -> BaseModule:
    """A module as ``run_module`` has it once the jobs go to the host."""
    module = module_type(MagicMock(), module_type.Configuration())
    module.declare_process_workflows()
    if build:
        asyncio.run(module.build_processes())
    return module


def jobs_of(module: BaseModule) -> dict[str, JobDescriptor]:
    return {j.name: j for j in module.jobs}


# --- descriptors ------------------------------------------------------------------


def test_every_class_is_a_workflow_named_after_its_kind_and_slug():
    module = declared(
        module_of(
            workflows=(GreetWorkflow, PlainWorkflow), pipelines=(IngestPipeline,)
        ),
        build=False,
    )

    jobs = jobs_of(module)

    assert sorted(jobs) == [
        "pipeline.ingest_pipeline",
        "workflow.greet_workflow",
        "workflow.plain_workflow",
    ]
    assert all(JOB_NAME.fullmatch(name) for name in jobs)
    assert all(j.kind == "workflow" for j in jobs.values())
    assert (
        process_workflow_name("pipeline", "ingest_pipeline")
        == "pipeline.ingest_pipeline"
    )


def test_the_input_schema_is_the_parameters_model_and_the_output_follows_run():
    jobs = jobs_of(
        declared(
            module_of(
                workflows=(GreetWorkflow, PlainWorkflow), pipelines=(IngestPipeline,)
            ),
            build=False,
        )
    )

    greet = jobs["workflow.greet_workflow"]
    assert json.loads(greet.input_schema) == json.loads(
        json.dumps(GreetParameters.model_json_schema(), sort_keys=True)
    )
    # A model, or the marker of a result too large for a run record.
    assert json.loads(greet.output_schema)["anyOf"][0]["title"] == "Greeting"
    assert (
        json.loads(jobs["pipeline.ingest_pipeline"].output_schema)
        == GRAPH_OUTPUT_SCHEMA
    )
    # No annotation: anything JSON.
    assert "type" not in json.loads(jobs["workflow.plain_workflow"].output_schema)


def test_job_settings_give_the_triggers_and_limits_and_their_absence_the_defaults():
    jobs = jobs_of(
        declared(
            module_of(
                workflows=(GreetWorkflow, PlainWorkflow), pipelines=(IngestPipeline,)
            ),
            build=False,
        )
    )

    greet = jobs["workflow.greet_workflow"]
    assert greet.triggers == (OnEvent(subject="greet.requested"),)
    assert (greet.max_attempts, greet.max_concurrency) == (3, 4)
    assert greet.timeout == timedelta(minutes=5)
    assert greet.description.startswith("Greets someone.\n\nA second line")
    assert jobs["pipeline.ingest_pipeline"].triggers == (Every("1h"),)
    plain = jobs["workflow.plain_workflow"]
    assert plain.triggers == () and plain.timeout is None
    assert (plain.max_attempts, plain.max_concurrency) == (1, 1)


def test_a_blank_docstring_is_the_slug_and_a_long_one_is_cut_in_bytes():
    class BlankWorkflow(Workflow[WorkflowParameters]):
        """ """  # noqa: D419

    class LongWorkflow(Workflow[WorkflowParameters]):
        pass

    LongWorkflow.__doc__ = "日本語" * 600

    jobs = jobs_of(
        declared(module_of(workflows=(BlankWorkflow, LongWorkflow)), build=False)
    )

    assert jobs["workflow.blank_workflow"].description == "blank_workflow"
    long = jobs["workflow.long_workflow"].description
    assert len(long.encode()) <= MAX_DESCRIPTION_BYTES and long.endswith("…")


def test_the_registered_descriptor_holds_them_once_declared():
    module_type = module_of(pipelines=(IngestPipeline,))
    module = declared(module_type, build=False)

    assert module_descriptor(module_type, "acme.flows", ()).jobs == []
    descriptor = module_descriptor(module, "acme.flows", ())
    assert [JobDescriptor.from_pb(j) for j in descriptor.jobs] == list(module.jobs)


def test_explicit_jobs_and_workflows_stay_beside_them():
    class Explicit(BaseModule):
        module_id = "acme.explicit"
        workflows = (PlainWorkflow,)
        jobs = (JobDescriptor("nightly"),)

        @job(triggers=(Every("1m"),))
        async def tick(self, ctx):
            return None

        @workflow()
        async def report(self, ctx, inp: dict) -> dict:
            return {}

    module = declared(Explicit)

    assert [j.name for j in module.jobs] == [
        "nightly",
        "tick",
        "report",
        "workflow.plain_workflow",
    ]
    assert module.missing_job_handlers() == {"nightly"}


def test_job_settings_are_checked_where_they_are_declared():
    with pytest.raises(ValueError, match="max_attempts"):
        JobSettings(max_attempts=0)
    with pytest.raises(ValueError, match="max_concurrency"):
        JobSettings(max_concurrency=65)
    with pytest.raises(ValueError, match="timeout"):
        JobSettings(timeout=timedelta(0))
    with pytest.raises(ValueError, match="triggers"):
        JobSettings(triggers=tuple(Every("1h") for _ in range(17)))


def test_job_that_is_not_job_settings_is_refused():
    class Odd(Workflow[WorkflowParameters]):
        job: ClassVar[dict] = {"triggers": ()}

        async def run(self, parameters):
            return {}

    with pytest.raises(TypeError, match=r"Odd\.job must be a JobSettings"):
        declared(module_of(workflows=(Odd,)), build=False)


# --- clashes and schedules ----------------------------------------------------------


def test_run_module_fails_before_it_connects_on_a_clash(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr("naas_abi_sdk.module.ABIClient", client)
    module_type = module_of(
        workflows=(PlainWorkflow,),
        jobs=(JobDescriptor("workflow.plain_workflow"),),
        dependencies=ModuleDependencies(services=("document",)),
    )

    with pytest.raises(ValueError, match=r"workflow\.plain_workflow.*rename"):
        asyncio.run(
            run_module(
                module_type,
                url="nats://unused",
                token="t",
                discovery=DiscoveryConfiguration(project="p"),
            )
        )
    client.assert_not_called()


def test_a_name_an_explicit_job_has_fails():
    module_type = module_of(
        workflows=(PlainWorkflow,), jobs=(JobDescriptor("workflow.plain_workflow"),)
    )

    with pytest.raises(
        ValueError, match=r"Duplicate job names.*workflow\.plain_workflow"
    ):
        declared(module_type, build=False)


def test_a_decorated_job_with_that_name_fails_too():
    class Clash(BaseModule):
        module_id = "acme.clash"
        workflows = (PlainWorkflow,)

        @job("workflow.plain_workflow")
        async def explicit(self, ctx):
            return None

    with pytest.raises(ValueError, match=r"workflow\.plain_workflow"):
        declared(Clash, build=False)


class NeedsParameters(WorkflowParameters):
    since: str


@pytest.mark.parametrize("trigger", [Cron("0 0 6 * * *"), Every("1h")])
def test_a_schedule_whose_input_does_not_fit_the_parameters_fails_at_start(
    trigger, monkeypatch
):
    class Scheduled(Workflow[NeedsParameters]):
        job = JobSettings(triggers=(trigger,))

        async def run(self, parameters: NeedsParameters):
            return {}

    client = MagicMock()
    monkeypatch.setattr("naas_abi_sdk.module.ABIClient", client)

    with pytest.raises(ValueError, match=r"'scheduled'.*since.*input="):
        asyncio.run(
            run_module(
                module_of(
                    workflows=(Scheduled,),
                    dependencies=ModuleDependencies(services=("document",)),
                ),
                url="nats://unused",
                token="t",
                discovery=DiscoveryConfiguration(project="p"),
            )
        )
    client.assert_not_called()


def test_a_schedule_input_that_fits_and_events_and_manual_runs_are_fine():
    from naas_abi_sdk.process_workflows import check_classes

    class WithInput(Workflow[NeedsParameters]):
        job = JobSettings(triggers=(Cron("0 0 6 * * *", input={"since": "2026"}),))

    class Event(Workflow[NeedsParameters]):
        job = JobSettings(triggers=(OnEvent(subject="x.y"),))

    class Manual(Workflow[NeedsParameters]):
        pass

    check_classes(
        {
            "workflow": {"a": WithInput, "b": Event, "c": Manual},
            "pipeline": {"d": IngestPipeline},  # count has a default
        }
    )


@pytest.mark.parametrize(
    "options, services",
    [({}, ("document",)), ({"discovery": DiscoveryConfiguration(project="p")}, ())],
)
def test_run_module_needs_discovery_and_the_document_service_before_it_connects(
    options, services, monkeypatch
):
    client = MagicMock()
    monkeypatch.setattr("naas_abi_sdk.module.ABIClient", client)
    module_type = module_of(
        workflows=(PlainWorkflow,),
        dependencies=ModuleDependencies(services=services),
    )

    with pytest.raises(ValueError, match="discovery.*document service"):
        asyncio.run(run_module(module_type, url="nats://unused", token="t", **options))

    client.assert_not_called()


# --- the handler ------------------------------------------------------------------


class InlineFlow:
    """Stands in for ``FlowContext``: the step runs once and nothing is journaled
    (the SDK's workflow tests cover the journal)."""

    def __init__(self, payload, kind="manual"):
        self.payload, self.trigger, self.skipped = payload, {"kind": kind}, None
        self.keys: list[str] = []

    async def step(self, key, fn, *args, **kwargs):
        self.keys.append(key)
        return await fn(*args, **kwargs)


def run_handler(module: BaseModule, name: str, payload, kind="manual"):
    flow = InlineFlow(payload, kind)
    return asyncio.run(module._job_handlers[name](flow)), flow


def test_a_workflow_run_validates_its_input_and_returns_its_json_in_one_step():
    module = declared(module_of(workflows=(GreetWorkflow,)))

    output, flow = run_handler(
        module, "workflow.greet_workflow", {"name": "ab", "times": 2}
    )

    assert output == {"message": "abab"} and flow.keys == ["run"]


def test_a_pipeline_run_returns_its_graph_as_turtle_with_a_triple_count():
    module = declared(module_of(pipelines=(IngestPipeline,)))

    output, _ = run_handler(module, "pipeline.ingest_pipeline", {})

    assert output["format"] == "text/turtle" and output["triples"] == 2
    assert len(Graph().parse(data=output["data"], format="turtle")) == 2


def test_an_input_the_model_refuses_fails_without_retry_naming_fields_not_values():
    ran = []

    class Counting(Workflow[GreetParameters]):
        async def run(self, parameters):
            ran.append(parameters)
            return {}

    module = declared(module_of(workflows=(Counting,)))

    with pytest.raises(InvalidWorkflowInput) as raised:
        run_handler(module, "workflow.counting", {"times": "secret-value"})

    assert "name" in str(raised.value) and "times" in str(raised.value)
    assert "secret-value" not in str(raised.value)
    assert ran == []


def test_an_event_run_takes_the_events_data_as_its_parameters():
    module = declared(module_of(workflows=(GreetWorkflow,)))
    name = "workflow.greet_workflow"

    event = {"subject": "greet.requested", "data": {"name": "Eve"}}
    assert run_handler(module, name, event, "event")[0] == {"message": "Eve"}
    with pytest.raises(InvalidWorkflowInput, match="name"):
        run_handler(module, name, {"subject": "s", "data": None}, "event")


def test_the_instance_bound_with_expose_workflow_is_the_one_that_runs():
    module = module_of(workflows=(GreetWorkflow,))(
        MagicMock(), BaseModule.Configuration()
    )
    module.declare_process_workflows()
    bound = GreetWorkflow(None)
    module.expose_workflow("greet_workflow", bound)
    asyncio.run(module.build_processes())

    output, _ = run_handler(module, "workflow.greet_workflow", {"name": "Ada"})

    assert output == {"message": "Ada"}
    assert module.get_workflow_instance("greet_workflow") is bound


def test_the_processs_own_error_reaches_the_run_unchanged():
    class Broken(Workflow[WorkflowParameters]):
        async def run(self, parameters):
            raise KeyError("boom")

    with pytest.raises(KeyError):
        run_handler(declared(module_of(workflows=(Broken,))), "workflow.broken", {})


def test_results_are_json_as_core_encodes_them_and_too_large_ones_are_omitted():
    from datetime import datetime, timezone
    from decimal import Decimal
    from uuid import UUID

    class Item(BaseModel):
        at: datetime
        id: UUID
        price: Decimal

    item = Item(
        at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        id=UUID(int=1),
        price=Decimal("2.5"),
    )
    # The REST route's conversions (FastAPI's jsonable_encoder), as core's bridge.
    assert encode_process_result({"items": [item]}) == {
        "items": [
            {"at": "2026-01-02T00:00:00+00:00", "id": str(UUID(int=1)), "price": 2.5}
        ]
    }
    omitted = encode_process_result({"blob": "x" * 100}, max_bytes=50)
    assert omitted["omitted"] is True and omitted["limit"] == 50
    graph = IngestPipeline(None)
    big = encode_process_result(asyncio.run(graph.run(IngestParameters(count=50))), 100)
    assert big["triples"] == 50 and "data" not in big and "note" in big


def test_nan_and_infinity_are_null_so_the_step_journal_takes_them():
    encoded = encode_process_result({"s": float("nan"), "t": [float("inf")], "u": 1.5})

    assert encoded == {"s": None, "t": [None], "u": 1.5}
    json.dumps(encoded, allow_nan=False)  # what the step journal requires


def test_a_result_that_cannot_be_encoded_never_fails_after_run_did_its_work():
    class Opaque:
        def __repr__(self):
            return "<opaque>"

    encoded = encode_process_result(
        {"leaf": Opaque(), "raw": b"\xff\xfe ok", "kind": object}
    )
    assert encoded["leaf"] == "<opaque>" and encoded["raw"].endswith(" ok")
    assert isinstance(encoded["kind"], str)
    assert encode_process_result(b"\xffdata") == {"data": "\ufffddata"}
    loop: list = []
    loop.append(loop)
    assert encode_process_result(loop)["repr"].startswith("[")
    json.dumps(encoded, allow_nan=False)


def test_a_pipeline_returning_nan_succeeds_through_its_handler():
    class Scored(Workflow[WorkflowParameters]):
        async def run(self, parameters):
            return {"score": float("nan")}

    output, _ = run_handler(
        declared(module_of(workflows=(Scored,))), "workflow.scored", {}
    )

    assert output == {"score": None}


# --- calling it from another module ---------------------------------------------------


def test_a_proxy_gives_an_agent_one_tool_that_runs_the_workflow():
    pytest.importorskip("langchain_core")
    module = declared(module_of(workflows=(GreetWorkflow,)), build=False)
    proxy = WorkflowProxy(
        None, "p", "acme.flows", jobs_of(module)["workflow.greet_workflow"]
    )
    calls = []

    async def run(input=None, *, timeout=None):
        calls.append(input)
        return Greeting(message="hi")

    proxy.run = run

    async def scenario():
        (tool,) = proxy.as_tools()
        return tool, await tool.ainvoke({"name": "Ada"})

    tool, output = asyncio.run(scenario())

    assert tool.name == "greet_workflow"
    assert tool.description.startswith("Greets someone.")
    assert set(tool.args) == {"name", "times"}
    assert calls == [{"name": "Ada"}] and output == {"message": "hi"}


def test_a_proxy_tool_called_from_another_thread_runs_on_the_module_loop():
    pytest.importorskip("langchain_core")
    proxy = WorkflowProxy(None, "p", "m", JobDescriptor("flow", kind="workflow"))
    seen = SimpleNamespace(loop=None)

    async def run(input=None, *, timeout=None):
        seen.loop = asyncio.get_running_loop()
        return {"ok": True}

    proxy.run = run

    async def scenario():
        (tool,) = proxy.as_tools()
        result = await asyncio.to_thread(tool.invoke, {})
        return result, asyncio.get_running_loop()

    result, loop = asyncio.run(scenario())

    assert result == {"ok": True} and seen.loop is loop
