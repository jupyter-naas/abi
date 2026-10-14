"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import signal
import subprocess
import sys

import pytest

from {{module_name_snake}} import MODULE_ID, ABIModule
from {{module_name_snake}}.__main__ import configuration_from, run_until_signalled
from {{module_name_snake}}.agents.{{module_name_pascal}}Agent import NAME
from {{module_name_snake}}.service_token import ServiceToken, token_source


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


def _claims(token: str) -> dict:
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def test_the_signed_token_has_the_engine_claims() -> None:
    token = ServiceToken("{{module_name}}", "s" * 48, clock=lambda: 1000.0)()

    header, payload, signature = token.split(".")
    expected = hmac.new(
        b"s" * 48, f"{header}.{payload}".encode(), hashlib.sha256
    ).digest()
    assert base64.urlsafe_b64encode(expected).rstrip(b"=").decode() == signature
    assert _claims(token) == {"sub": "{{module_name}}", "iat": 1000, "exp": 4600}


def test_the_token_is_refreshed_at_half_its_lifetime() -> None:
    now = [1000.0]
    token = ServiceToken("{{module_name}}", "s" * 48, clock=lambda: now[0])
    first = token()
    now[0] += 1799
    assert token() == first
    now[0] += 1
    assert _claims(token())["iat"] == 2800


def test_an_issued_token_wins_over_signing() -> None:
    env = {"ABI_SERVICE_TOKEN": "issued", "NATS_JWT_SECRET": "s" * 48}
    assert token_source(env, "{{module_name}}") == "issued"
    assert isinstance(token_source({"NATS_JWT_SECRET": "s" * 48}, "x"), ServiceToken)
    with pytest.raises(RuntimeError, match="NATS_JWT_SECRET"):
        token_source({}, "x")


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
