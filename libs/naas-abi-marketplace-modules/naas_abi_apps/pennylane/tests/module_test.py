"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import os
import subprocess
import sys

from naas_abi_apps.common.runtime import configuration_from, token_from
from naas_abi_apps.pennylane import MODULE_ID, ABIModule
from naas_abi_apps.pennylane.__main__ import ENV_PREFIX
from naas_abi_apps.pennylane.agents.PennylaneAgent import NAME, tools_for


def test_the_module_declares_its_agent_and_services() -> None:
    assert ABIModule.module_id == MODULE_ID == "applications.pennylane"
    assert [agent.name for agent in ABIModule.agents] == [NAME]
    assert "agent.invoke.v1" in ABIModule.agents[0].capabilities
    assert set(ABIModule.dependencies.services) == {
        "model_registry",
        "document",
        "secret",
        "object_storage",
    }


def test_the_configuration_comes_from_the_environment() -> None:
    default = configuration_from(ABIModule.Configuration, ENV_PREFIX, {})
    assert default.api_key_secret == "PENNYLANE_API_KEY"
    assert default.datastore_path == "pennylane"
    assert default.chat_model == ""
    configured = configuration_from(
        ABIModule.Configuration,
        ENV_PREFIX,
        {"PENNYLANE_CHAT_MODEL": "m", "PENNYLANE_DATASTORE_PATH": "acme/pennylane"},
    )
    assert (configured.chat_model, configured.datastore_path) == ("m", "acme/pennylane")


def test_no_api_key_means_no_tools() -> None:
    assert tools_for(None) == []
    assert tools_for("") == []
    assert len(tools_for("token")) == 4


def test_the_module_calls_the_engine_as_its_module_id() -> None:
    assert token_from({"ABI_MODULE_KEY": "k"}, MODULE_ID).identity == MODULE_ID


def test_the_module_never_imports_abi_core() -> None:
    """A remote module reaches the engine only through NATS."""
    code = (
        "import sys, naas_abi_apps.pennylane, naas_abi_apps.pennylane.__main__, "
        "naas_abi_apps.pennylane.integrations.PennylaneIntegration; "
        "bad = [m for m in sys.modules if m.split('.')[0] in "
        "('naas_abi_core', 'naas_abi', 'naas_abi_marketplace')]; "
        "sys.exit(f'imports {bad[0]}' if bad else 0)"
    )
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)}
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
