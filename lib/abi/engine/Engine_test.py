from abi.engine.Engine import Engine


def test_engine(test_configuration: str):
    engine = Engine(test_configuration)
    assert engine is not None
