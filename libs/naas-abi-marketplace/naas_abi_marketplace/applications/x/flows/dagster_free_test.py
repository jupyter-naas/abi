"""The NATS path must not need Dagster, a legacy extra: nothing in ``flows/`` imports it."""

from __future__ import annotations

import subprocess
import sys

CODE = """
import importlib, sys
sys.modules["dagster"] = None  # an import of it now raises ImportError
for name in (
    "x", "x.flows.common", "x.flows.envelopes", "x.flows.maintenance", "x.flows.search",
    "x.flows.mapping", "x.flows.reprocess", "x.flows.count", "x.flows.guard",
    "x.flows.triggers", "x.apps.x_proxy.build",
):
    importlib.import_module(
        "naas_abi_marketplace.applications." + name
    )
print("ok")
"""


def test_the_flows_and_the_module_import_without_dagster():
    result = subprocess.run(
        [sys.executable, "-c", CODE],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip() == "ok"
