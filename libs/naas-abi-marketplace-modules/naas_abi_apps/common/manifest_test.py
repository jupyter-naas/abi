"""Every application submits a permission manifest the SDK can build: the
broker admits a module only with the subjects of its approved manifest."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from naas_abi_sdk.permissions import module_manifest

APPS = sorted(
    p.name
    for p in Path(__file__).resolve().parents[1].iterdir()
    if (p / "__main__.py").is_file()
)


@pytest.mark.parametrize("app", APPS)
def test_the_manifest_covers_the_declared_services(app: str) -> None:
    module = importlib.import_module(f"naas_abi_apps.{app}").ABIModule
    actions = {a for s in module_manifest(module)["statements"] for a in s["actions"]}
    services = {a.split(":", 1)[0] for a in actions}
    assert set(module.get_dependencies().services) <= services
