"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys

import pytest

from {{module_name_snake}} import MODULE_ID, ABIModule
from {{module_name_snake}}.__main__ import configuration_from, run_until_signalled, token_from
from {{module_name_snake}}.agents.{{module_name_pascal}}Agent import NAME


def test_the_module_declares_its_agent_services_and_job() -> None:
    assert ABIModule.module_id == MODULE_ID
    assert [agent.name for agent in ABIModule.agents] == [NAME]
    assert "agent.invoke.v1" in ABIModule.agents[0].capabilities
    assert set(ABIModule.dependencies.services) == {"model_registry", "document"}
    (heartbeat,) = ABIModule.jobs
    assert heartbeat.name == "heartbeat"
    assert [trigger.spec for trigger in heartbeat.triggers] == ["1h"]


def test_the_configuration_comes_from_the_environment() -> None:
    assert configuration_from({}).chat_model == ""
    assert (
        configuration_from({"{{module_name_upper}}_CHAT_MODEL": "m"}).chat_model == "m"
    )


def test_the_module_never_imports_abi_core() -> None:
    """A remote module reaches the engine only through NATS."""
    code = (
        "import sys, {{module_name_snake}}, {{module_name_snake}}.__main__; "
        "core = [m for m in sys.modules if m.split('.')[0] == 'naas_abi_core']; "
        "sys.exit(f'imports {core[0]}' if core else 0)"
    )
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_the_module_calls_the_engine_as_its_module_id() -> None:
    """Discovery registers a module only under a token for its own module id."""
    assert token_from({"ABI_SERVICE_TOKEN": "issued", "ABI_MODULE_KEY": "k"}) == "issued"
    assert token_from({"ABI_MODULE_KEY": "k"}).identity == MODULE_ID
    with pytest.raises(RuntimeError, match="ABI_MODULE_KEY"):
        token_from({})


def test_sigterm_cancels_the_module_before_it_runs() -> None:
    async def scenario() -> object:
        started = asyncio.Event()

        async def starting() -> str:
            started.set()
            await asyncio.Event().wait()
            return "never"

        task = asyncio.ensure_future(run_until_signalled(starting()))
        await started.wait()
        os.kill(os.getpid(), signal.SIGTERM)
        return await task

    assert asyncio.run(scenario()) is None
