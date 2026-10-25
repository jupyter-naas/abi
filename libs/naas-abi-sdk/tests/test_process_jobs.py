"""Workflows and pipelines as jobs: descriptors, payloads and clashes (extras: workflows, rdf).

No broker: the job host's own behaviour is in ``test_jobs_integration.py``.
"""

from __future__ import annotations

import asyncio
import re
from datetime import timedelta
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("pydantic")
pytest.importorskip("rdflib")

from rdflib import Graph, Literal, URIRef

from naas_abi_sdk.discovery import module_descriptor
from naas_abi_sdk.jobs import (
    Cron,
    Every,
    JobContext,
    JobDescriptor,
    JobRun,
    JobSettings,
    OnEvent,
    job,
    process_job_name,
)
from naas_abi_sdk.module import BaseModule, run_module
from naas_abi_sdk.pipeline import Pipeline, PipelineParameters
from naas_abi_sdk.process_jobs import process_job_handler
from naas_abi_sdk.process_proxy import ProcessProxy
from naas_abi_sdk.transport import RPCError
from naas_abi_sdk.workflow import Workflow, WorkflowParameters

JOB_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,255}")


class GreetParameters(WorkflowParameters):
    name: str
    times: int = 1


class GreetWorkflow(Workflow[GreetParameters]):
    """Greets someone.

    A second line the job's description leaves out.
    """

    job = JobSettings(
        triggers=(OnEvent(subject="greet.requested"),),
        timeout=timedelta(minutes=5),
        max_attempts=3,
        max_concurrency=4,
    )

    async def run(self, parameters: GreetParameters):
        return {"message": parameters.name * parameters.times}


class IngestParameters(PipelineParameters):
    count: int = 2


class IngestPipeline(Pipeline[IngestParameters]):
    """Loads triples."""

    job = JobSettings(triggers=(Every("1h"),))

    async def run(self, parameters: IngestParameters):
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


class ManualWorkflow(Workflow[WorkflowParameters]):
    job = JobSettings()

    async def run(self, parameters: WorkflowParameters):
        return {"ok": True}


class PlainWorkflow(Workflow[WorkflowParameters]):
    """Declares no job."""

    async def run(self, parameters: WorkflowParameters):
        return {}


def module_of(*, workflows=(), pipelines=(), **attributes) -> type[BaseModule]:
    return type(
        "ABIModule",
        (BaseModule,),
        {
            "module_id": "acme.jobs",
            "workflows": tuple(workflows),
            "pipelines": tuple(pipelines),
            **attributes,
        },
    )


def built(module_type: type[BaseModule]) -> BaseModule:
    module = module_type(MagicMock(), module_type.Configuration())
    asyncio.run(module.build_processes())
    return module


# --- descriptors ------------------------------------------------------------------


def test_a_blank_docstring_gives_the_job_the_class_name_as_description():
    class BlankWorkflow(Workflow[WorkflowParameters]):
        """ """  # noqa: D419

        job = JobSettings()

    (descriptor,) = module_of(workflows=(BlankWorkflow,)).get_jobs()

    assert descriptor.name == "workflow.blank_workflow"
    assert descriptor.description == "blank_workflow"


def test_a_process_with_job_settings_gets_a_descriptor_named_after_kind_and_name():
    module_type = module_of(
        workflows=(GreetWorkflow, ManualWorkflow, PlainWorkflow),
        pipelines=(IngestPipeline,),
    )

    jobs = {j.name: j for j in module_type.get_jobs()}

    assert sorted(jobs) == [
        "pipeline.ingest_pipeline",
        "workflow.greet_workflow",
        "workflow.manual_workflow",
    ]
    assert all(JOB_NAME.fullmatch(name) for name in jobs)
    greet = jobs["workflow.greet_workflow"]
    assert greet == JobDescriptor(
        "workflow.greet_workflow",
        description="Greets someone.",
        triggers=(OnEvent(subject="greet.requested"),),
        max_concurrency=4,
        timeout=timedelta(minutes=5),
        max_attempts=3,
    )
    ingest = jobs["pipeline.ingest_pipeline"]
    assert ingest.triggers == (Every("1h"),) and ingest.description == "Loads triples."
    manual = jobs["workflow.manual_workflow"]
    assert manual.triggers == () and manual.max_attempts == 1 and manual.timeout is None


