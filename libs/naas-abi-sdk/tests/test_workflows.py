"""Workflows, pipelines and integrations of a remote module (extras: workflows, rdf, agents)."""

from __future__ import annotations

import asyncio
import sys
import textwrap
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest

from naas_abi_sdk.discovery import DiscoveryConfiguration
from naas_abi_sdk.module import BaseModule, run_module

pydantic = pytest.importorskip("pydantic")
pytest.importorskip("rdflib")

from naas_abi_sdk.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from naas_abi_sdk.pipeline import Pipeline, PipelineParameters
from naas_abi_sdk.workflow import (
    Workflow,
    WorkflowConfiguration,
    WorkflowParameters,
)

_COUNTER = iter(range(10_000))

MODULE = """
from naas_abi_sdk import BaseModule


class ABIModule(BaseModule):
    module_id = "acme.demo"
"""

GREET = '''
from dataclasses import dataclass

from naas_abi_sdk.workflow import Workflow, WorkflowConfiguration, WorkflowParameters


@dataclass
class GreetWorkflowConfiguration(WorkflowConfiguration):
    greeting: str = "Hello"


class GreetWorkflowParameters(WorkflowParameters):
    name: str


class GreetWorkflow(Workflow[GreetWorkflowParameters]):
    """Greets someone by name."""

    def __init__(self, configuration: GreetWorkflowConfiguration):
        super().__init__(configuration)
        self.greeting = configuration.greeting

    async def run(self, parameters: GreetWorkflowParameters) -> dict:
        return {"message": f"{self.greeting}, {parameters.name}!"}
'''


@pytest.fixture
def package(tmp_path, monkeypatch):
    """Write a module package to disk and import its ABIModule."""
    monkeypatch.syspath_prepend(str(tmp_path))
    created: list[str] = []

    def make(files: dict[str, str], module: str = MODULE) -> type[BaseModule]:
        name = f"remote_pkg_{next(_COUNTER)}"
        root = tmp_path / name
        for relative, source in {"__init__.py": module, **files}.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(textwrap.dedent(source), encoding="utf-8")
        import importlib

        importlib.invalidate_caches()
        created.append(name)
        return importlib.import_module(name).ABIModule

    yield make
    for name in list(sys.modules):
        if name.split(".")[0] in created:
            del sys.modules[name]


def with_methods(monkeypatch, module_type: type[BaseModule], **methods):
    """The module class with ``methods`` in place: discovery follows the class
    that defines the package, so a subclass elsewhere would look elsewhere."""
    for name, method in methods.items():
        monkeypatch.setattr(module_type, name, method)
    return module_type


def engine_module(module_type: type[BaseModule]) -> BaseModule:
    return module_type(MagicMock(), module_type.Configuration())


def test_two_classes_with_one_slug_are_refused(package):
    module_type = package(
        {
            "workflows/a.py": """
            from naas_abi_sdk.workflow import Workflow

            class FooBar(Workflow):
                pass
            """,
            "workflows/b.py": """
            from naas_abi_sdk.workflow import Workflow

            class Foo_Bar(Workflow):
                pass
            """,
        }
    )
    with pytest.raises(ValueError, match="'foo_bar'.*Rename one class"):
        module_type.get_workflow_classes()


# --- discovery -----------------------------------------------------------------


def test_workflows_and_pipelines_are_discovered_recursively(package):
    module_type = package(
        {
            "workflows/greet.py": GREET,
            "workflows/deep/__init__.py": "",
            "workflows/deep/farewell.py": """
            from naas_abi_sdk.workflow import Workflow

            class FarewellWorkflow(Workflow):
                pass
            """,
            "pipelines/load.py": """
            from naas_abi_sdk.pipeline import Pipeline

            class LoadPipeline(Pipeline):
                pass
            """,
        }
    )

    assert list(module_type.get_workflow_classes()) == [
        "farewell_workflow",
        "greet_workflow",
    ]
    assert list(module_type.get_pipeline_classes()) == ["load_pipeline"]
    # Class level, before any instance or registration.
    assert (
        module_type.get_workflow_classes()["greet_workflow"].__name__ == "GreetWorkflow"
    )


