"""The agent's prompt and its actual tool surface must agree.

``Agent`` injects five default tools (get_time_date, write_file, read_file,
list_dir, run_terminal) unless told not to, and declaring ``tools = []`` does
not stop it. This agent's prompt claims no tools and no network access, and
``run_terminal`` made that claim wrong outright in a coding workspace.

Builds the agent for real rather than inspecting its source, so the assertion
is about behaviour and survives a refactor of how the flag is passed.
"""

from __future__ import annotations

from naas_abi_core.engine.engine_configuration.EngineConfiguration import GlobalConfig
from naas_abi_core.engine.EngineProxy import EngineProxy
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.module.Module import ModuleDependencies
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_marketplace.ai.ollama.agents.OllamaAgent import OllamaAgent


class _DummyEngine:
    def __init__(self, services: IEngine.Services) -> None:
        self.services = services
        self.modules: dict[str, object] = {}


def _loaded_module():
    """A loaded ollama module, so ``New()`` can resolve the chat model."""
    from naas_abi_marketplace.ai.ollama import ABIModule

    registry = ModelRegistryService()
    proxy = EngineProxy(
        engine=_DummyEngine(services=IEngine.Services(model_registry=registry)),
        module_name="naas_abi_marketplace.ai.ollama",
        module_dependencies=ModuleDependencies(
            modules=[], services=[ModelRegistryService]
        ),
    )
    module = ABIModule(
        proxy,
        ABIModule.Configuration(
            global_config=GlobalConfig(ai_mode="local"),
            # No server required for any of this.
            probe_on_load=False,
        ),
    )
    module.on_load()
    return module


def test_agent_binds_no_tools_at_runtime() -> None:
    """`tools = []` is not enough — the framework injects five by default."""
    _loaded_module()
    agent = OllamaAgent.New()

    bound = [getattr(tool, "name", str(tool)) for tool in agent._tools]
    assert bound == [], f"prompt claims no tools, but these are bound: {bound}"


def test_run_terminal_is_not_among_them() -> None:
    """The one that makes the privacy claim actively wrong."""
    _loaded_module()
    agent = OllamaAgent.New()

    assert not any(
        getattr(tool, "name", "") == "run_terminal" for tool in agent._tools
    )


def test_prompt_claims_no_tools() -> None:
    """Pins the claim the above exists to keep true."""
    assert "no tools and no network access" in OllamaAgent.system_prompt