def test_the_name_is_deterministic_and_the_job_survives_the_discovery_round_trip():
    module_type = module_of(pipelines=(IngestPipeline,))

    assert process_job_name("pipeline", "ingest_pipeline") == "pipeline.ingest_pipeline"
    descriptor = module_descriptor(module_type, "acme.jobs", ())
    assert [JobDescriptor.from_pb(j) for j in descriptor.jobs] == list(
        module_type.get_jobs()
    )
    assert [p.name for p in descriptor.processes] == ["ingest_pipeline"]


def test_explicit_jobs_stay_and_a_module_without_job_settings_adds_none():
    class Explicit(BaseModule):
        module_id = "acme.explicit"
        workflows = (PlainWorkflow,)
        jobs = (JobDescriptor("nightly"),)

        @job(triggers=(Every("1m"),))
        async def tick(self, ctx):
            return None

    assert [j.name for j in Explicit.get_jobs()] == ["nightly", "tick"]

    class WithProcess(Explicit):
        workflows = (PlainWorkflow, ManualWorkflow)

    assert [j.name for j in WithProcess.get_jobs()] == [
        "nightly",
        "tick",
        "workflow.manual_workflow",
    ]


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
        module_of(workflows=(Odd,)).get_jobs()


# --- clashes and schedules ----------------------------------------------------------


def test_a_derived_name_that_an_explicit_job_has_fails():
    module_type = module_of(
        workflows=(ManualWorkflow,),
        jobs=(JobDescriptor("workflow.manual_workflow"),),
    )

    with pytest.raises(ValueError, match=r"workflow\.manual_workflow.*rename"):
        module_type.get_jobs()


def test_a_decorated_job_with_the_derived_name_fails_too():
    class Clash(BaseModule):
        module_id = "acme.clash"
        workflows = (ManualWorkflow,)

        @job("workflow.manual_workflow")
        async def explicit(self, ctx):
            return None

    with pytest.raises(ValueError, match=r"workflow\.manual_workflow"):
        Clash.get_jobs()


class NeedsParameters(WorkflowParameters):
    since: str


@pytest.mark.parametrize("trigger", [Cron("0 0 6 * * *"), Every("1h")])
def test_a_schedule_on_parameters_with_required_fields_fails(trigger):
    class Scheduled(Workflow[NeedsParameters]):
        job = JobSettings(triggers=(trigger,))

        async def run(self, parameters: NeedsParameters):
            return {}

    with pytest.raises(ValueError, match=r"'scheduled'.*since.*payload \{\}"):
        module_of(workflows=(Scheduled,)).get_jobs()


def test_required_fields_are_fine_for_events_and_manual_runs_and_defaults_for_schedules():
    class Event(Workflow[NeedsParameters]):
        job = JobSettings(triggers=(OnEvent(subject="x.y"),))

        async def run(self, parameters: NeedsParameters):
            return {}

    class Manual(Workflow[NeedsParameters]):
        job = JobSettings()

        async def run(self, parameters: NeedsParameters):
            return {}

    assert len(module_of(workflows=(Event, Manual)).get_jobs()) == 2
    assert len(module_of(pipelines=(IngestPipeline,)).get_jobs()) == 1  # count = 2


def test_run_module_fails_before_it_connects_on_a_clash(monkeypatch):
    module_type = module_of(
        workflows=(ManualWorkflow,),
        jobs=(JobDescriptor("workflow.manual_workflow"),),
    )
    client = MagicMock()
    monkeypatch.setattr("naas_abi_sdk.module.ABIClient", client)

    with pytest.raises(ValueError, match="workflow.manual_workflow"):
        asyncio.run(run_module(module_type, url="nats://unused", token="t"))

    client.assert_not_called()


# --- binding ----------------------------------------------------------------------


def test_building_binds_a_handler_for_each_derived_job_and_no_other():
    module = built(
        module_of(
            workflows=(GreetWorkflow, PlainWorkflow),
            pipelines=(IngestPipeline,),
            jobs=(JobDescriptor("nightly"),),
        )
    )

    assert module.missing_job_handlers() == {"nightly"}
    assert sorted(module._job_handlers) == [
        "pipeline.ingest_pipeline",
        "workflow.greet_workflow",
    ]
    asyncio.run(module.build_processes())  # idempotent: nothing replaced
    assert len(module._job_handlers) == 2


