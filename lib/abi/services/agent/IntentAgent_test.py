import pytest
from abi.services.agent.Agent import AgentConfiguration
from abi.services.agent.IntentAgent import IntentAgent
from abi.services.agent.beta.IntentMapper import Intent, IntentType
from langchain_openai import ChatOpenAI
@pytest.fixture
def agent():


    model = ChatOpenAI(model="gpt-4o-mini")

    intents = [
        Intent(intent_value="test", intent_type=IntentType.RAW, intent_target="This is a test intent"),
        Intent(intent_value="Give me the personal phone number of John Doe", intent_type=IntentType.RAW, intent_target="I can't give you the personal phone number of John Doe"),
        Intent(intent_value="Give me the professional phone number of John Doe", intent_type=IntentType.RAW, intent_target="00 11 22 33 44 55"),
        Intent(intent_value="a phone number of", intent_type=IntentType.RAW, intent_target="What phone number do you want?"),
        Intent(intent_value="What is the color of the shoes of Tom?", intent_type=IntentType.RAW, intent_target="The color of the shoes of Tom is red"),
        # Intent(intent_value="What is the color of the shoes of", intent_type=IntentType.RAW, intent_target=""),
        
    ]

    agent = IntentAgent(name="Test Agent", description="A test agent", chat_model=model, tools=[], agents=[], intents=intents, configuration=AgentConfiguration(system_prompt="""
You are an helpful assistant. 
"""))
    
    return agent


def test_intent_agent(agent):
    
    assert isinstance(agent, IntentAgent)
    
    test = agent.invoke("test")
    assert test == "This is a test intent", test
    
    e = agent.invoke("professional phone number of John Doe")
    assert "00 11 22 33 44 55" == e, e
    
    e = agent.invoke("personal phone number of John Doe")
    assert "I can't give you the personal phone number of John Doe".lower() in e.lower(), e


    assert len(agent._intent_mapper.map_intent("Give me the professional phone number of")) == 1, agent._intent_mapper.map_intent("Give me the professional phone number of")
    
    e = agent.invoke("Give me the professional phone number of")
    assert "00 11 22 33 44 55".lower() not in e.lower(), e
    
    
    
def test_unclear_intent(agent):
    # e = agent.invoke("Give me the professional phone number of")
    # assert "00 11 22 33 44 55".lower() not in e.lower(), e
    
    # e = agent.invoke("What is the color of the shoes of Tom?")
    # assert "The color of the shoes of Tom is red".lower() in e.lower(), e
    
    e = agent.invoke("What is the color of the shoes of")
    assert "The color of the shoes of Tom is red".lower() not in e.lower()
    
    