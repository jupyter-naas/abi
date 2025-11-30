import pytest
from langchain_openai import ChatOpenAI
from naas_abi_core.services.agent.IntentAgent import (
    Agent,
    AgentConfiguration,
    Intent,
    IntentAgent,
    IntentType,
)


@pytest.fixture
def agent():
    model = ChatOpenAI(model="gpt-4.1")
    subagent_chatgpt = Agent(
        name="ChatGPT",
        description="ChatGPT agent",
        chat_model=model,
        tools=[],
        agents=[],
        configuration=AgentConfiguration(),
    )
    subagent_perplexity = Agent(
        name="Perplexity",
        description="Perplexity agent",
        chat_model=model,
        tools=[],
        agents=[],
        configuration=AgentConfiguration(),
    )

    intents = [
        Intent(
            intent_value="test",
            intent_type=IntentType.RAW,
            intent_target="This is a test intent",
        ),
        Intent(
            intent_value="Give me the personal phone number of John Doe",
            intent_type=IntentType.RAW,
            intent_target="I can't give you the personal phone number of John Doe",
        ),
        Intent(
            intent_value="Give me the professional phone number of John Doe",
            intent_type=IntentType.RAW,
            intent_target="00 11 22 33 44 55",
        ),
        Intent(
            intent_value="a phone number of",
            intent_type=IntentType.RAW,
            intent_target="What phone number do you want?",
        ),
        Intent(
            intent_value="What is the color of the shoes of Tom?",
            intent_type=IntentType.RAW,
            intent_target="The color of the shoes of Tom is red",
        ),
        Intent(
            intent_value="Search news about",
            intent_type=IntentType.AGENT,
            intent_target="ChatGPT",
        ),
        Intent(
            intent_value="Search news about",
            intent_type=IntentType.AGENT,
            intent_target="Perplexity",
        ),
    ]

    agent = IntentAgent(
        name="Test Agent",
        description="A test agent",
        chat_model=model,
        tools=[],
        agents=[subagent_chatgpt, subagent_perplexity],
        intents=intents,
        configuration=AgentConfiguration(system_prompt="You are an helpful assistant."),
    )
    return agent


def test_intent_agent(agent):
    test = agent.invoke("test")
    assert test == "This is a test intent", test

    result = agent.invoke("professional phone number of John Doe")
    assert "00 11 22 33 44 55" == result, result

    result = agent.invoke("personal phone number of John Doe")
    assert (
        "I can't give you the personal phone number of John Doe".lower()
        in result.lower()
    ), result
    assert (
        len(agent._intent_mapper.map_intent("Give me the professional phone number of"))
        == 1
    ), agent._intent_mapper.map_intent("Give me the professional phone number of")

    result = agent.invoke("Give me the professional phone number of")
    assert "00 11 22 33 44 55".lower() not in result.lower(), result


def test_direct_intent(agent):
    result = agent.invoke("Hello")
    assert "Hello, what can I do for you?" == result, result

    result = agent.invoke("Thank you")
    assert "You're welcome, can I help you with anything else?" == result, result


def test_request_human_validation(agent):
    result = agent.invoke("Search news about ai")

    assert result is not None, result
    assert "I found multiple intents that could handle your request" in result, result
    assert "chatgpt" in result.lower() or "perplexity" in result.lower(), result


def test_request_help_tool(agent):
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
