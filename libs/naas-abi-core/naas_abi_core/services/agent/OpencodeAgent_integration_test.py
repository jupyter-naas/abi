import os

import pytest

from naas_abi_core.services.agent.OpencodeAgent import (
    OpencodeAgent,
    OpencodeAgentConfiguration,
)


@pytest.mark.integration
def test_opencode_agent_start_stop_with_real_server(tmp_path):
    if os.getenv("RUN_OPENCODE_INTEGRATION", "false").lower() != "true":
        pytest.skip("Set RUN_OPENCODE_INTEGRATION=true to run this test")

    agent = OpencodeAgent(
        configuration=OpencodeAgentConfiguration(
            workdir=str(tmp_path),
            port=14096,
            name="test-agent",
            description="Test agent",
            startup_timeout=30,
        )
    )

    agent.start()
    agent.stop()
