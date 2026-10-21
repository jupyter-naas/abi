"""Session hooks for the SDK tests.

With ``ABI_REQUIRE_NATS_SERVER=1`` (set in CI), a test skipped because
nats-server is missing fails instead, so a broker suite cannot pass silently.
Mirrors ``naas_abi_core.engine.nats_test_server.pytest_runtest_makereport``:
the SDK stays core-free, so change them together.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import Any

import pytest

REQUIRE_NATS_SERVER = "ABI_REQUIRE_NATS_SERVER"


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Fail a skip whose reason names nats-server when the broker is required."""
    report = yield
    if (
        report.skipped
        and not hasattr(report, "wasxfail")
        and os.environ.get(REQUIRE_NATS_SERVER) == "1"
    ):
        longrepr: Any = report.longrepr
        reason = str(longrepr[2] if isinstance(longrepr, tuple) else longrepr)
        if "nats-server" in reason:
            report.outcome = "failed"
            report.longrepr = (
                f"{REQUIRE_NATS_SERVER}=1 requires nats-server, "
                f"but this test was skipped: {reason}"
            )
    return report
