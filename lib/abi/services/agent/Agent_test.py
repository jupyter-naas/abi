import pytest


@pytest.fixture
def model():
    import os
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model="gpt-4o", temperature=0, api_key=os.environ.get("OPENAI_API_KEY")
    )


def test_no_tools_no_agents(model):
    from abi.services.agent.Agent import Agent, AgentConfiguration
    from langchain_core.messages import AIMessage

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
    from abi.services.agent.Agent import Agent, AgentConfiguration
    from langchain_core.tools import tool

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


def test_agents_no_tools(model):
    from abi.services.agent.Agent import Agent, AgentConfiguration
    from queue import Queue

    queue = Queue()

    agent = Agent(
        name="Test Agent",
        description="A test agent",
        chat_model=model,
        tools=[
            Agent(
                name="Greeter",
                description="A greeter agent",
                chat_model=model,
                tools=[],
                agents=[],
                configuration=AgentConfiguration(
                    system_prompt="You are a greeter agent. You must greet the user with the name they provide in the form 'Hello, <name>!' and nothing else."
                ),
                event_queue=queue,
            )
        ],
        agents=[],
        configuration=AgentConfiguration(
            system_prompt="You are an LLM running in a test environment. You have must call the greeter agent and output it's result and nothing else."
        ),
        event_queue=queue,
    )

    chunks = []

    for _, chunk in agent.stream("ABI"):
        chunks.append(chunk)

    assert queue.qsize() == 2

    while not queue.empty():
        _ = queue.get()


def test_agent_duplication(model):
    from abi.services.agent.Agent import Agent, AgentConfiguration
    from queue import Queue

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


def test_agent_stream_invoke(model):
    from abi.services.agent.Agent import Agent, AgentConfiguration

    agent = Agent(
        name="Greeting Agent",
        description="A Greeting agent",
        chat_model=model,
        tools=[],
        agents=[],
        configuration=AgentConfiguration(system_prompt="You are a Greeting agent"),
    )

    events = []
    for event in agent.stream_invoke("My name is ABI"):
        events.append(event)

    assert len(events) == 2
    assert events[0]["event"] == "message"
    assert events[1]["event"] == "done"