def test_discovery_skips_tests_helpers_that_only_import_and_abstract_bases(package):
    module_type = package(
        {
            "workflows/greet.py": GREET,
            # Imports a workflow: it is not defined here.
            "workflows/reexport.py": "from .greet import GreetWorkflow\n",
            "workflows/greet_test.py": "raise RuntimeError('tests are not imported')\n",
            "workflows/test_greet.py": "raise RuntimeError('tests are not imported')\n",
            "workflows/tests/test_more.py": "raise RuntimeError('not imported')\n",
            "workflows/base.py": """
            import abc
            from naas_abi_sdk.workflow import Workflow

            class BaseWorkflow(Workflow, abc.ABC):
                @abc.abstractmethod
                def helper(self): ...
            """,
        }
    )

    assert list(module_type.get_workflow_classes()) == ["greet_workflow"]


def test_declared_classes_replace_discovery(package):
    module_type = package({"workflows/greet.py": GREET})

    class OtherWorkflow(Workflow):
        pass

    class Declared(module_type):
        workflows = (OtherWorkflow,)

    assert list(Declared.get_workflow_classes()) == ["other_workflow"]
    with pytest.raises(TypeError, match="Pipeline subclasses"):

        class Wrong(module_type):
            pipelines = (OtherWorkflow,)

        Wrong.get_pipeline_classes()


def test_a_module_without_folders_has_none(package):
    module_type = package({})
    assert module_type.get_workflow_classes() == {}
    assert module_type.get_pipeline_classes() == {}


def test_a_file_that_cannot_be_imported_fails_discovery_naming_it(package):
    module_type = package({"workflows/broken.py": "import not_a_real_dependency_xyz\n"})
    with pytest.raises(
        ImportError, match=r"workflows\.broken.*not_a_real_dependency_xyz"
    ):
        module_type.get_workflow_classes()


# --- construction --------------------------------------------------------------


def test_run_module_builds_each_class_with_its_empty_configuration(
    package, monkeypatch
):
    module_type = package(
        {
            "workflows/greet.py": GREET,
            "pipelines/load.py": """
            from naas_abi_sdk.pipeline import Pipeline
            from rdflib import Graph

            class LoadPipeline(Pipeline):
                async def run(self, parameters):
                    return Graph()
            """,
        }
    )
    seen = {}

    async def run(self):
        seen["workflow"] = self.get_workflow("greet_workflow")
        seen["pipeline"] = self.get_pipeline("load_pipeline")
        return sorted(self.get_workflows()), sorted(self.get_pipelines())

    with_methods(monkeypatch, module_type, run=run)

    result = asyncio.run(run_module_with_fake_client(monkeypatch, module_type))

    assert result == (["greet_workflow"], ["load_pipeline"])
    assert type(seen["workflow"]).__name__ == "GreetWorkflow"
    assert seen["workflow"].greeting == "Hello"
    assert asyncio.run(
        seen["workflow"].run(seen["workflow"].parameters_type()(name="Ada"))
    ) == {"message": "Hello, Ada!"}


class FakeSession:
    """A registration that is READY at once: no broker, no discovery service."""

    def __init__(self, client, descriptor, rollout_id="", rollout_modules=()):
        self.client, self.descriptor = client, descriptor
        self.rollout_id, self.rollout_modules = rollout_id, rollout_modules
        self.instance_id, self.lease_token = "instance", "lease"
        self.initialized = self.draining = False
        self.status, self.task = "READY", None
        self.drain_requested = asyncio.Event()

    async def start(self):
        pass

    async def renew(self):
        pass

    async def close(self):
        pass