def test_an_instance_bound_with_expose_workflow_is_the_one_the_job_runs():
    module = module_of(workflows=(GreetWorkflow,))(
        MagicMock(), BaseModule.Configuration()
    )
    bound = GreetWorkflow(None)
    module.expose_workflow("greet_workflow", bound)
    asyncio.run(module.build_processes())

    record = asyncio.run(
        module._job_handlers["workflow.greet_workflow"](context({"name": "Ada"}))
    )

    assert (
        record == {"message": "Ada"} and module.get_workflow("greet_workflow") is bound
    )


# --- the handler ------------------------------------------------------------------


def context(payload, kind="manual") -> JobContext:
    return JobContext("run:1", "job", 1, {"kind": kind}, payload)


def handler_of(cls, kind="workflow", configuration=None):
    return process_job_handler(kind, cls(configuration))


def test_a_workflow_job_validates_the_payload_and_returns_its_json():
    handle = handler_of(GreetWorkflow)

    assert asyncio.run(handle(context({"name": "ab", "times": 2}))) == {
        "message": "abab"
    }


def test_a_pipeline_job_returns_its_graph_as_n_triples_text():
    handle = handler_of(IngestPipeline, "pipeline")

    result = asyncio.run(handle(context({"count": 2})))

    assert isinstance(result, str)
    graph = Graph().parse(data=result, format="nt")
    assert len(graph) == 2
    assert asyncio.run(handle(context({}))) == result  # the default is count 2
    assert (
        len(Graph().parse(data=asyncio.run(handle(context({"count": 3}))), format="nt"))
        == 3
    )


def test_a_payload_the_model_refuses_fails_the_run_naming_fields_not_values():
    handle = handler_of(GreetWorkflow)

    with pytest.raises(RPCError, match="INVALID_ARGUMENT|name") as raised:
        asyncio.run(handle(context({"times": "secret-value"})))

    assert raised.value.code == "INVALID_ARGUMENT"
    assert "name: " in str(raised.value) and "times: " in str(raised.value)
    assert "secret-value" not in str(raised.value)


def test_the_process_never_runs_on_a_refused_payload():
    ran = []

    class Counting(Workflow[GreetParameters]):
        async def run(self, parameters):
            ran.append(parameters)
            return {}

    with pytest.raises(RPCError):
        asyncio.run(handler_of(Counting)(context({})))

    assert ran == []


def test_an_event_run_takes_the_events_data_as_its_parameters():
    handle = handler_of(GreetWorkflow)
    event = {"subject": "greet.requested", "data": {"name": "Eve"}}

    assert asyncio.run(handle(context(event, kind="event"))) == {"message": "Eve"}
    with pytest.raises(RPCError, match="name"):
        asyncio.run(handle(context({"subject": "s", "data": None}, kind="event")))
    with pytest.raises(RPCError, match="JSON object"):
        asyncio.run(handle(context({"subject": "s", "data": [1]}, kind="event")))


def test_a_result_the_process_cannot_encode_fails_the_run():
    class Bytes(Workflow[WorkflowParameters]):
        async def run(self, parameters):
            return {"data": object()}

    class NotAGraph(Pipeline[PipelineParameters]):
        async def run(self, parameters):
            return {"not": "a graph"}

    with pytest.raises(RPCError, match="JSON-serializable"):
        asyncio.run(handler_of(Bytes)(context({})))
    with pytest.raises(RPCError, match="rdflib Graph"):
        asyncio.run(handler_of(NotAGraph, "pipeline")(context({})))


def test_a_result_with_nested_models_and_common_scalars_is_the_runs_json():
    from datetime import datetime, timezone
    from decimal import Decimal
    from uuid import UUID

    class Item(WorkflowParameters):
        at: datetime
        id: UUID
        price: Decimal

    class Nested(Workflow[WorkflowParameters]):
        async def run(self, parameters):
            item = Item(
                at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                id=UUID(int=1),
                price=Decimal("2.5"),
            )
            return {"items": [item], "list": [item]}

    item = {"at": "2026-01-02T00:00:00Z", "id": str(UUID(int=1)), "price": "2.5"}

    assert asyncio.run(handler_of(Nested)(context({}))) == {
        "items": [item],
        "list": [item],
    }


