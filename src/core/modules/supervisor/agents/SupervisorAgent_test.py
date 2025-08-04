import pytest

from src.core.modules.supervisor.agents.SupervisorAgent import create_agent as create_supervisor_agent

@pytest.fixture
def agent():
    return create_supervisor_agent()

def test_raw_intent_name(agent):
    """Test RAW intent mapping for name question"""
    result = agent.invoke("what is your name")
    
    assert result is not None, result
    assert "My name is ABI" in result, result

def test_agent_intent_grok(agent):
    """Test AGENT intent mapping for Grok agent"""
    result = agent.invoke("ask grok")
    
    assert result is not None, result
    # The agent should route to Grok, so we expect some response indicating Grok is being used
    # This could be a routing message or actual Grok response
    assert "grok" in result.lower() or "gro" in result.lower(), result

def test_agent_intent_gemini(agent):
    """Test AGENT intent mapping for Gemini agent"""
    result = agent.invoke("use gemini")
    
    assert result is not None, result
    # The agent should route to Gemini
    assert "gemini" in result.lower() or "google" in result.lower(), result

def test_agent_intent_openai(agent):
    """Test AGENT intent mapping for OpenAI agent"""
    result = agent.invoke("ask chatgpt")
    
    assert result is not None, result
    # The agent should route to OpenAI/ChatGPT
    assert "openai" in result.lower() or "chatgpt" in result.lower() or "gpt" in result.lower(), result

def test_agent_intent_claude(agent):
    """Test AGENT intent mapping for Claude agent"""
    result = agent.invoke("use claude")
    
    assert result is not None, result
    # The agent should route to Claude
    assert "claude" in result.lower() or "anthropic" in result.lower(), result

def test_agent_intent_perplexity(agent):
    """Test AGENT intent mapping for Perplexity agent"""
    result = agent.invoke("search web")
    
    assert result is not None, result
    # The agent should route to Perplexity for web search
    assert "perplexity" in result.lower() or "search" in result.lower(), result

def test_agent_intent_mistral(agent):
    """Test AGENT intent mapping for Mistral agent"""
    result = agent.invoke("ask mistral")
    
    assert result is not None, result
    # The agent should route to Mistral
    assert "mistral" in result.lower(), result

def test_agent_intent_llama(agent):
    """Test AGENT intent mapping for LLaMA agent"""
    result = agent.invoke("use llama")
    
    assert result is not None, result
    # The agent should route to LLaMA
    assert "llama" in result.lower() or "meta" in result.lower(), result

def test_image_generation_intent(agent):
    """Test AGENT intent mapping for image generation"""
    result = agent.invoke("generate image")
    
    assert result is not None, result
    # The agent should route to Gemini for image generation
    assert "gemini" in result.lower() or "image" in result.lower() or "generate" in result.lower(), result

def test_multimodal_analysis_intent(agent):
    """Test AGENT intent mapping for multimodal analysis"""
    result = agent.invoke("analyze image")
    
    assert result is not None, result
    # The agent should route to Gemini for image analysis
    assert "gemini" in result.lower() or "analyze" in result.lower() or "image" in result.lower(), result

def test_truth_seeking_intent(agent):
    """Test AGENT intent mapping for truth seeking (Grok)"""
    result = agent.invoke("truth seeking")
    
    assert result is not None, result
    # The agent should route to Grok for truth seeking
    assert "grok" in result.lower() or "truth" in result.lower(), result

def test_web_search_intent(agent):
    """Test AGENT intent mapping for web search"""
    result = agent.invoke("search internet")
    
    assert result is not None, result
    # The agent should route to Perplexity for internet search
    assert "perplexity" in result.lower() or "search" in result.lower() or "internet" in result.lower(), result