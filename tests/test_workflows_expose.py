import importlib.util
import inspect
import sys
from pathlib import Path

import pytest
from naas_abi_core.workflow import Workflow


def get_workflow_classes():
    """Recursively find all Workflow classes in the src/workflows directory."""
    workflow_classes = []
    workflows_dir = Path("src/workflows")

    for python_file in workflows_dir.rglob("*.py"):
        if python_file.name.startswith("__"):
            continue

        # Import the module
        module_name = str(python_file).replace("/", ".").replace(".py", "")
        spec = importlib.util.spec_from_file_location(module_name, python_file)
        if not spec or not spec.loader:
            continue

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # Find all Workflow classes in the module
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and issubclass(obj, Workflow) and obj != Workflow:
                workflow_classes.append((name, obj))

    return workflow_classes


@pytest.mark.parametrize("class_name,workflow_class", get_workflow_classes())
class TestWorkflowExpose:
    def test_has_run_method(self, class_name, workflow_class):
        """Test that the workflow class implements the run method."""
        # Check that run is defined directly on the class, not inherited
        assert "run" in workflow_class.__dict__, (
            f"{class_name} must implement its own run method, not inherit it"
        )
        method = getattr(workflow_class, "run")
        assert callable(method), f"{class_name}.run must be callable"

    def test_has_api_function(self, class_name, workflow_class):
        """Test that the workflow module has an api function."""
        # Check that as_api is defined directly on the class, not inherited
        assert "as_api" in workflow_class.__dict__, (
            f"{class_name} must implement its own as_api method, not inherit it"
        )
        function = getattr(workflow_class, "as_api")
        assert callable(function), f"{class_name}'s as_api must be callable"

    def test_has_as_tools_function(self, class_name, workflow_class):
        """Test that the workflow module has an as_tools function."""
        # Check that as_tools is defined directly on the class, not inherited
        assert "as_tools" in workflow_class.__dict__, (
            f"{class_name} must implement its own as_tools method, not inherit it"
        )
        function = getattr(workflow_class, "as_tools")
        assert callable(function), f"{class_name}'s as_tools must be callable"
