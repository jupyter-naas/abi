def test_model():
    from .Gpt4oAIModel import model
    from .Model import ChatModel, ModelType

    assert model.name == "gpt-4o"
    assert model.context_window == 128000
    assert model.owner == "openai"
    assert isinstance(model.model, ChatModel)
    assert model.model_type == ModelType.CHAT