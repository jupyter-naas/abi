"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys

import pytest

from {{module_name_snake}} import MODULE_ID, ABIModule
from {{module_name_snake}}.__main__ import configuration_from, main, run_until_signalled
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


def test_the_module_needs_its_service_key() -> None:
    # It holds a key, never a signing secret: no key, no start.
    for env in ({}, {"ABI_SERVICE_KEY": "a-token"}):
        with pytest.raises(SystemExit, match="ABI_SERVICE_KEY"):
            main(env)


def test_its_manifest_defaults_from_its_dependencies() -> None:
    from naas_abi_sdk.permissions import module_manifest

    actions = {a for s in module_manifest(ABIModule)["statements"] for a in s["actions"]}
    assert {"document:*", "model_registry:*"} <= actions


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


def test_a_module_that_never_gets_ready_says_so(monkeypatch, caplog) -> None:
    """Not READY (discovery down, a wrong key): run() logs it, not a silent wait."""
    import logging

    import {{module_name_snake}} as package

    monkeypatch.setattr(package, "NOT_READY_NOTICE_SECONDS", 0.05)
    module = ABIModule.__new__(ABIModule)
    module._discovery_session = None  # no engine: discovery is off

    async def scenario() -> None:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(module.run(), 0.3)

    with caplog.at_level(logging.WARNING, logger=package.__name__):
        asyncio.run(scenario())
    assert f"{MODULE_ID} not READY" in caplog.text
