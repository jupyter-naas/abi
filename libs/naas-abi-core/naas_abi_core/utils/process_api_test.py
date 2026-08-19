"""Kernel process mounts: live as_api, default run(), stubs, no fiction."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import Field
from rdflib import Graph

from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.utils.Expose import Expose
from naas_abi_core.utils.process_api import (
    instantiate_process,
    mount_expose_process,
    mount_module_processes,
)
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters


@dataclass
class EchoWorkflowConfiguration(WorkflowConfiguration):
    pass


class EchoWorkflowParameters(WorkflowParameters):
    text: Annotated[str, Field(..., description="Text to echo")]


class _StubAsApi:
    """Empty as_api with the Expose signature. Kernel should fall back to run()."""

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        return None


class EchoWorkflow(_StubAsApi, Workflow):
    """Fixture workflow with a stub as_api and a live run()."""

    def run(self, parameters: EchoWorkflowParameters) -> dict:
        return {"echo": parameters.text}

    def as_tools(self) -> list[BaseTool]:
        return []


class DeadWorkflow(_StubAsApi, Workflow):
    """Fixture workflow: stub as_api and no run() override."""

    def as_tools(self) -> list[BaseTool]:
        return []


class LiveWorkflow(Workflow):
    """Fixture workflow that registers its own route."""

    def run(self, parameters: EchoWorkflowParameters) -> dict:
        return {"live": parameters.text}

    def as_tools(self) -> list[BaseTool]:
        return []

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        @router.post("/custom_live")
        def custom(parameters: EchoWorkflowParameters) -> dict:
            return self.run(parameters)


@dataclass
class EchoPipelineConfiguration(PipelineConfiguration):
    pass


class EchoPipeline(_StubAsApi, Pipeline):
    def run(self, parameters: PipelineParameters) -> Graph:
        return Graph()

    def as_tools(self) -> list[BaseTool]:
        return []


@dataclass
class NeedsStoreConfiguration(WorkflowConfiguration):
    store: object


class NeedsStoreWorkflow(Workflow):
    def __init__(self, configuration: NeedsStoreConfiguration):
        super().__init__(configuration)

    def as_tools(self) -> list[BaseTool]:
        return []


class LiveExposeTool(Expose):
    def as_tools(self) -> list[BaseTool]:
        return []

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        @router.post("/live_expose_tool")
        def run_tool() -> dict:
            return {"tool": True}


class FakeAgent:
    name = "fixture_agent"

    @classmethod
    def New(cls) -> FakeAgent:
        return cls()

    def as_api(self, router: APIRouter, **kwargs) -> None:
        @router.post(f"/{self.name}/completion")
        def completion() -> dict:
            return {"ok": True}

        @router.post(f"/{self.name}/stream-completion")
        def stream() -> dict:
            return {"ok": True}


class FakeModule:
    def __init__(
        self,
        *,
        workflows: list | None = None,
        pipelines: list | None = None,
        tools: list | None = None,
    ):
        self.workflows = workflows or []
        self.pipelines = pipelines or []
        self.tools = tools or []


def _openapi_paths(app: FastAPI) -> set[str]:
    return set(TestClient(app).get("/openapi.json").json().get("paths", {}))


def test_live_as_api_appears_in_openapi() -> None:
    workflows_router = APIRouter(prefix="/workflows")
    assert mount_expose_process(
        LiveWorkflow(EchoWorkflowConfiguration()), workflows_router
    )
    app = FastAPI()
    app.include_router(workflows_router)
    assert "/workflows/custom_live" in _openapi_paths(app)


def test_stub_with_live_run_gets_default_post() -> None:
    workflows_router = APIRouter(prefix="/workflows")
    workflow = EchoWorkflow(EchoWorkflowConfiguration())
    assert mount_expose_process(workflow, workflows_router)
    app = FastAPI()
    app.include_router(workflows_router)
    client = TestClient(app)
    paths = set(client.get("/openapi.json").json()["paths"])
    assert "/workflows/echo_workflow" in paths
    response = client.post("/workflows/echo_workflow", json={"text": "hi"})
    assert response.status_code == 200
    assert response.json() == {"echo": "hi"}


def test_stub_without_run_is_not_published() -> None:
    workflows_router = APIRouter(prefix="/workflows")
    assert not mount_expose_process(
        DeadWorkflow(EchoWorkflowConfiguration()), workflows_router
    )
    assert workflows_router.routes == []


def test_pipeline_default_run_serializes_graph() -> None:
    pipelines_router = APIRouter(prefix="/pipelines")
    assert mount_expose_process(
        EchoPipeline(EchoPipelineConfiguration()), pipelines_router
    )
    app = FastAPI()
    app.include_router(pipelines_router)
    client = TestClient(app)
    response = client.post("/pipelines/echo_pipeline", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "turtle"
    assert isinstance(body["data"], str)


def test_langchain_tool_does_not_get_rest() -> None:
    tools_router = APIRouter(prefix="/tools")
    langchain_only = StructuredTool.from_function(
        func=lambda: "nope",
        name="only_langchain",
        description="Agent-internal only",
    )
    mount_module_processes(
        [FakeModule(tools=[langchain_only])],
        workflows_router=APIRouter(prefix="/workflows"),
        pipelines_router=APIRouter(prefix="/pipelines"),
        tools_router=tools_router,
    )
    assert tools_router.routes == []


def test_expose_tool_with_as_api_is_mounted() -> None:
    tools_router = APIRouter(prefix="/tools")
    mount_module_processes(
        [FakeModule(tools=[LiveExposeTool()])],
        workflows_router=APIRouter(prefix="/workflows"),
        pipelines_router=APIRouter(prefix="/pipelines"),
        tools_router=tools_router,
    )
    app = FastAPI()
    app.include_router(tools_router)
    assert "/tools/live_expose_tool" in _openapi_paths(app)


def test_agent_routes_still_exist_beside_processes() -> None:
    agents_router = APIRouter(prefix="/agents")
    workflows_router = APIRouter(prefix="/workflows")
    pipelines_router = APIRouter(prefix="/pipelines")
    tools_router = APIRouter(prefix="/tools")

    FakeAgent.New().as_api(agents_router)
    mount_module_processes(
        [
            FakeModule(
                workflows=[
                    LiveWorkflow(EchoWorkflowConfiguration()),
                    DeadWorkflow(EchoWorkflowConfiguration()),
                ],
                pipelines=[EchoPipeline(EchoPipelineConfiguration())],
                tools=[
                    LiveExposeTool(),
                    StructuredTool.from_function(
                        func=lambda: "nope",
                        name="only_langchain",
                        description="skip",
                    ),
                ],
            )
        ],
        workflows_router=workflows_router,
        pipelines_router=pipelines_router,
        tools_router=tools_router,
    )

    app = FastAPI()
    app.include_router(agents_router)
    if workflows_router.routes:
        app.include_router(workflows_router)
    if pipelines_router.routes:
        app.include_router(pipelines_router)
    if tools_router.routes:
        app.include_router(tools_router)

    paths = _openapi_paths(app)
    assert "/agents/fixture_agent/completion" in paths
    assert "/agents/fixture_agent/stream-completion" in paths
    assert "/workflows/custom_live" in paths
    assert "/pipelines/echo_pipeline" in paths
    assert "/tools/live_expose_tool" in paths
    assert not any("dead_workflow" in path for path in paths)
    assert not any("only_langchain" in path for path in paths)


def test_instantiate_skips_required_config() -> None:
    assert instantiate_process(NeedsStoreWorkflow) is None
    assert isinstance(instantiate_process(EchoWorkflow), EchoWorkflow)


class InheritedRunWorkflow(Workflow):
    """No as_api override. Expose default should POST run()."""

    def run(self, parameters: EchoWorkflowParameters) -> dict:
        return {"echo": parameters.text}

    def as_tools(self) -> list[BaseTool]:
        return []


class PassOnlyWorkflow(Workflow):
    def run(self, parameters: EchoWorkflowParameters) -> dict:  # type: ignore[empty-body]
        pass

    def as_tools(self) -> list[BaseTool]:
        return []


def test_inherited_as_api_posts_live_run() -> None:
    workflows_router = APIRouter(prefix="/workflows")
    workflow = InheritedRunWorkflow(EchoWorkflowConfiguration())
    assert mount_expose_process(workflow, workflows_router)
    app = FastAPI()
    app.include_router(workflows_router)
    client = TestClient(app)
    response = client.post("/workflows/inherited_run_workflow", json={"text": "ok"})
    assert response.status_code == 200
    assert response.json() == {"echo": "ok"}


def test_pass_only_run_is_not_published() -> None:
    workflows_router = APIRouter(prefix="/workflows")
    assert not mount_expose_process(
        PassOnlyWorkflow(EchoWorkflowConfiguration()), workflows_router
    )
    assert workflows_router.routes == []
