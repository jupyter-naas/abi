from lib.abi.services.agent.OpenRouter import ChatOpenRouter

def test_openai():
    llm = ChatOpenRouter(model_name="openai/gpt-4.1")
    result = llm.invoke("What is the capital of France?").content
    assert result is not None, result
    assert "Paris" in result, result

def test_anthropic():
    llm = ChatOpenRouter(model_name="anthropic/claude-sonnet-4.5")
    result = llm.invoke("What is the capital of France?").content
    assert result is not None, result
    assert "Paris" in result, result

def test_xai():
    llm = ChatOpenRouter(model_name="x-ai/grok-4")
    result = llm.invoke("What is the capital of France?").content
    assert result is not None, result
    assert "Paris" in result, result

def test_mistral():
    llm = ChatOpenRouter(model_name="mistralai/mistral-large")
    result = llm.invoke("What is the capital of France?").content
    assert result is not None, result
    assert "Paris" in result, result

def test_gemini():
    llm = ChatOpenRouter(model_name="google/gemini-2.5-flash")
    result = llm.invoke("What is the capital of France?").content
    assert result is not None, result
    assert "Paris" in result, result

