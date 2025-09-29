import pytest

from src.core.abi.agents.AbiAgent import create_agent as create_abi_agent

@pytest.fixture
def agent():
    return create_abi_agent()

def test_raw_intent_name(agent):
    """Test RAW intent mapping for name question"""
    result = agent.invoke("what is your name")

    # Abi: My name is Abi, developed by NaasAI. How can I assist you today?  

    assert result is not None, result
    assert "abi" in result.lower(), result

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
        'naasai',
    ]
    found_capabilities = sum(1 for cap in key_capabilities if cap in result.lower())
    min_required = int(len(key_capabilities) * 0.7)
    assert found_capabilities >= min_required, f"Only found {found_capabilities} capabilities in response: {result}"

# def test_search_web(agent):
#     """Test search web capability"""
#     from datetime import datetime
#     result = agent.invoke("Ask ChatGPT Agent, what are the news about France today? Start by: 'As of today the date is YYYY-MM-DD.")
    
#     assert result is not None, result
#     assert datetime.now().strftime("%Y-%m-%d") in result, result
#     assert "sources" in result.lower(), result

def test_image_generation_intent(agent):
    """Test AGENT intent mapping for image generation"""
    result = agent.invoke("generate image")
    
    # Gemini: What kind of image would you like to generate? Please describe it in detail.
       
    assert result is not None, result
    # The agent should route to Gemini for image generation
    assert "describe" in result.lower() or "image" in result.lower() or "generate" in result.lower(), result

    result = agent.invoke("a cat in a box")
    assert "generate" in result.lower(), result

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

# # =============================================================================
# # REAL-WORLD CONVERSATION PATTERNS (from terminal logs)
# # =============================================================================

# def test_french_greeting_and_typos(agent):
#     """Test French greetings and typo tolerance (real patterns from logs)"""
#     # French greeting
#     result = agent.invoke("salut")
#     assert result is not None, result
#     assert "salut" in result.lower(), result
    
#     # Typo in agent name "gemiini" instead of "gemini"
#     result_typo = agent.invoke("parle a gemiini")
#     assert result_typo is not None, result_typo

# def test_agent_switching_mid_conversation(agent):
#     """Test changing agent preference mid-conversation (real pattern from logs)"""
#     # First ask for one agent
#     result1 = agent.invoke("I want to talk to gemini")
#     assert result1 is not None, result1
    
#     # Then change mind
#     result2 = agent.invoke("no sorry ChatGPT")
#     assert result2 is not None, result2

# def test_social_media_searches(agent):
#     """Test real social media search patterns from logs"""
#     # Trump tweet search (real query from logs)
#     result1 = agent.invoke("what's the latest tweet from Trump?")
#     assert result1 is not None, result1
    
#     # Obama tweet search in French (real query from logs)
#     result2 = agent.invoke("je veux chercher des infos sur X, le dernier tweet de Obama")
#     assert result2 is not None, result2

# def test_ai_news_request_french(agent):
#     """Test AI news request in French (real pattern from logs)"""
#     result = agent.invoke("tu peux nous donner les dernies news AI?")
#     assert result is not None, result

# def test_agent_chaining_pattern(agent):
#     from datetime import datetime
#     """Test asking one agent then another for interpretation (real pattern from logs)"""
#     # Ask Perplexity for info
#     result1 = agent.invoke("ask perplexity for latest AI news")
#     assert result1 is not None, result1
#     # Check for year
#     assert str(datetime.now().year) in result1, f"Year is not present in result: {result1}"
#     # Check for month in numeric and text formats
#     current_month = datetime.now().month
#     month_str = str(current_month)
#     month_name = datetime.now().strftime("%B")
#     month_abbr = datetime.now().strftime("%b")
#     assert any(m in result1 for m in [month_str, month_name, month_abbr]), f"Month not found in any format in result: {result1}"
    
#     # Then ask Claude to interpret
#     result2 = agent.invoke("ask claude tu interprete comment les resultats?")
#     assert result2 is not None, result2
#     assert "claude" in result2.lower(), f"Claude not found in result: {result2}"

# def test_casual_greetings(agent):
#     """Test casual greetings found in real conversations"""
#     casual_greetings = ["yo", "coucou", "salut toi"]
    
#     for greeting in casual_greetings:
#         result = agent.invoke(greeting)
#         assert result is not None, f"Failed for greeting: {greeting}"

# def test_meta_conversation_about_system(agent):
#     """Test conversation about the multi-agent system itself (real pattern from logs)"""
#     result = agent.invoke("je suis en train de monter un multi agent system la")
#     assert result is not None, result
    
#     # Follow up about agents in the system
#     result2 = agent.invoke("y a mistral dans la boucle avec claude et llama")
#     assert result2 is not None, result2

# def test_specific_agent_requests_french(agent):
#     """Test asking for specific agents in French (real pattern from logs)"""
#     result = agent.invoke("on peut parler a mistral?")
#     assert result is not None, result

# def test_grok_for_truth_seeking(agent):
#     """Test Grok for current events and truth-seeking (real usage pattern)"""
#     result = agent.invoke("can we talk to grok")
#     assert result is not None, result

# def test_persistent_information_requests(agent):
#     """Test persistent requests for specific information (real pattern from logs)"""
#     # User keeps asking for the same thing in different ways
#     requests = [
#         "give the link",
#         "I want the link from the post", 
#         "i want the link of the tweet"
#     ]
    
#     for request in requests:
#         result = agent.invoke(request)
#         assert result is not None, f"Failed for request: {request}"

# def test_mixed_language_patterns(agent):
#     """Test mixed language usage (real pattern from logs)"""
#     # English request to French context
#     result = agent.invoke("ask perplexity tu peux nous donner les dernies news AI?")
#     assert result is not None, result

# def test_french_agent_switching(agent):
#     """Test French agent switching patterns (real from logs)"""
#     result = agent.invoke("pardon plutot mistral")
#     assert result is not None, result

# def test_common_typos(agent):
#     """Test tolerance for common typos found in real conversations"""
#     typos = [
#         ("gemiini", "gemini"),
#         ("chatGTP", "chatgpt"), 
#         ("mistrl", "mistral")
#     ]
    
#     for typo, correct in typos:
#         result = agent.invoke(f"talk to {typo}")
#         assert result is not None, f"Failed to handle typo: {typo}"