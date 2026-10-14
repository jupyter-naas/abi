import sys

import pytest
from naas_abi.orchestrations.DemoOrchestration import DemoOrchestration
from naas_abi_core.utils.LegacyExtras import MissingLegacyExtra


def test_new_builds_empty_definitions() -> None:
    dagster = pytest.importorskip("dagster")

    assert isinstance(DemoOrchestration.New().definitions, dagster.Definitions)


def test_new_without_dagster_says_what_to_install(monkeypatch) -> None:
    # The class itself imported above without touching Dagster.
    monkeypatch.setitem(sys.modules, "dagster", None)

    with pytest.raises(MissingLegacyExtra, match=r"naas-abi-core\[dagster\]"):
        DemoOrchestration.New()
