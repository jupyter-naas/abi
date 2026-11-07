import asyncio
import json
import threading

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
)
from naas_abi_core.engine.engine_loaders.EngineJobLoader import as_async_handler
from naas_abi_core.engine.engine_loaders.EngineProcessBridge import (
    bridge_processes,
    declare_process_workflow,
    process_workflow_name,
)
from naas_abi_core.module.jobs import JobsMixin
from naas_abi_core.module.workflows_test import Documents, _flow
from naas_abi_core.pipeline.pipeline import (
    Pipeline,
    PipelineConfiguration,
    PipelineParameters,
)
from naas_abi_core.workflow.workflow import (
    Workflow,
    WorkflowConfiguration,
    WorkflowParameters,
)

# The encoding is the SDK's, shared with remote modules' classes.
from naas_abi_sdk.process_workflows import GRAPH_OUTPUT_SCHEMA, encode_process_result
from pydantic import BaseModel
from rdflib import RDF, Graph, Literal, URIRef


class _NoTools:
    def as_tools(self):
        return []


class TweetsParameters(PipelineParameters):
    query: str
    limit: int = 10


class TweetsPipeline(_NoTools, Pipeline):
    """Maps tweets to the ontology.

    Writes the triples to the triple store too.
    """

    def run(self, parameters: TweetsParameters) -> Graph:  # type: ignore[override]
        graph = Graph()
        for i in range(parameters.limit):
            graph.add((URIRef(f"urn:t:{i}"), RDF.type, Literal(parameters.query)))
        self.thread = threading.current_thread().name
        return graph


class ReportParameters(WorkflowParameters):
    name: str


class ReportOutput(BaseModel):
    greeting: str


class ReportWorkflow(_NoTools, Workflow[ReportParameters]):
    def run(self, parameters: ReportParameters) -> ReportOutput:
        return ReportOutput(greeting=f"hello {parameters.name}")


class DictWorkflow(_NoTools, Workflow[ReportParameters]):
    def run(self, parameters: ReportParameters) -> dict:
        return {"name": parameters.name}


class StubWorkflow(_NoTools, Workflow):
    """A scaffold: the inherited run() is not live."""


class TrivialPipeline(_NoTools, Pipeline):
    def run(self, parameters: TweetsParameters) -> Graph:  # type: ignore[override]
        raise NotImplementedError()


class UntypedWorkflow(_NoTools, Workflow):
    def run(self, parameters):
        return {"live": True}


class AsyncPipeline(_NoTools, Pipeline):
    async def run(self, parameters: TweetsParameters) -> Graph:  # type: ignore[override]
        return Graph()


class _Module(JobsMixin):
    _sync_jobs = True

    def __init__(self, workflows=(), pipelines=()):
        self.workflows, self.pipelines = list(workflows), list(pipelines)


def _config(**workflows):
    return NATSConfiguration(workflows=workflows)


def _tweets():
    return TweetsPipeline(PipelineConfiguration())


def _report():
    return ReportWorkflow(WorkflowConfiguration())


def test_names_are_the_rest_slug_with_the_kind_in_front():
    assert process_workflow_name("pipeline", _tweets()) == "pipeline.tweets_pipeline"
    assert process_workflow_name("workflow", _report()) == "workflow.report_workflow"


def test_only_instances_with_a_live_typed_run_are_published():
    module = _Module(
        workflows=[
            _report(),
            DictWorkflow(WorkflowConfiguration()),
            StubWorkflow(WorkflowConfiguration()),
            UntypedWorkflow(WorkflowConfiguration()),
        ],
        pipelines=[
            _tweets(),
            TrivialPipeline(PipelineConfiguration()),
            AsyncPipeline(PipelineConfiguration()),
        ],
    )

    declared = bridge_processes({"acme.mod": module}, _config())

    assert sorted(declared) == [
        "acme.mod:pipeline.tweets_pipeline",
        "acme.mod:workflow.dict_workflow",
        "acme.mod:workflow.report_workflow",
    ]
    assert {j.name for j in module.jobs} == {
        "pipeline.tweets_pipeline",
        "workflow.dict_workflow",
        "workflow.report_workflow",
    }