class FakeProcessHost:
    """Records what the module would serve; the host itself is tested apart."""

    hosted: ClassVar[list] = []

    def __init__(self, session, workflows, pipelines):
        FakeProcessHost.hosted.append((sorted(workflows), sorted(pipelines)))

    async def start(self):
        pass

    async def drain(self, timeout):
        pass

    async def close(self):
        pass


async def run_module_with_fake_client(monkeypatch, module_type, **options):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr("naas_abi_sdk.module.ABIClient", lambda *a, **k: client)
    monkeypatch.setattr("naas_abi_sdk.module.DiscoverySession", FakeSession)
    monkeypatch.setattr("naas_abi_sdk.process_host.ProcessHost", FakeProcessHost)
    options.setdefault("discovery", DiscoveryConfiguration())
    FakeProcessHost.hosted.clear()
    return await run_module(module_type, url="nats://unused", token="issued", **options)


def test_new_builds_a_class_that_needs_the_module(package, monkeypatch):
    module_type = package(
        {
            "workflows/lookup.py": """
            from naas_abi_sdk.workflow import Workflow

            class LookupWorkflow(Workflow):
                def __init__(self, token):
                    super().__init__(None)
                    self.token = token

                @classmethod
                async def New(cls, module):
                    return cls(f"token-of-{module.module_id}")

                async def run(self, parameters):
                    return self.token
            """,
            "pipelines/sync.py": """
            from naas_abi_sdk.pipeline import Pipeline

            class SyncPipeline(Pipeline):
                def __init__(self, module):
                    super().__init__(None)
                    self.module = module

                @classmethod
                def New(cls, module):
                    return cls(module)
            """,
        }
    )

    async def run(self):
        return (
            self.get_workflow("lookup_workflow").token,
            self.get_pipeline("sync_pipeline").module is self,
        )

    with_methods(monkeypatch, module_type, run=run)

    assert asyncio.run(run_module_with_fake_client(monkeypatch, module_type)) == (
        "token-of-acme.demo",
        True,
    )


NEEDS_ARGUMENTS = """
from naas_abi_sdk.workflow import Workflow

class NeedsWorkflow(Workflow):
    def __init__(self, api_key):
        super().__init__(None)
        self.api_key = api_key
"""


def test_a_class_needing_arguments_is_bound_with_expose_workflow(package, monkeypatch):
    module_type = package({"workflows/needs.py": NEEDS_ARGUMENTS})

    async def on_initialized(self):
        cls = self.get_workflow_classes()["needs_workflow"]
        self.expose_workflow("needs_workflow", cls("secret"))

    async def run(self):
        return self.get_workflow("needs_workflow").api_key

    with_methods(monkeypatch, module_type, on_initialized=on_initialized, run=run)

    assert (
        asyncio.run(run_module_with_fake_client(monkeypatch, module_type)) == "secret"
    )


def test_an_unbuildable_and_unbound_class_fails_startup_naming_it(package, monkeypatch):
    module_type = package({"workflows/needs.py": NEEDS_ARGUMENTS})
    ran = []

    async def run(self):
        ran.append(True)

    with_methods(monkeypatch, module_type, run=run)

    with pytest.raises(ValueError) as error:
        asyncio.run(run_module_with_fake_client(monkeypatch, module_type))

    message = str(error.value)
    assert "NeedsWorkflow" in message and "'needs_workflow'" in message
    assert "expose_workflow" in message and "New(module)" in message
    assert not ran


def test_an_unbuildable_pipeline_names_expose_pipeline(package, monkeypatch):
    module_type = package(
        {
            "pipelines/needs.py": """
            from dataclasses import dataclass
            from naas_abi_sdk.pipeline import Pipeline, PipelineConfiguration

            @dataclass
            class NeedsPipelineConfiguration(PipelineConfiguration):
                url: str

            class NeedsPipeline(Pipeline):
                def __init__(self, configuration):
                    super().__init__(configuration)
            """
        }
    )
    with pytest.raises(ValueError, match=r"NeedsPipeline.*expose_pipeline"):
        asyncio.run(run_module_with_fake_client(monkeypatch, module_type))


