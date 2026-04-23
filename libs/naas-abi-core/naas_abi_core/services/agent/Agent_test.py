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
        tools=[],
        agents=[sub_agent],
        configuration=AgentConfiguration(system_prompt=""),
        event_queue=queue,
    )

    duplicated_agent = first_agent.duplicate()

    assert id(duplicated_agent) != id(first_agent)
    assert id(duplicated_agent.agents[0]) != id(first_agent.agents[0])


def test_agent_stream_invoke(model):
    from naas_abi_core.services.agent.Agent import Agent, AgentConfiguration

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

    assert len(events) == 3, events
    assert events[0]["event"] == "ai_message", events[0]
    assert events[1]["event"] == "message", events[1]
    assert events[2]["event"] == "done", events[2]


def test_agent_stream_invoke_isolation(model):
    from queue import Queue

    from naas_abi_core.services.agent.Agent import (
        Agent,
        AgentConfiguration,
        AgentSharedState,
    )

    agent = Agent(
        name="Isolation Test Agent",
        description="Tests request isolation",
        chat_model=model,
        tools=[],
        agents=[],
        configuration=AgentConfiguration(
            system_prompt="You must respond with exactly the word 'ANSWER_A' and nothing else."
        ),
    )

    fresh_queue = Queue()
    fresh_state = AgentSharedState(thread_id="thread-a")
    dup_a = agent.duplicate(queue=fresh_queue, agent_shared_state=fresh_state)

    events_a = list(dup_a.stream_invoke("Give me answer A"))
    content_a = "".join(
        e["data"]
        for e in events_a
        if e.get("event") == "message" and "[DONE]" not in e.get("data", "")
    )
    assert "ANSWER_A" in content_a, f"Expected ANSWER_A but got: {content_a}"


def test_agent_completion_fresh_state_per_request(model):
    from naas_abi_core.services.agent.Agent import (
        Agent,
        AgentConfiguration,
        AgentSharedState,
    )

    agent = Agent(
        name="State Freshness Agent",
        description="Tests fresh state per request",
        chat_model=model,
        tools=[],
        agents=[],
        configuration=AgentConfiguration(system_prompt="Respond with 'OK'."),
    )

    dup = agent.duplicate(
        agent_shared_state=AgentSharedState(thread_id="unique-thread-123")
    )
    assert dup.state.thread_id == "unique-thread-123"

    dup2 = agent.duplicate(
        agent_shared_state=AgentSharedState(thread_id="another-thread-456")
    )
    assert dup2.state.thread_id == "another-thread-456"
    assert dup.state.thread_id == "unique-thread-123"
    assert dup.state.thread_id != dup2.state.thread_id


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
