import pytest

from src.core.modules.abi.agents.AbiAgent import create_agent as create_abi_agent

@pytest.fixture
def agent():
    return create_abi_agent()

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

# =============================================================================
# REAL-WORLD CONVERSATION PATTERNS (from terminal logs)
# =============================================================================

def test_french_greeting_and_typos(agent):
    """Test French greetings and typo tolerance (real patterns from logs)"""
    # French greeting
    result = agent.invoke("salut")
    assert result is not None, result
    assert "salut" in result.lower(), result
    
    # Typo in agent name "gemiini" instead of "gemini"
    result_typo = agent.invoke("parle a gemiini")
    assert result_typo is not None, result_typo

def test_agent_switching_mid_conversation(agent):
    """Test changing agent preference mid-conversation (real pattern from logs)"""
    # First ask for one agent
    result1 = agent.invoke("I want to talk to gemini")
    assert result1 is not None, result1
    
    # Then change mind
    result2 = agent.invoke("no sorry ChatGPT")
    assert result2 is not None, result2

def test_social_media_searches(agent):
    """Test real social media search patterns from logs"""
    # Trump tweet search (real query from logs)
    result1 = agent.invoke("what's the latest tweet from Trump?")
    assert result1 is not None, result1
    
    # Obama tweet search in French (real query from logs)
    result2 = agent.invoke("je veux chercher des infos sur X, le dernier tweet de Obama")
    assert result2 is not None, result2

def test_ai_news_request_french(agent):
    """Test AI news request in French (real pattern from logs)"""
    result = agent.invoke("tu peux nous donner les dernies news AI?")
    assert result is not None, result

def test_agent_chaining_pattern(agent):
    from datetime import datetime
    """Test asking one agent then another for interpretation (real pattern from logs)"""
    # Ask Perplexity for info
    result1 = agent.invoke("ask perplexity for latest AI news")
    assert result1 is not None, result1
    # Check for year
    assert str(datetime.now().year) in result1, f"Year is not present in result: {result1}"
    # Check for month in numeric and text formats
    current_month = datetime.now().month
    month_str = str(current_month)
    month_name = datetime.now().strftime("%B")
    month_abbr = datetime.now().strftime("%b")
    assert any(m in result1 for m in [month_str, month_name, month_abbr]), f"Month not found in any format in result: {result1}"
    
    # Then ask Claude to interpret
    result2 = agent.invoke("ask claude tu interprete comment les resultats?")
    assert result2 is not None, result2
    assert "claude" in result2.lower(), f"Claude not found in result: {result2}"

def test_casual_greetings(agent):
    """Test casual greetings found in real conversations"""
    casual_greetings = ["yo", "coucou", "salut toi"]
    
    for greeting in casual_greetings:
        result = agent.invoke(greeting)
        assert result is not None, f"Failed for greeting: {greeting}"

def test_meta_conversation_about_system(agent):
    """Test conversation about the multi-agent system itself (real pattern from logs)"""
    result = agent.invoke("je suis en train de monter un multi agent system la")
    assert result is not None, result
    
    # Follow up about agents in the system
    result2 = agent.invoke("y a mistral dans la boucle avec claude et llama")
    assert result2 is not None, result2

def test_specific_agent_requests_french(agent):
    """Test asking for specific agents in French (real pattern from logs)"""
    result = agent.invoke("on peut parler a mistral?")
    assert result is not None, result

def test_grok_for_truth_seeking(agent):
    """Test Grok for current events and truth-seeking (real usage pattern)"""
    result = agent.invoke("can we talk to grok")
    assert result is not None, result

def test_persistent_information_requests(agent):
    """Test persistent requests for specific information (real pattern from logs)"""
    # User keeps asking for the same thing in different ways
    requests = [
        "give the link",
        "I want the link from the post", 
        "i want the link of the tweet"
    ]
    
    for request in requests:
        result = agent.invoke(request)
        assert result is not None, f"Failed for request: {request}"

def test_mixed_language_patterns(agent):
    """Test mixed language usage (real pattern from logs)"""
    # English request to French context
    result = agent.invoke("ask perplexity tu peux nous donner les dernies news AI?")
    assert result is not None, result

def test_french_agent_switching(agent):
    """Test French agent switching patterns (real from logs)"""
    result = agent.invoke("pardon plutot mistral")
    assert result is not None, result

def test_common_typos(agent):
    """Test tolerance for common typos found in real conversations"""
    typos = [
        ("gemiini", "gemini"),
        ("chatGTP", "chatgpt"), 
        ("mistrl", "mistral")
    ]
    
    for typo, correct in typos:
        result = agent.invoke(f"talk to {typo}")
        assert result is not None, f"Failed to handle typo: {typo}"