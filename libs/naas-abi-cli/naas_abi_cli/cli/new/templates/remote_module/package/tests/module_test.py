"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import signal
import subprocess
import sys

import pytest
from naas_abi_sdk.workflows import InvalidWorkflowInput

from {{module_name_snake}} import MODULE_ID, ABIModule, jobs
from {{module_name_snake}}.__main__ import configuration_from, run_until_signalled, token_from
from {{module_name_snake}}.agents.{{module_name_pascal}}Agent import NAME


def test_the_module_declares_its_agent_services_job_and_workflow() -> None:
    assert ABIModule.module_id == MODULE_ID
    assert [agent.name for agent in ABIModule.agents] == [NAME]
    assert "agent.invoke.v1" in ABIModule.agents[0].capabilities
    assert set(ABIModule.dependencies.services) == {"model_registry", "document"}
    heartbeat, digest = ABIModule.jobs
    assert heartbeat.name == "heartbeat" and heartbeat.kind == "job"
    assert [trigger.spec for trigger in heartbeat.triggers] == ["1h"]
    # A workflow is a job with a kind and JSON Schemas, from its annotations.
    assert digest.name == "digest" and digest.kind == "workflow"
    assert json.loads(digest.input_schema)["properties"]["topic"]["default"] == "news"
    assert set(json.loads(digest.output_schema)["required"]) == {"topic", "items", "summary"}
    # The schedule carries an input: it is the run's payload.
    assert digest.triggers[0].input == {"topic": "news"}


class InlineFlow:
    """Stands in for ``FlowContext``: each step runs once and nothing is journaled.

    The SDK's own tests cover the journal (replay, retries, child runs); this
    checks what the module does with the context."""

    def __init__(self, payload: dict) -> None:
        self.payload, self.attempt, self.keys, self.logs = payload, 1, [], []

    async def step(self, key: str, fn, *args, **kwargs):
        kwargs.pop("retries", None)
        self.keys.append(key)
        value = fn(*args, **kwargs)
        return await value if inspect.isawaitable(value) else value

    async def map(self, key: str, items, fn, **kwargs):
        self.keys.append(key)
        return [await self.step(f"{key}[{i}]", fn, item) for i, item in enumerate(items)]

    def log(self, message: str) -> None:
        self.logs.append(message)


def test_the_digest_workflow_validates_its_input_and_runs_its_steps() -> None:
    handler = ABIModule.__new__(ABIModule)._job_handlers["digest"]
    flow = InlineFlow({"topic": "db", "limit": 2})

    output = asyncio.run(handler(flow))

    # The handler returns the output as JSON, as the run record keeps it.
    assert output == {
        "topic": "db",
        "items": 2,
        "summary": "2 items about db, 18 characters",
    }
    assert flow.keys == ["collect", "measure", "measure[0]", "measure[1]", "summarize"]
    assert "attempt 1" in flow.logs[0]
    # What a schedule without an input delivers is valid: the defaults apply.
    assert asyncio.run(handler(InlineFlow({})))["items"] == 3
    # An invalid input fails the run without a retry.
    with pytest.raises(InvalidWorkflowInput, match="limit"):
        asyncio.run(handler(InlineFlow({"limit": 0})))
    assert jobs.measure("abcd") == 4


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
    # The key wins over an issued token: it signs fresh ones, bound to the module called.
    assert token_from({"ABI_SERVICE_TOKEN": "issued", "ABI_MODULE_KEY": "k"}).identity == MODULE_ID
    assert token_from({"ABI_SERVICE_TOKEN": "issued"}) == "issued"
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