def test_a_class_that_fails_to_build_fails_startup_naming_it(package, monkeypatch):
    module_type = package(
        {
            "workflows/bad.py": """
            from naas_abi_sdk.workflow import Workflow

            class BadWorkflow(Workflow):
                @classmethod
                def New(cls, module):
                    raise KeyError("API_KEY")
            """
        }
    )
    with pytest.raises(RuntimeError, match=r"BadWorkflow.*API_KEY") as error:
        asyncio.run(run_module_with_fake_client(monkeypatch, module_type))
    assert isinstance(error.value.__cause__, KeyError)


def test_run_module_hosts_what_it_built_and_refuses_to_without_discovery(
    package, monkeypatch
):
    module_type = package(
        {
            "workflows/greet.py": GREET,
            "pipelines/load.py": """
            from naas_abi_sdk.pipeline import Pipeline
            from rdflib import Graph

            class LoadPipeline(Pipeline):
                async def run(self, parameters):
                    return Graph()
            """,
        }
    )

    async def run(self):
        return "ran"

    with_methods(monkeypatch, module_type, run=run)

    assert asyncio.run(run_module_with_fake_client(monkeypatch, module_type)) == "ran"
    assert FakeProcessHost.hosted == [(["greet_workflow"], ["load_pipeline"])]

    client = MagicMock()
    monkeypatch.setattr("naas_abi_sdk.module.ABIClient", client)
    with pytest.raises(ValueError, match="requires discovery"):
        asyncio.run(run_module(module_type, url="nats://unused", token="issued"))
    client.assert_not_called()  # before it connects


def test_a_module_without_workflows_or_pipelines_hosts_none(package, monkeypatch):
    module_type = package({})

    async def run(self):
        return "ran"

    with_methods(monkeypatch, module_type, run=run)

    assert asyncio.run(run_module_with_fake_client(monkeypatch, module_type)) == "ran"
    assert FakeProcessHost.hosted == []


def test_a_bad_folder_fails_before_the_module_connects(package, monkeypatch):
    module_type = package({"workflows/broken.py": "import not_a_real_dependency_xyz\n"})
    client = MagicMock()
    monkeypatch.setattr("naas_abi_sdk.module.ABIClient", client)
    with pytest.raises(ImportError):
        asyncio.run(run_module(module_type, url="nats://unused", token="issued"))
    client.assert_not_called()


def test_expose_refuses_unknown_duplicate_and_foreign_instances(package):
    module_type = package({"workflows/needs.py": NEEDS_ARGUMENTS})
    module = engine_module(module_type)
    cls = module_type.get_workflow_classes()["needs_workflow"]

    with pytest.raises(ValueError, match="Declare the workflow first"):
        module.expose_workflow("nope", cls("k"))
    with pytest.raises(TypeError, match="not"):
        module.expose_workflow("needs_workflow", object())
    module.expose_workflow("needs_workflow", cls("k"))
    with pytest.raises(ValueError, match="already registered"):
        module.expose_workflow("needs_workflow", cls("k"))
    with pytest.raises(ValueError, match="Declare the pipeline first"):
        module.expose_pipeline("needs_workflow", cls("k"))


PIPELINE = """
from naas_abi_sdk.pipeline import Pipeline, PipelineParameters
from rdflib import RDFS, Graph, Literal, URIRef


class LoadPipelineParameters(PipelineParameters):
    label: str = "x"


class LoadPipeline(Pipeline[LoadPipelineParameters]):
    \"\"\"Loads a labelled individual.\"\"\"

    async def run(self, parameters: LoadPipelineParameters) -> Graph:
        graph = Graph()
        graph.add((URIRef("urn:a"), RDFS.label, Literal(parameters.label)))
        return graph
"""


