"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import pytest
from naas_abi_apps.common.runtime import configuration_from, main
from naas_abi_apps.common.testing import no_core_import
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


def test_the_module_needs_its_service_key() -> None:
    # It holds a key, never a signing secret: no key, no start.
    for env in ({}, {"ABI_SERVICE_KEY": "a-token"}):
        with pytest.raises(SystemExit, match=f"module/<project>/{MODULE_ID}"):
            main(ABIModule, ENV_PREFIX, env)


def test_its_manifest_defaults_from_its_dependencies() -> None:
    from naas_abi_sdk.permissions import module_manifest

    actions = {
        a for s in module_manifest(ABIModule)["statements"] for a in s["actions"]
    }
    assert {"document:*", "model_registry:*", "secret:*"} <= actions


def test_the_module_never_imports_abi_core() -> None:
    """A remote module reaches the engine only through NATS."""
    assert (
        no_core_import(
            "naas_abi_apps.pennylane",
            "naas_abi_apps.pennylane.__main__",
            "naas_abi_apps.pennylane.integrations.PennylaneIntegration",
        )
        is None
    )
