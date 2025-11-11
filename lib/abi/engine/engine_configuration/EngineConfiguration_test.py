from abi.engine.engine_configuration.EngineConfiguration import EngineConfiguration


def test_configuration_load(test_configuration: str):
    config = EngineConfiguration.load_configuration(test_configuration)
    assert config is not None
    assert False is True
