import importlib.util
import inspect
import sys
from pathlib import Path

import pytest
from naas_abi_core.pipeline import Pipeline


def get_pipeline_classes():
    """Recursively find all Pipeline classes in the src/data/pipelines directory."""
    pipeline_classes = []
    pipelines_dir = Path("src/data/pipelines")

    for python_file in pipelines_dir.rglob("*.py"):
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

        # Find all Pipeline classes in the module
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and issubclass(obj, Pipeline) and obj != Pipeline:
                pipeline_classes.append((name, obj))

    return pipeline_classes


@pytest.mark.parametrize("class_name,pipeline_class", get_pipeline_classes())
class TestPipelineExpose:
    def test_has_as_tools_method(self, class_name, pipeline_class):
        """Test that the pipeline class implements the as_tools method."""
        assert hasattr(pipeline_class, "as_tools"), (
            f"{class_name} must implement as_tools method"
        )
        method = getattr(pipeline_class, "as_tools")
        assert callable(method), f"{class_name}.as_tools must be callable"

    def test_has_as_api_method(self, class_name, pipeline_class):
        """Test that the pipeline class implements the as_api method."""
        assert hasattr(pipeline_class, "as_api"), (
            f"{class_name} must implement as_api method"
        )
        method = getattr(pipeline_class, "as_api")
        assert callable(method), f"{class_name}.as_api must be callable"
