"""Tests for EngineModuleLoader's model-provider detection.

The detector is a filesystem-level scan: a module "ships models" iff its
``models/`` package contains at least one ``.py`` source file that
references ``ModelDefinition``. This is what lets ``Engine.load`` expand a
narrow ``module_names`` (e.g. ``abi chat <module> <agent>``) with the AI
provider modules required for the model registry's configured defaults to
resolve.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from naas_abi_core.engine.engine_loaders.EngineModuleLoader import (
    EngineModuleLoader,
)


def _write_pkg(root: Path, dotted: str, body: str = "") -> Path:
    pkg_dir = root.joinpath(*dotted.split("."))
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text(body)
    return pkg_dir


def _install(root: Path, monkeypatch) -> None:
    """Put ``root`` on sys.path and clear any cached entries for our test
    package names so importlib.find_spec hits the fresh copy."""
    monkeypatch.syspath_prepend(str(root))
    for name in list(sys.modules):
        if name.startswith("eng_module_loader_test_pkg"):
            del sys.modules[name]


def test_ships_model_definitions_true_when_models_dir_contains_ref(
    tmp_path: Path, monkeypatch
) -> None:
    pkg = _write_pkg(tmp_path, "eng_module_loader_test_pkg.with_models")
    models = pkg / "models"
    models.mkdir()
    (models / "__init__.py").write_text("")
    (models / "thing.py").write_text(
        textwrap.dedent(
            """
            from naas_abi_core.models.Model import ModelDefinition

            class Thing(ModelDefinition):
                pass
            """
        )
    )
    _install(tmp_path, monkeypatch)

    assert EngineModuleLoader._module_ships_model_definitions(
        "eng_module_loader_test_pkg.with_models"
    )


def test_ships_model_definitions_false_when_models_dir_lacks_ref(
    tmp_path: Path, monkeypatch
) -> None:
    # Mimics ``domains/*/models`` which exists but ships pydantic schemas,
    # not ``ModelDefinition`` subclasses.
    pkg = _write_pkg(tmp_path, "eng_module_loader_test_pkg.without_ref")
    models = pkg / "models"
    models.mkdir()
    (models / "schema.py").write_text(
        "from pydantic import BaseModel\nclass Schema(BaseModel): pass\n"
    )
    _install(tmp_path, monkeypatch)

    assert not EngineModuleLoader._module_ships_model_definitions(
        "eng_module_loader_test_pkg.without_ref"
    )


def test_ships_model_definitions_false_when_no_models_dir(
    tmp_path: Path, monkeypatch
) -> None:
    _write_pkg(tmp_path, "eng_module_loader_test_pkg.no_dir")
    _install(tmp_path, monkeypatch)

    assert not EngineModuleLoader._module_ships_model_definitions(
        "eng_module_loader_test_pkg.no_dir"
    )


def test_ships_model_definitions_false_for_unknown_module() -> None:
    # Missing modules must return False rather than raise — the caller
    # treats this as "doesn't ship models" and proceeds.
    assert not EngineModuleLoader._module_ships_model_definitions(
        "eng_module_loader_test_pkg.does_not_exist_xyz"
    )


def test_ships_model_definitions_skips_init_and_test_files(
    tmp_path: Path, monkeypatch
) -> None:
    # Even if ``__init__.py`` or ``*_test.py`` mention ModelDefinition, they
    # must not flip the detector on — only real model source files count.
    pkg = _write_pkg(tmp_path, "eng_module_loader_test_pkg.only_excluded")
    models = pkg / "models"
    models.mkdir()
    (models / "__init__.py").write_text("# references ModelDefinition\n")
    (models / "thing_test.py").write_text("# references ModelDefinition\n")
    _install(tmp_path, monkeypatch)

    assert not EngineModuleLoader._module_ships_model_definitions(
        "eng_module_loader_test_pkg.only_excluded"
    )
