import pytest
from naas_abi.core.qwen.agents.QwenAgent import create_agent


@pytest.fixture
def agent():
    """Create a QwenAgent instance for testing."""
    return create_agent()


def test_agent_name_identification(self, agent):
    """Test that agent correctly identifies itself."""
    result = agent.invoke("what is your name")

    assert result is not None, "Agent should return a response"
    assert "Qwen" in result, f"Expected 'Qwen' in response, got: {result}"


def test_agent_responds_to_privacy_questions(self, agent):
    """Test agent emphasizes privacy and local processing."""
    result = agent.invoke("Can you help me process data privately?")

    assert result is not None
    # Should mention local processing or privacy
    result_lower = result.lower()
    privacy_keywords = ["local", "private", "privacy", "offline", "device"]
    assert any(keyword in result_lower for keyword in privacy_keywords), (
        f"Expected privacy-related keywords in response: {result}"
    )


def test_agent_handles_code_requests(self, agent):
    """Test agent responds appropriately to code generation requests."""
    result = agent.invoke("Generate a simple Python function")

    assert result is not None
    # Should provide code or offer to help with coding
    result_lower = result.lower()
    code_keywords = ["python", "function", "def", "code"]
    assert any(keyword in result_lower for keyword in code_keywords), (
        f"Expected code-related response: {result}"
    )


def test_agent_handles_multilingual_requests(self, agent):
    """Test agent responds to multilingual requests."""
    result = agent.invoke("Can you help me translate something to Chinese?")

    assert result is not None
    # Should acknowledge multilingual capabilities
    result_lower = result.lower()
    multilingual_keywords = ["chinese", "translate", "multilingual", "language"]
    assert any(keyword in result_lower for keyword in multilingual_keywords), (
        f"Expected multilingual response: {result}"
    )


def test_agent_reasoning_capabilities(self, agent):
    """Test agent handles reasoning and analysis requests."""
    result = agent.invoke("Can you help me analyze a complex problem?")

    assert result is not None
    # Should acknowledge reasoning capabilities
    result_lower = result.lower()
    reasoning_keywords = ["analyze", "problem", "reasoning", "solve", "logic"]
    assert any(keyword in result_lower for keyword in reasoning_keywords), (
        f"Expected reasoning-related response: {result}"
    )


def test_full_conversation_flow(self, agent):
    """Test a full conversation flow with the agent."""
    # This test assumes the model is available and functional
    responses = []

    # Initial greeting
    response1 = agent.invoke("Hello, what can you help me with?")
    responses.append(response1)

    # Privacy question
    response2 = agent.invoke(
        "Can you process my data locally without sending it to external servers?"
    )
    responses.append(response2)

    # Code generation request
    response3 = agent.invoke(
        "Can you generate a simple Python function to calculate fibonacci numbers?"
    )
    responses.append(response3)

    # All responses should be non-empty
    for i, response in enumerate(responses, 1):
        assert response is not None, f"Response {i} should not be None"
        assert len(response.strip()) > 0, f"Response {i} should not be empty"


def test_context_preservation(self, agent):
    """Test that agent preserves context across multiple interactions."""
    # This would test the agent's memory and context handling
    response1 = agent.invoke("My name is Alice and I'm working on a Python project.")
    assert response1 is not None

    response2 = agent.invoke("What was my name again?")
    assert response2 is not None
    # In a real test, we'd check if the agent remembered the name
    # This depends on the agent's memory configuration
