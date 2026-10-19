"""``internal_call`` and ``own_storage`` stay inside core (they run as the engine).

``catalog_maintenance`` (core, typed to a dataset) is the one entry a module gets."""

from __future__ import annotations

from pathlib import Path

LIBS = Path(__file__).resolve().parents[4]


def test_nothing_outside_core_imports_the_engine_helpers():
    offenders = []
    for lib in ("naas-abi", "naas-abi-cli", "naas-abi-marketplace"):
        for path in (LIBS / lib).rglob("*.py"):
            if (
                path.name.endswith("_test.py")
                or path.name.startswith("test_")
                or "tests" in path.parts
                or ".venv" in path.parts
                or "node_modules" in path.parts
            ):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "internal_call" in text or "own_storage" in text:
                offenders.append(str(path.relative_to(LIBS)))
    assert not offenders, f"use a narrow entry point instead: {offenders}"
