"""Component names, and the workflow base classes without their extras.

No pydantic, rdflib or LangChain is needed to run these: the extras are blocked in
a subprocess, so they pass (and mean the same) whatever is installed.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import pytest

from naas_abi_sdk.components import component_slug


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("GreetWorkflow", "greet_workflow"),
        ("HTTPServerPipeline", "http_server_pipeline"),
        ("Sync2Cloud", "sync2_cloud"),
        ("lower", "lower"),
    ],
)
def test_the_name_is_a_stable_slug_of_the_class_name(name, slug):
    assert component_slug(name) == slug


@pytest.mark.parametrize("name", ["Étoile", "X" * 80, "1abc"])
def test_a_class_name_that_is_not_a_subject_token_is_refused(name):
    with pytest.raises(ValueError, match="NATS subject token"):
        component_slug(name)


# --- the extras ----------------------------------------------------------------

_BLOCK = "import sys\nfor name in {blocked!r}:\n    sys.modules[name] = None\n"


def python(code: str, *blocked: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
    return subprocess.run(
        [sys.executable, "-c", _BLOCK.format(blocked=blocked) + textwrap.dedent(code)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_package_and_module_import_without_pydantic_rdflib_or_langchain():
    result = python(
        """
        import naas_abi_sdk, naas_abi_sdk.module, naas_abi_sdk.integration
        from naas_abi_sdk import BaseModule, Integration

        class M(BaseModule):
            pass

        assert M.get_workflow_classes() == {} and M.get_pipeline_classes() == {}
        """,
        "pydantic",
        "rdflib",
        "langchain_core",
    )
    assert result.returncode == 0, result.stderr


def test_a_missing_pydantic_names_the_workflows_extra():
    result = python("from naas_abi_sdk import Workflow", "pydantic")
    assert result.returncode != 0
    assert "ImportError" in result.stderr
    assert "naas-abi-sdk[workflows]" in result.stderr


def test_a_missing_rdflib_names_the_rdf_extra_but_workflows_still_import():
    result = python("from naas_abi_sdk import Pipeline", "rdflib")
    assert result.returncode != 0 and "naas-abi-sdk[workflows,rdf]" in result.stderr
    assert python("from naas_abi_sdk import Workflow", "rdflib").returncode == 0


def test_a_missing_langchain_names_the_agents_extra_only_when_as_tools_is_called():
    result = python(
        """
        from naas_abi_sdk import Workflow

        class W(Workflow):
            pass

        w = W(None)
        try:
            w.as_tools()
        except ImportError as exc:
            print(exc)
        """,
        "langchain_core",
    )
    assert result.returncode == 0, result.stderr
    assert "naas-abi-sdk[agents]" in result.stdout


def test_a_workflows_folder_without_pydantic_names_the_extra(tmp_path):
    package = tmp_path / "no_pydantic_pkg"
    (package / "workflows").mkdir(parents=True)
    (package / "__init__.py").write_text(
        "from naas_abi_sdk import BaseModule\n\n\nclass ABIModule(BaseModule):\n    pass\n"
    )
    (package / "workflows" / "greet.py").write_text(
        "from naas_abi_sdk.workflow import Workflow\n\n\nclass Greet(Workflow):\n    pass\n"
    )
    result = python(
        f"""
        import sys
        sys.path.insert(0, {str(tmp_path)!r})
        from no_pydantic_pkg import ABIModule
        try:
            ABIModule.get_workflow_classes()
        except ImportError as exc:
            print(exc)
        """,
        "pydantic",
    )
    assert result.returncode == 0, result.stderr
    assert "naas-abi-sdk[workflows]" in result.stdout


def test_an_empty_workflows_folder_needs_no_extra(tmp_path):
    package = tmp_path / "empty_pkg"
    (package / "workflows").mkdir(parents=True)
    (package / "workflows" / "AGENTS.md").write_text("# workflows\n")
    (package / "__init__.py").write_text(
        "from naas_abi_sdk import BaseModule\n\n\nclass ABIModule(BaseModule):\n    pass\n"
    )
    result = python(
        f"""
        import sys
        sys.path.insert(0, {str(tmp_path)!r})
        from empty_pkg import ABIModule
        assert ABIModule.get_workflow_classes() == {{}}
        """,
        "pydantic",
        "rdflib",
    )
    assert result.returncode == 0, result.stderr