def test_the_workflow_carries_the_schema_the_description_and_one_attempt():
    module = _Module(pipelines=[_tweets()], workflows=[_report()])
    bridge_processes({"acme.mod": module}, _config())

    pipeline = next(j for j in module.jobs if j.name == "pipeline.tweets_pipeline")
    workflow = next(j for j in module.jobs if j.name == "workflow.report_workflow")

    assert pipeline.kind == "workflow"
    assert pipeline.max_concurrency == 1 and pipeline.max_attempts == 1
    assert pipeline.triggers == ()
    assert pipeline.description == (
        "Maps tweets to the ontology.\n\nWrites the triples to the triple store too."
    )
    schema = json.loads(pipeline.input_schema)
    assert schema["required"] == ["query"]
    assert set(schema["properties"]) == {"query", "limit"}
    assert json.loads(pipeline.output_schema) == json.loads(
        json.dumps(GRAPH_OUTPUT_SCHEMA, sort_keys=True)
    )
    assert json.loads(workflow.output_schema)["anyOf"][0]["required"] == ["greeting"]
    # The class's own docstring only: ReportWorkflow has none, Workflow's is generic.
    assert workflow.description == "ReportWorkflow"


def test_the_bridge_is_off_without_nats_and_with_the_switch():
    for config in (None, _config(bridge=False)):
        module = _Module(pipelines=[_tweets()])
        assert bridge_processes({"acme.mod": module}, config) == []
        assert module.jobs == ()
    assert _config().workflows.bridge is True


def test_the_bridge_switch_reads_from_the_nats_block():
    config = NATSConfiguration.model_validate({"workflows": {"bridge": False}})

    assert config.workflows.bridge is False


def test_modules_without_workflows_or_pipelines_are_left_alone():
    class Plain:
        jobs = ()

    assert (
        bridge_processes({"acme.plain": Plain(), "acme.empty": _Module()}, _config())
        == []
    )


def test_a_name_that_exists_is_not_replaced():
    module = _Module(pipelines=[_tweets()])

    first = declare_process_workflow(module, "pipeline", module.pipelines[0])
    again = declare_process_workflow(module, "pipeline", module.pipelines[0])

    assert first == "pipeline.tweets_pipeline" and again is None
    assert len(module.jobs) == 1


def test_a_class_that_cannot_be_declared_does_not_stop_the_others():
    module = _Module(pipelines=[_tweets()], workflows=[_report()])
    module._seal_jobs()  # the host already took the jobs

    assert bridge_processes({"acme.mod": module}, _config()) == []


def test_a_graph_becomes_turtle_with_its_triple_count():
    graph = Graph()
    graph.add((URIRef("urn:a"), RDF.type, URIRef("urn:B")))

    encoded = encode_process_result(graph)

    assert encoded["format"] == "text/turtle" and encoded["triples"] == 1
    assert "urn:a" in encoded["data"]
    parsed = Graph().parse(data=encoded["data"], format="turtle")
    assert len(parsed) == 1
    assert set(encoded) == {"format", "triples", "data"}


def test_a_large_graph_drops_its_turtle_and_says_why():
    graph = Graph()
    for i in range(500):
        graph.add((URIRef(f"urn:s:{i}"), RDF.type, URIRef("urn:Thing")))

    encoded = encode_process_result(graph, max_bytes=1000)

    assert encoded["triples"] == 500 and "data" not in encoded
    assert "Turtle omitted" in encoded["note"] and "1000" in encoded["note"]


def test_other_results_are_kept_as_they_are():
    class Out(BaseModel):
        n: int

    assert encode_process_result(Out(n=2)) == {"n": 2}
    assert encode_process_result({"a": [1, 2]}) == {"a": [1, 2]}
    assert encode_process_result([1, "x"]) == [1, "x"]
    assert encode_process_result("done") == "done"
    assert encode_process_result(None) is None
    assert encode_process_result(b"raw") == {"data": "raw"}


