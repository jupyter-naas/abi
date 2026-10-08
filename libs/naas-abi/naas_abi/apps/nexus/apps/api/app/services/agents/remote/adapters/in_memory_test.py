from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.adapters.in_memory import (
    InMemoryRemoteAgentDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.contracts import (
    RESEARCHER,
    RemoteAgentDirectoryContract,
)


@pytest.fixture
def directory():
    async def answer(prompt: str, thread_id: str) -> str:
        return f"fact: {prompt}"

    return InMemoryRemoteAgentDirectory({RESEARCHER: answer})


class TestInMemoryRemoteAgentDirectory(RemoteAgentDirectoryContract):
    pass