def test_the_processs_own_error_reaches_the_run_unchanged():
    class Broken(Workflow[WorkflowParameters]):
        async def run(self, parameters):
            raise KeyError("boom")

    with pytest.raises(KeyError):
        asyncio.run(handler_of(Broken)(context({})))


def test_cancelling_the_run_cancels_the_process():
    state = SimpleNamespace(started=None, cancelled=False)

    class Slow(Workflow[WorkflowParameters]):
        async def run(self, parameters):
            state.started.set()
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                state.cancelled = True
                raise

    async def scenario():
        state.started = asyncio.Event()
        ctx = context({})
        task = asyncio.create_task(handler_of(Slow)(ctx))
        await state.started.wait()
        ctx.cancelled.set()
        return await asyncio.wait_for(task, 5)

    assert asyncio.run(scenario()) is None and state.cancelled


def test_a_host_timeout_cancels_the_process_too():
    state = SimpleNamespace(started=None, cancelled=False)

    class Slow(Workflow[WorkflowParameters]):
        async def run(self, parameters):
            state.started.set()
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                state.cancelled = True
                raise

    async def scenario():
        state.started = asyncio.Event()
        task = asyncio.create_task(handler_of(Slow)(context({})))
        await state.started.wait()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())

    assert state.cancelled


# --- the proxy ----------------------------------------------------------------------


def proxy_of(kind, name, jobs=(), error=None):
    async def get_job(job_name):
        if error is not None:
            raise error
        found = next((j for j in jobs if j.name == job_name), None)
        if found is None:
            raise RPCError("JOB_NOT_FOUND", job_name)
        return SimpleNamespace(trigger=triggered)

    triggered = AsyncMock(return_value=JobRun(None, "p", "acme.jobs", "j", "j:1"))
    module = SimpleNamespace(module_id="acme.jobs", get_job=get_job)
    return ProcessProxy(module, kind, name), triggered


def test_trigger_delegates_to_the_job_with_the_parameters_and_key():
    proxy, triggered = proxy_of(
        "pipeline",
        "ingest_pipeline",
        module_of(pipelines=(IngestPipeline,)).get_jobs(),
    )

    run = asyncio.run(
        proxy.trigger(IngestParameters(count=5), idempotency_key="nightly-1")
    )

    assert isinstance(run, JobRun)
    triggered.assert_awaited_once_with({"count": 5}, idempotency_key="nightly-1")


def test_trigger_accepts_a_dict_and_nothing_else():
    proxy, triggered = proxy_of(
        "workflow", "manual_workflow", module_of(workflows=(ManualWorkflow,)).get_jobs()
    )

    asyncio.run(proxy.trigger({"a": 1}))
    triggered.assert_awaited_once_with({"a": 1}, idempotency_key=None)
    with pytest.raises(TypeError, match="dict or a pydantic model"):
        asyncio.run(proxy.trigger("nope"))
    with pytest.raises(ValueError, match="JSON-serializable"):
        asyncio.run(proxy.trigger({"a": float("nan")}))


def test_trigger_refuses_a_process_that_is_not_bound_as_a_job():
    proxy, triggered = proxy_of(
        "workflow", "plain_workflow", module_of(workflows=(ManualWorkflow,)).get_jobs()
    )

    with pytest.raises(RPCError, match="JobSettings") as raised:
        asyncio.run(proxy.trigger({}))

    assert raised.value.code == "PROCESS_NOT_A_JOB"
    assert "plain_workflow" in str(raised.value)
    triggered.assert_not_awaited()


def test_trigger_does_not_hide_other_discovery_errors():
    proxy, _ = proxy_of(
        "workflow", "x", error=RPCError("MODULE_UNAVAILABLE", "no ready instances")
    )

    with pytest.raises(RPCError) as raised:
        asyncio.run(proxy.trigger({}))

    assert raised.value.code == "MODULE_UNAVAILABLE"
