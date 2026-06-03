"""Tests for EngineModuleLoader's model-provider detection.

A module is considered model-providing iff its package contains a
``models/`` directory with at least one ``.py`` source file other than
``__init__.py`` and ``*_test.py``. This is what lets ``Engine.load``
expand a narrow ``module_names`` (e.g. ``abi chat <module> <agent>``)
with the modules required for the model registry's configured defaults
to resolve.
"""

from __future__ import annotations

import sys
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


def test_ships_models_true_when_models_dir_has_source_file(
    tmp_path: Path, monkeypatch
) -> None:
    pkg = _write_pkg(tmp_path, "eng_module_loader_test_pkg.with_models")
    models = pkg / "models"
    models.mkdir()
    (models / "__init__.py").write_text("")
    (models / "thing.py").write_text("# anything\n")
    _install(tmp_path, monkeypatch)

    assert EngineModuleLoader._module_ships_models(
        "eng_module_loader_test_pkg.with_models"
    )


def test_ships_models_false_when_models_dir_only_has_init(
    tmp_path: Path, monkeypatch
) -> None:
    pkg = _write_pkg(tmp_path, "eng_module_loader_test_pkg.only_init")
    models = pkg / "models"
    models.mkdir()
    (models / "__init__.py").write_text("")
    _install(tmp_path, monkeypatch)

    assert not EngineModuleLoader._module_ships_models(
        "eng_module_loader_test_pkg.only_init"
    )


def test_ships_models_false_when_models_dir_only_has_tests(
    tmp_path: Path, monkeypatch
) -> None:
    # ``ModuleModelLoader`` filters ``*_test.py`` out at on_load time, so
    # the detector mirrors that — a tests-only models/ dir doesn't count
    # as shipping a model.
    pkg = _write_pkg(tmp_path, "eng_module_loader_test_pkg.only_tests")
    models = pkg / "models"
    models.mkdir()
    (models / "__init__.py").write_text("")
    (models / "thing_test.py").write_text("# a test\n")
    _install(tmp_path, monkeypatch)

    assert not EngineModuleLoader._module_ships_models(
        "eng_module_loader_test_pkg.only_tests"
    )


def test_ships_models_false_when_no_models_dir(
    tmp_path: Path, monkeypatch
) -> None:
    _write_pkg(tmp_path, "eng_module_loader_test_pkg.no_dir")
    _install(tmp_path, monkeypatch)

    assert not EngineModuleLoader._module_ships_models(
        "eng_module_loader_test_pkg.no_dir"
    )


def test_ships_models_false_for_unknown_module() -> None:
    # Missing modules must return False rather than raise — the caller
    # treats this as "doesn't ship models" and proceeds.
    assert not EngineModuleLoader._module_ships_models(
        "eng_module_loader_test_pkg.does_not_exist_xyz"
    )
