import pytest
from naas_abi_core.engine.Engine import Engine
from naas_abi_marketplace.ai.chatgpt import ABIModule


@pytest.fixture
def module() -> ABIModule:
    # Load the engine to load the module.
    engine = Engine()
    engine.load(module_names=["src.core.chatgpt"])

    return ABIModule.get_instance()