def test_values_the_rest_route_can_send_do_not_fail_the_step():
    import datetime
    import decimal
    import enum
    import pathlib

    class Color(enum.Enum):
        RED = "red"

    result = {
        "when": datetime.datetime(2026, 10, 25, 10, 0, tzinfo=datetime.UTC),
        "day": datetime.date(2026, 10, 25),
        "path": pathlib.Path("/srv/x"),
        "price": decimal.Decimal("1.50"),
        "tags": {"b"},
        "color": Color.RED,
        "ratio": float("nan"),
        "inf": float("inf"),
        "odd": object,
    }

    encoded = encode_process_result(result)

    json.dumps(encoded, allow_nan=False)  # what the step journal requires
    assert encoded["when"].startswith("2026-10-25T10:00:00")
    assert encoded["day"] == "2026-10-25" and encoded["path"] == "/srv/x"
    assert (
        encoded["price"] == 1.5
        and encoded["tags"] == ["b"]
        and encoded["color"] == "red"
    )
    assert encoded["ratio"] is None and encoded["inf"] is None
    assert isinstance(encoded["odd"], str)
    assert encode_process_result({("a", "b"): 1}) == {"('a', 'b')": 1}
    loop: list = []
    loop.append(loop)
    assert encode_process_result(loop)["repr"].startswith("[")


def test_a_pipeline_returning_such_a_dict_still_succeeds_after_its_work():
    import datetime

    class Dated(_NoTools, Workflow[ReportParameters]):
        wrote = 0

        def run(self, parameters: ReportParameters) -> dict:
            Dated.wrote += 1  # the work, done before the result is encoded
            return {"at": datetime.datetime(2026, 1, 1), "score": float("nan")}

    module = _Module(workflows=[Dated(WorkflowConfiguration())])
    bridge_processes({"acme.mod": module}, _config())

    result, docs = _run(module, "workflow.dated", {"name": "x"})

    assert result == {"at": "2026-01-01T00:00:00", "score": None}
    assert Dated.wrote == 1 and docs.statuses() == {"run": "SUCCEEDED"}


def test_a_result_over_the_cap_becomes_a_marker_for_every_result_type():
    class Big(BaseModel):
        items: list[str]

    huge = ["x" * 100] * 1000  # about 100 KB of JSON
    for result in ({"items": huge}, huge, Big(items=huge), "y" * 200_000):
        encoded = encode_process_result(result)
        assert encoded["omitted"] is True and encoded["limit"] == 60 * 1024
        assert encoded["bytes"] > 60 * 1024 and "left out" in encoded["note"]
        assert len(json.dumps(encoded)) < 1000
    small = {"items": ["x"]}
    assert encode_process_result(small) == small
    assert encode_process_result(huge, max_bytes=10**6) == huge


def test_a_result_that_is_not_an_object_is_not_advertised_as_one():
    class Names(_NoTools, Workflow[ReportParameters]):
        def run(self, parameters: ReportParameters) -> list[str]:
            return ["a", "b"]

    class Count(_NoTools, Workflow[ReportParameters]):
        def run(self, parameters: ReportParameters) -> int:
            return 2

    class Untyped(_NoTools, Workflow[ReportParameters]):
        def run(self, parameters: ReportParameters):  # type: ignore[no-untyped-def]
            return "done"

    module = _Module(
        workflows=[
            Names(WorkflowConfiguration()),
            Count(WorkflowConfiguration()),
            Untyped(WorkflowConfiguration()),
        ]
    )
    bridge_processes({"acme.mod": module}, _config())

    assert len(module.jobs) == 3
    for job in module.jobs:
        schema = json.loads(job.output_schema)
        assert "type" not in schema and "description" in schema, job.name


def test_the_advertised_output_schema_admits_the_marker():
    class Out(BaseModel):
        n: int

    class Typed(_NoTools, Workflow[ReportParameters]):
        def run(self, parameters: ReportParameters) -> Out:
            return Out(n=1)

    module = _Module(workflows=[Typed(WorkflowConfiguration())])
    bridge_processes({"acme.mod": module}, _config())

    schema = json.loads(module.jobs[0].output_schema)

    assert [s.get("title") for s in schema["anyOf"]] == ["Out", None]
    assert schema["anyOf"][1]["required"] == ["omitted", "bytes", "limit"]


