import pytest


@pytest.fixture
def model():
    import os

    from dotenv import load_dotenv
    from langchain_openai import ChatOpenAI

    load_dotenv()

    return ChatOpenAI(
        model="gpt-4o", temperature=0, api_key=os.environ.get("OPENAI_API_KEY")
    )


def test_no_tools_no_agents(model):
    from langchain_core.messages import AIMessage
    from naas_abi_core.services.agent.Agent import Agent, AgentConfiguration

    agent = Agent(
        name="Test Agent",
        description="A test agent",
        chat_model=model,
        tools=[],
        agents=[],
        configuration=AgentConfiguration(
            system_prompt="You are an LLM running in a test environment. You must output '42' and nothing else."
        ),
    )

    for _, chunk in agent.stream("Hello, world!"):
        assert "call_model" in chunk
        assert "messages" in chunk["call_model"]
        assert len(chunk["call_model"]["messages"]) == 1
        assert isinstance(chunk["call_model"]["messages"][0], AIMessage)
        assert chunk["call_model"]["messages"][0].content == "42"


def test_tools_no_agents(model):
    from langchain_core.tools import tool
    from naas_abi_core.services.agent.Agent import Agent, AgentConfiguration

    @tool
    def test_tool(input: str) -> str:
        """test_tool

        Args:
            input (str): The input to the tool

        Returns:
            str: Return the input
        """
        assert input == "Hello, world!"
        return input

    agent = Agent(
        name="Test Agent",
        description="A test agent",
        chat_model=model,
        tools=[test_tool],
        agents=[],
        configuration=AgentConfiguration(
            system_prompt="You are an LLM running in a test environment. You must call the tool `test_tool` with the argument `Hello, world!` and format the output as `Tool Response: <result>`. It is very important that you reformat the output and not return only the tool response."
        ),
    )

    chunks = []

    for _, chunk in agent.stream("Hello, world!"):
        chunks.append(chunk)


# This test is not consistent.
# def test_agents_no_tools(model):
#     from naas_abi_core.services.agent.Agent import Agent, AgentConfiguration, AgentSharedState
#     from queue import Queue
#     import json
#     import pydash as pd

#     queue = Queue()

#     agent = Agent(
#         name="Test Agent",
#         description="A test agent",
#         chat_model=model,
#         tools=[
#             Agent(
#                 name="Greeter",
#                 description="A greeter agent",
#                 chat_model=model,
#                 tools=[],
#                 agents=[],
#                 configuration=AgentConfiguration(
#                     system_prompt="You are a greeter agent. You must greet the user with the name they provide in the form 'Hello, <name>!' and nothing else."
#                 ),
#                 event_queue=queue,
#             )
#         ],
#         agents=[],
#         configuration=AgentConfiguration(
#             system_prompt="The user will send you his name. You must call the greeter agent and output it's result and nothing else. You must call it only once."
#         ),
#         event_queue=queue,
#     )

#     chunks = []

#     for _, chunk in agent.stream("ABI"):
#         chunks.append(chunk)
#         if 'call_model' in chunk:
#             print(f'\n\t Call Model: {type(chunk)}')
#             print(pd.get(chunk, "call_model.messages[-1].content"))
#             print('\n')
#         elif 'call_tools' in chunk:
#             print(f'\n\t Call Tools: {type(chunk)}')
#             print(pd.get(chunk, "call_tools.messages[-1].content"))
#             print('\n')
#         else:
#             print(f'\n\t Unknown: {type(chunk)}')
#             print(chunk)
#             print('\n')
#         assert len(chunks) <= 5

#     assert len(chunks) == 5
#     assert list(chunks[-1].values())[0]['messages'][-1].content == "Hello, ABI!"


def test_agent_duplication(model):
    from queue import Queue

    from naas_abi_core.services.agent.Agent import Agent, AgentConfiguration

    queue = Queue()

    sub_agent = Agent(
        name="Sub agent",
        description="Sub agent",
        chat_model=model,
        tools=[],
        configuration=AgentConfiguration(system_prompt=""),
        event_queue=queue,
    )

    first_agent = Agent(
        name="Test Agent",
        description="A test agent",
        chat_model=model,
        tools=[sub_agent],
        agents=[],
        configuration=AgentConfiguration(system_prompt=""),
        event_queue=queue,
    )

    duplicated_agent = first_agent.duplicate()

    assert id(duplicated_agent) != id(first_agent)
    assert id(duplicated_agent.agents[0]) != id(first_agent.agents[0])


# def test_agent_stream_invoke(model):
#     from naas_abi_core.services.agent.Agent import Agent, AgentConfiguration

#     agent = Agent(
#         name="Greeting Agent",
#         description="A Greeting agent",
#         chat_model=model,
#         tools=[],
#         agents=[],
#         configuration=AgentConfiguration(system_prompt="You are a Greeting agent"),
#     )

#     events = []
#     for event in agent.stream_invoke("My name is ABI"):
#         events.append(event)

#     assert len(events) == 2
#     assert events[0]["event"] == "message"
#     assert events[1]["event"] == "done"


def test_agent_one_tool_agent_response(model):
    from langchain_core.tools import tool
    from naas_abi_core.services.agent.Agent import Agent, AgentConfiguration

    @tool
    def add_one(input: int) -> int:
        """Add one to the input"""
        return input + 1

    agent = Agent(
        name="Test Agent",
        description="A test agent",
        chat_model=model,
        tools=[add_one],
        configuration=AgentConfiguration(
            system_prompt="""You are a test agent. You must add one to the input and return the result.
        Your output must be like:
        
        
        <user_input> + one = result
        """
        ),
    )

    chunks = []
    for _, chunk in agent.stream("42"):
        chunks.append(chunk)
        print(chunk)

    assert len(chunks) == 3
    assert "call_model" in chunks[-1]
    assert chunks[-1]["call_model"]["messages"][0].content == "42 + one = 43"