class FakeAgent:
    """What an agent is to the module: it takes its tools when it is built."""

    def __init__(self, tools):
        self.tools = {tool.name: tool for tool in tools}


def test_an_agent_built_in_on_initialized_gets_the_tools_of_both_kinds(
    package, monkeypatch
):
    pytest.importorskip("langchain_core")
    module_type = package({"workflows/greet.py": GREET, "pipelines/load.py": PIPELINE})
    state = {}

    async def on_initialized(self):
        await self.build_processes()
        state["agent"] = FakeAgent(
            [
                *self.get_workflow("greet_workflow").as_tools(),
                *self.get_pipeline("load_pipeline").as_tools(),
            ]
        )

    async def run(self):
        tools = state["agent"].tools
        return (
            await tools["greet_workflow"].ainvoke({"name": "Ada"}),
            (await tools["load_pipeline"].ainvoke({"label": "A"}))["format"],
            tools["load_pipeline"].description,
        )

    with_methods(monkeypatch, module_type, on_initialized=on_initialized, run=run)

    assert asyncio.run(run_module_with_fake_client(monkeypatch, module_type)) == (
        {"message": "Hello, Ada!"},
        "turtle",
        "Loads a labelled individual.",
    )


def test_build_processes_is_idempotent_and_run_module_does_not_rebuild(
    package, monkeypatch
):
    module_type = package(
        {
            "workflows/counted.py": """
            from naas_abi_sdk.workflow import Workflow

            BUILT = []

            class CountedWorkflow(Workflow):
                @classmethod
                def New(cls, module):
                    BUILT.append(1)
                    return cls(None)
            """
        }
    )
    seen = {}

    async def on_initialized(self):
        await asyncio.gather(self.build_processes(), self.build_processes())
        seen["first"] = self.get_workflow("counted_workflow")
        await self.build_processes()

    async def run(self):
        import importlib

        built = importlib.import_module(
            f"{module_type.__module__}.workflows.counted"
        ).BUILT
        return built, self.get_workflow("counted_workflow") is seen["first"]

    with_methods(monkeypatch, module_type, on_initialized=on_initialized, run=run)

    assert asyncio.run(run_module_with_fake_client(monkeypatch, module_type)) == (
        [1],
        True,
    )


def test_a_class_bound_before_build_processes_is_left_alone(package, monkeypatch):
    module_type = package(
        {"workflows/needs.py": NEEDS_ARGUMENTS, "workflows/greet.py": GREET}
    )

    async def on_initialized(self):
        cls = self.get_workflow_classes()["needs_workflow"]
        self.expose_workflow("needs_workflow", cls("secret"))
        await self.build_processes()

    async def run(self):
        return sorted(self.get_workflows()), self.get_workflow("needs_workflow").api_key

    with_methods(monkeypatch, module_type, on_initialized=on_initialized, run=run)

    assert asyncio.run(run_module_with_fake_client(monkeypatch, module_type)) == (
        ["greet_workflow", "needs_workflow"],
        "secret",
    )


def test_build_processes_in_on_initialized_fails_for_an_unbuildable_class(
    package, monkeypatch
):
    module_type = package({"workflows/needs.py": NEEDS_ARGUMENTS})

    async def on_initialized(self):
        await self.build_processes()

    with_methods(monkeypatch, module_type, on_initialized=on_initialized)

    with pytest.raises(ValueError, match=r"NeedsWorkflow.*expose_workflow"):
        asyncio.run(run_module_with_fake_client(monkeypatch, module_type))


def test_a_workflow_before_it_is_built_is_not_available(package):
    module = engine_module(package({"workflows/greet.py": GREET}))
    with pytest.raises(ValueError, match="build_processes"):
        module.get_workflow("greet_workflow")


def test_run_must_be_async():
    with pytest.raises(TypeError, match="must be `async def`"):

        class Sync(Workflow):
            def run(self, parameters):
                return 1


# --- parameters and tools ------------------------------------------------------


