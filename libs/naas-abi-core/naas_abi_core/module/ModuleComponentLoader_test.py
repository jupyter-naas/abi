"""Discovery tests for workflows, pipelines, and module tools."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from naas_abi_core.module.ModulePipelineLoader import ModulePipelineLoader
from naas_abi_core.module.ModuleToolLoader import ModuleToolLoader
from naas_abi_core.module.ModuleWorkflowLoader import ModuleWorkflowLoader

_WORKFLOW = textwrap.dedent(
    """
    from dataclasses import dataclass
    from langchain_core.tools import BaseTool
    from naas_abi_core.workflow import Workflow, WorkflowConfiguration
    from naas_abi_core.workflow.workflow import WorkflowParameters


    @dataclass
    class EchoWorkflowConfiguration(WorkflowConfiguration):
        pass


    class EchoWorkflowParameters(WorkflowParameters):
        text: str = "ok"


    class EchoWorkflow(Workflow):
        def run(self, parameters: EchoWorkflowParameters) -> dict:
            return {"echo": parameters.text}

        def as_tools(self) -> list[BaseTool]:
            return []
    """
).strip()

_PIPELINE = textwrap.dedent(
    """
    from dataclasses import dataclass
    from langchain_core.tools import BaseTool
    from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
    from rdflib import Graph


    @dataclass
    class EchoPipelineConfiguration(PipelineConfiguration):
        pass


    class EchoPipelineParameters(PipelineParameters):
        text: str = "ok"


    class EchoPipeline(Pipeline):
        def run(self, parameters: EchoPipelineParameters) -> Graph:
            return Graph()

        def as_tools(self) -> list[BaseTool]:
            return []
    """
).strip()

_EXPOSE_TOOL = textwrap.dedent(
    """
    from enum import Enum
    from fastapi import APIRouter
    from langchain_core.tools import BaseTool
    from naas_abi_core.utils.Expose import Expose


    class FixtureExposeTool(Expose):
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
            @router.post("/fixture_expose_tool")
            def run_tool() -> dict:
                return {"ok": True}
    """
).strip()


def _make_module(tmp_path: Path, name: str, layout: dict[str, str]) -> type:
    pkg = tmp_path / name
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        textwrap.dedent(
            """
            class FakeModule:
                pass
            """
        ).strip()
    )
    for relpath, content in layout.items():
        dest = pkg / relpath
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
        current = dest.parent
        while current != pkg:
            init = current / "__init__.py"
            if not init.exists():
                init.write_text("")
            current = current.parent

    sys.path.insert(0, str(tmp_path))
    imported = __import__(name, fromlist=["FakeModule"])
    return imported.FakeModule


def test_workflow_loader_finds_class_in_workflows(tmp_path: Path) -> None:
    cls = _make_module(
        tmp_path,
        "pkg_wf",
        {"workflows/EchoWorkflow.py": _WORKFLOW},
    )
    found = ModuleWorkflowLoader.load_workflows(cls)
    assert [item.__name__ for item in found] == ["EchoWorkflow"]


def test_pipeline_loader_walks_nested_package(tmp_path: Path) -> None:
    cls = _make_module(
        tmp_path,
        "pkg_pipe",
        {"pipelines/nested/EchoPipeline.py": _PIPELINE},
    )
    found = ModulePipelineLoader.load_pipelines(cls)
    assert [item.__name__ for item in found] == ["EchoPipeline"]


def test_loaders_skip_test_modules(tmp_path: Path) -> None:
    cls = _make_module(
        tmp_path,
        "pkg_skip",
        {
            "workflows/EchoWorkflow.py": _WORKFLOW,
            "workflows/EchoWorkflow_test.py": _WORKFLOW.replace(
                "EchoWorkflow", "TestOnlyWorkflow"
            ),
        },
    )
    found = ModuleWorkflowLoader.load_workflows(cls)
    assert [item.__name__ for item in found] == ["EchoWorkflow"]


def test_tool_loader_finds_expose_in_tools(tmp_path: Path) -> None:
    cls = _make_module(
        tmp_path,
        "pkg_tool",
        {"tools/FixtureExposeTool.py": _EXPOSE_TOOL},
    )
    found = ModuleToolLoader.load_tools(cls)
    assert [item.__name__ for item in found] == ["FixtureExposeTool"]


def test_import_failure_does_not_abort_sibling_files(tmp_path: Path) -> None:
    cls = _make_module(
        tmp_path,
        "pkg_broken",
        {
            "workflows/broken.py": "import this_module_does_not_exist\n",
            "workflows/EchoWorkflow.py": _WORKFLOW,
        },
    )
    found = ModuleWorkflowLoader.load_workflows(cls)
    assert [item.__name__ for item in found] == ["EchoWorkflow"]


def test_missing_folder_returns_empty(tmp_path: Path) -> None:
    cls = _make_module(tmp_path, "pkg_empty", {})
    assert ModuleWorkflowLoader.load_workflows(cls) == []
    assert ModulePipelineLoader.load_pipelines(cls) == []
    assert ModuleToolLoader.load_tools(cls) == []
