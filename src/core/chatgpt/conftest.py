import pytest
from abi.engine.Engine import Engine

from src.core.chatgpt import ABIModule


@pytest.fixture
def module() -> ABIModule:
    # Load the engine to load the module.
    engine = Engine()
    engine.load(module_names=["src.core.chatgpt"])

    return ABIModule.get_instance()
