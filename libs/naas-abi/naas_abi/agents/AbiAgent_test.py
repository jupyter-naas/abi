import pytest
from naas_abi.agents.AbiAgent import create_agent as create_abi_agent


@pytest.fixture
def agent():
    return create_abi_agent()


# ------------------------------------------------------------
# DIRECT INTENTS
# ------------------------------------------------------------


def test_hello(agent):
    """Test RAW intent mapping for name question -> RAW intent"""
    result = agent.invoke("hello")

    # Abi: Hello, what can I do for you?

    assert result is not None, result
    assert "Hello, what can I do for you?" in result, result


def test_capabilities(agent):
    """Test capabilities of the agent"""
    result = agent.invoke("what can you do")

    # Abi: I’m Abi, developed by NaasAI. Here’s what I can do for you:

    # 1. Agent Orchestration: I route your requests to the best specialized AI agents for the task—whether it’s coding, research, business strategy, creative work, or data
    # analysis. 2. Strategic Advisory: I provide high-level consulting on business, technical, and strategic matters, synthesizing insights from multiple sources. 3. Knowledge
    # Integration: I combine information from various agents and data sources to deliver clear, actionable answers. 4. Context Preservation: I keep track of our conversation, so
    # you don’t have to repeat yourself, even when switching between different agents or topics. 5. Task Automation: I can help automate workflows, manage resources, and interact
    # with platforms like GitHub or Naas. 6. Custom Recommendations: I suggest the best AI agent or tool for your specific needs—whether you want speed, cost-efficiency,
    # intelligence, or a particular capability. 7. Multimodal Support: I handle text, images, PDFs, and more, and can generate or analyze content in multiple formats.

    # If you have a specific task or question, just let me know!

    assert result is not None, result
    # Check that at least 80% (4 out of 5) of the key capabilities are present
    key_capabilities: list[str] = [
        "orchestration",
        "strategic",
        "advisory",
        "knowledge",
        "integration",
        "coordination",
        "multi-agent",
        "routing",
        "naasai",
    ]
    found_capabilities = sum(1 for cap in key_capabilities if cap in result.lower())
    min_required = int(len(key_capabilities) * 0.7)
    assert found_capabilities >= min_required, (
        f"Only found {found_capabilities} capabilities in response: {result}"
    )


# def test_search_web(agent):
#     """Test search web capability"""
#     from datetime import datetime
#     result = agent.invoke("Ask ChatGPT Agent, what are the news about France today? Start by: 'As of today the date is YYYY-MM-DD.")

#     assert result is not None, result
#     assert datetime.now().strftime("%Y-%m-%d") in result, result
#     assert "sources" in result.lower(), result


def test_thank_you(agent):
    """Test thank you intent -> RAW intent"""
    result = agent.invoke("thank you")

    # Abi: You're welcome, can I help you with anything else?

    assert result is not None, result
    assert "You're welcome, can I help you with anything else?" in result, result


# ------------------------------------------------------------
# AGENTS CAPABILITIES
# ------------------------------------------------------------


def test_search_web_intent(agent):
    """Test search web intent -> AGENT intent"""
    result = agent.invoke("search news about ai")

    # Abi: I found multiple intents that could handle your request:

    #  1 ChatGPT (confidence: 89.7%) Intent: search news about
    #  2 Grok (confidence: 89.7%) Intent: search news about

    # Please choose an intent by number (e.g., '1' or '2')

    assert result is not None, result
    assert "I found multiple intents that could handle your request" in result, result
    assert "chatgpt" in result.lower() or "grok" in result.lower(), result


def test_image_generation_intent(agent):
    """Test AGENT intent mapping for image generation"""
    result = agent.invoke("generate image")

    # Gemini: What kind of image would you like to generate? Please describe it in detail.

    assert result is not None, result
    # The agent should route to Gemini for image generation
    assert (
        "describe" in result.lower()
        or "image" in result.lower()
        or "generate" in result.lower()
    ), result

    result = agent.invoke("a cat in a box")
    assert "generate" in result.lower(), result


def test_multimodal_analysis_intent(agent):
    """Test AGENT intent mapping for multimodal analysis"""
    result = agent.invoke("analyze image")

    assert result is not None, result
    # The agent should route to Gemini for image analysis
    assert (
        "gemini" in result.lower()
        or "analyze" in result.lower()
        or "image" in result.lower()
    ), result


# ------------------------------------------------------------
# AGENTS ROUTING
# ------------------------------------------------------------


def test_chatgpt_intent(agent):
    """Test AGENT intent mapping for chatgpt"""
    result = agent.invoke("@Knowledge_Graph_Builder hello")

    # Knowledge_Graph_Builder: Hello, what can I do for you?

    assert result is not None, result
    assert "Hello, what can I do for you?" in result, result

    result = agent.invoke("search news about ai")  # testing routing to other agents

    # Knowledge_Graph_Builder: I found multiple intents that could handle your request:

    #  1 ChatGPT (confidence: 89.7%) Intent: search news about
    #  2 Grok (confidence: 89.7%) Intent: search news about

    # Please choose an intent by number (e.g., '1' or '2')

    assert result is not None, result
    assert "I found multiple intents that could handle your request" in result, result
    assert "chatgpt" in result.lower() or "grok" in result.lower(), result
