import asyncio
import json
import threading

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
)
from naas_abi_core.engine.engine_loaders.EngineJobLoader import as_async_handler
from naas_abi_core.engine.engine_loaders.EngineProcessBridge import (
    GRAPH_OUTPUT_SCHEMA,
    bridge_processes,
    declare_process_workflow,
    encode_process_result,
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
from pydantic import BaseModel
from rdflib import RDF, Graph, Literal, URIRef

SECRET = "bridge-test-secret-32-bytes-long-ok"


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
    return NATSConfiguration(jwt_secret=SECRET, workflows=workflows)


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
    assert json.loads(workflow.output_schema)["required"] == ["greeting"]
    # The class's own docstring only: ReportWorkflow has none, Workflow's is generic.
    assert workflow.description == "ReportWorkflow"


def test_the_bridge_is_off_without_nats_and_with_the_switch():
    for config in (None, _config(bridge=False)):
        module = _Module(pipelines=[_tweets()])
        assert bridge_processes({"acme.mod": module}, config) == []
        assert module.jobs == ()
    assert _config().workflows.bridge is True


def test_the_bridge_switch_reads_from_the_nats_block():
    config = NATSConfiguration.model_validate(
        {"jwt_secret": SECRET, "workflows": {"bridge": False}}
    )

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
