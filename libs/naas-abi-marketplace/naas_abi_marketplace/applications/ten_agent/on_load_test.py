from __future__ import annotations

from fastapi import FastAPI
from naas_abi_core.engine.engine_configuration.EngineConfiguration import GlobalConfig
from naas_abi_core.engine.EngineProxy import EngineProxy
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_marketplace.applications.ten_agent import (
    ABIModule,
    integration_configuration,
)


class _DummyEngine:
    def __init__(self) -> None:
        self.services = IEngine.Services()
        self.modules: dict[str, object] = {}


def _module() -> ABIModule:
    proxy = EngineProxy(
        engine=_DummyEngine(),
        module_name="naas_abi_marketplace.applications.ten_agent",
        module_dependencies=ABIModule.dependencies,
    )
    config = ABIModule.Configuration(
        global_config=GlobalConfig(ai_mode="cloud"),
        openai_api_key="test-key-not-used",
    )
    return ABIModule(proxy, config)


def test_on_load_registers_no_agents() -> None:
    module = _module()
    module.on_load()
    assert module.agents == []


def test_api_mounts_only_the_voice_route() -> None:
    app = FastAPI()
    _module().api(app)
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/v1/voice/chat/completions" in paths
    assert "/api/v1/chat/completions" not in paths


def test_integration_configuration_carries_the_module_settings() -> None:
    cfg = integration_configuration(_module().configuration)
    assert cfg.openai_api_key == "test-key-not-used"
    assert cfg.websocket_port == 8765
    assert "~" not in str(cfg.runtime_dir)
