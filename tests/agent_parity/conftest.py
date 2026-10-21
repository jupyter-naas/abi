from __future__ import annotations

import pytest

from tests.agent_parity.harness import CoreRunner, SdkRunner


@pytest.fixture(params=[CoreRunner, SdkRunner], ids=lambda r: r.name)
def runner(request):
    """Every parity scenario runs once per agent runtime."""
    return request.param()
