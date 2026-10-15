"""`abi new pipeline` creates a pipeline module that imports and subclasses Pipeline."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from naas_abi_core.pipeline import Pipeline

from naas_abi_cli.cli.new.pipeline import new_pipeline


def test_a_new_pipeline_imports(tmp_path: Path) -> None:
    """`Pipeline` is not generic: `Pipeline[...]` failed at import, so the module
    never loaded."""
    new_pipeline("echo", str(tmp_path))
    (path,) = tmp_path.glob("*Pipeline.py")

    spec = importlib.util.spec_from_file_location("generated_echo_pipeline", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[spec.name]

    assert issubclass(module.EchoPipeline, Pipeline)