def test_bridging_the_same_modules_twice_declares_each_class_once_without_warnings(
    caplog,
):
    module = _Module(pipelines=[_tweets()], workflows=[_report()])

    first = bridge_processes({"acme.mod": module}, _config())
    with caplog.at_level("WARNING"):
        second = bridge_processes({"acme.mod": module}, _config())

    assert len(first) == 2 and second == []
    assert len(module.jobs) == 2
    assert not [r for r in caplog.records if "exists" in r.getMessage()]


def test_a_users_workflow_of_the_same_name_still_wins():
    class Mine(JobsMixin):
        _sync_jobs = True
        workflows = [_report()]
        pipelines: list = []

    module = Mine()
    module.declare_workflow(
        "workflow.report_workflow", lambda ctx, inp: {}, input_schema={"type": "object"}
    )

    assert bridge_processes({"acme.mod": module}, _config()) == []
    assert len(module.jobs) == 1


def _run(module, name, payload):
    handler = as_async_handler(module._job_handlers[name], interrupt_grace_seconds=2)
    docs = Documents()

    async def go():
        return await handler(_flow(docs, run_id=f"{name}:1", payload=payload))

    return asyncio.run(go()), docs


def test_the_handler_validates_the_input_and_runs_the_class_in_the_worker_thread():
    pipeline = _tweets()
    module = _Module(pipelines=[pipeline], workflows=[_report()])
    bridge_processes({"acme.mod": module}, _config())

    result, docs = _run(module, "pipeline.tweets_pipeline", {"query": "db", "limit": 3})

    assert result["format"] == "text/turtle" and result["triples"] == 3
    assert pipeline.thread.startswith("abi-job-")  # the worker thread, not the loop's
    assert docs.statuses() == {"run": "SUCCEEDED"}  # one step
    greeting, _ = _run(module, "workflow.report_workflow", {"name": "abi"})
    assert greeting == {"greeting": "hello abi"}


def test_an_invalid_input_never_reaches_run():
    pipeline = _tweets()
    module = _Module(pipelines=[pipeline])
    bridge_processes({"acme.mod": module}, _config())

    from naas_abi_sdk.jobs import NonRetryable

    with pytest.raises(NonRetryable, match="query"):
        _run(module, "pipeline.tweets_pipeline", {"limit": 3})
    assert not hasattr(pipeline, "thread")


def test_the_bridged_instances_still_answer_in_process():
    pipeline = _tweets()
    bridge_processes({"acme.mod": _Module(pipelines=[pipeline])}, _config())

    assert len(pipeline.run(TweetsParameters(query="q", limit=2))) == 2


def test_bridged_workflows_of_a_base_module_are_listed_by_the_engine_as_jobs():
    from types import SimpleNamespace

    from naas_abi_core.engine.Engine import Engine
    from naas_abi_core.module.Module import BaseModule, ModuleConfiguration

    class Acme(BaseModule):
        class Configuration(ModuleConfiguration):
            pass

    module = object.__new__(Acme)
    module._BaseModule__pipelines = [_tweets()]  # type: ignore[attr-defined]
    module._BaseModule__workflows = [_report(), StubWorkflow(WorkflowConfiguration())]  # type: ignore[attr-defined]
    nats = _config()
    bridge_processes({"acme.mod": module}, nats)

    engine = Engine.__new__(Engine)
    engine._Engine__configuration = SimpleNamespace(nats=nats)  # type: ignore[attr-defined]
    engine._Engine__modules = {"acme.mod": module}  # type: ignore[attr-defined]
    engine._Engine__services = SimpleNamespace(  # type: ignore[attr-defined]
        dataset_available=lambda: False, all=[]
    )
    engine._Engine__agent_checkpointer = None  # type: ignore[attr-defined]

    owner = engine.job_owners()["acme.mod"]
    listed = {j.name: j for j in owner.jobs}  # type: ignore[attr-defined]
    assert set(listed) == {"pipeline.tweets_pipeline", "workflow.report_workflow"}
    assert all(j.kind == "workflow" and j.input_schema for j in listed.values())
    assert owner.missing_job_handlers() == set()  # type: ignore[attr-defined]
