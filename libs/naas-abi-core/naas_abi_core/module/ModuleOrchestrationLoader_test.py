"""Orchestration discovery when the legacy Dagster extra is missing."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest
from naas_abi_core.module.ModuleOrchestrationLoader import ModuleOrchestrationLoader

_PLAIN = textwrap.dedent(
    """
    from naas_abi_core.orchestrations.Orchestrations import Orchestrations


    class PlainOrchestration(Orchestrations):
        @classmethod
        def New(cls):
            return cls()
    """
).strip()

# A module's orchestration that imports Dagster itself, as the marketplace's do.
_DAGSTER_AT_IMPORT = textwrap.dedent(
    """
    import dagster as dg
    from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration


    class EagerOrchestration(DagsterOrchestration):
        @classmethod
        def New(cls):
            return cls(definitions=dg.Definitions())
    """
).strip()

# Imports only DagsterOrchestration, which loads without Dagster.
_DAGSTER_IN_NEW = textwrap.dedent(
    """
    from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration


    class LazyOrchestration(DagsterOrchestration):
        pass
    """
).strip()


def _make_module(tmp_path: Path, name: str, files: dict[str, str]) -> type:
    package = tmp_path / name
    (package / "orchestrations").mkdir(parents=True)
    (package / "__init__.py").write_text("class FakeModule:\n    pass\n")
    (package / "orchestrations" / "__init__.py").write_text("")
    for filename, content in files.items():
        (package / "orchestrations" / filename).write_text(content)
    sys.path.insert(0, str(tmp_path))
    return __import__(name, fromlist=["FakeModule"]).FakeModule


@pytest.fixture
def without_dagster(monkeypatch):
    # None in sys.modules makes `import dagster` raise ModuleNotFoundError
    # (name="dagster"), as in an install without the extra.
    monkeypatch.setitem(sys.modules, "dagster", None)


def _names(found: list[type]) -> list[str]:
    return sorted(item.__name__ for item in found)


def test_without_dagster_only_dagster_orchestrations_importing_it_are_left_out(
    tmp_path: Path, without_dagster
) -> None:
    cls = _make_module(
        tmp_path,
        "pkg_orch_nodagster",
        {
            "Plain.py": _PLAIN,
            "Eager.py": _DAGSTER_AT_IMPORT,
            "Lazy.py": _DAGSTER_IN_NEW,
        },
    )

    found = ModuleOrchestrationLoader.load_orchestrations(cls)

    assert _names(found) == ["LazyOrchestration", "PlainOrchestration"]


def test_with_dagster_every_orchestration_loads(tmp_path: Path) -> None:
    pytest.importorskip("dagster")
    cls = _make_module(
        tmp_path,
        "pkg_orch_dagster",
        {"Plain.py": _PLAIN, "Eager.py": _DAGSTER_AT_IMPORT},
    )

    found = ModuleOrchestrationLoader.load_orchestrations(cls)

    assert _names(found) == ["EagerOrchestration", "PlainOrchestration"]


def test_another_missing_module_still_fails_the_load(tmp_path: Path) -> None:
    cls = _make_module(
        tmp_path,
        "pkg_orch_broken",
        {"Broken.py": "import this_module_does_not_exist\n"},
    )

    with pytest.raises(ModuleNotFoundError, match="this_module_does_not_exist"):
        ModuleOrchestrationLoader.load_orchestrations(cls)