class CountParameters(WorkflowParameters):
    a: int


def test_parameters_come_from_the_annotation_the_generic_or_the_naming_convention():
    class FromAnnotation(Workflow):
        async def run(self, parameters: CountParameters) -> int:
            return parameters.a

    class FromGeneric(Workflow[CountParameters]):
        async def run(self, parameters) -> int:
            return 1

    class Count(Workflow):
        async def run(self, parameters) -> int:
            return 1

    class Bare(Workflow):
        pass

    assert FromAnnotation.parameters_type() is CountParameters
    assert FromGeneric.parameters_type() is CountParameters
    # `CountParameters` sits beside `Count` in this module.
    assert Count.parameters_type() is CountParameters
    assert Bare.parameters_type() is WorkflowParameters


def test_as_tools_runs_the_workflow_with_the_parameters_model(package, monkeypatch):
    pytest.importorskip("langchain_core")
    module_type = package({"workflows/greet.py": GREET})

    async def scenario():
        async def run(self):
            (tool,) = self.get_workflow("greet_workflow").as_tools()
            assert tool.name == "greet_workflow"
            assert tool.description == "Greets someone by name."
            assert set(tool.args) == {"name"}
            return await tool.ainvoke({"name": "Ada"})

        with_methods(monkeypatch, module_type, run=run)
        return await run_module_with_fake_client(monkeypatch, module_type)

    assert asyncio.run(scenario()) == {"message": "Hello, Ada!"}


def test_a_tool_returns_a_model_as_json_and_a_graph_as_turtle():
    pytest.importorskip("langchain_core")
    from rdflib import RDF, Graph, Literal, URIRef

    class Out(WorkflowParameters):
        count: int

    class Tally(Workflow):
        """Counts."""

        async def run(self, parameters: WorkflowParameters) -> Out:
            return Out(count=2)

    class Describe(Pipeline):
        async def run(self, parameters: PipelineParameters) -> Graph:
            graph = Graph()
            graph.add((URIRef("urn:a"), RDF.value, Literal("x")))
            return graph

    async def scenario():
        (count,) = Tally(WorkflowConfiguration()).as_tools()
        (describe,) = Describe(None).as_tools()
        return await count.ainvoke({}), await describe.ainvoke({})

    counted, described = asyncio.run(scenario())
    assert counted == {"count": 2}
    assert described["format"] == "turtle" and "urn:a" in described["data"]
    # No docstring of its own: the name, not the base class's description.
    assert Describe(None).as_tools()[0].description == "describe"


def test_a_sync_tool_call_from_another_thread_runs_on_the_module_loop():
    pytest.importorskip("langchain_core")
    loops = []

    class Where(Workflow):
        """Reports its loop."""

        async def run(self, parameters: WorkflowParameters) -> str:
            loops.append(asyncio.get_running_loop())
            return "done"

    async def scenario():
        (tool,) = Where(None).as_tools()
        result = await asyncio.to_thread(tool.invoke, {})
        return result, asyncio.get_running_loop()

    result, loop = asyncio.run(scenario())
    assert result == "done" and loops == [loop]


def test_a_sync_tool_call_on_the_module_loop_is_refused():
    pytest.importorskip("langchain_core")

    class Noop(Workflow):
        async def run(self, parameters: WorkflowParameters) -> None:
            return None

    async def scenario():
        (tool,) = Noop(None).as_tools()
        with pytest.raises(RuntimeError, match="ainvoke"):
            tool.invoke({})

    asyncio.run(scenario())


# --- integrations --------------------------------------------------------------


def test_an_integration_keeps_its_configuration_and_names_connection_errors():
    class Fake(IntegrationConfiguration):
        pass

    class FakeIntegration(Integration):
        def __init__(self, configuration: Fake):
            super().__init__(configuration)

    assert FakeIntegration(Fake())
    assert issubclass(IntegrationConnectionError, Exception)
