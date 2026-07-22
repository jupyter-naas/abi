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


# ─────────────────────────────────────────────────────────────────────────────
# _strip_inbound_handoff_artifacts — orphan tool_use in extended-thinking content
# ─────────────────────────────────────────────────────────────────────────────


def _strip(name, messages):
    """Call the unbound method with a lightweight self (only ._name is used)."""
    from types import SimpleNamespace

    from naas_abi_core.services.agent.Agent import Agent

    return Agent._strip_inbound_handoff_artifacts(SimpleNamespace(_name=name), messages)


def test_strip_removes_orphan_tool_use_block_in_list_content():
    """Regression: with extended thinking the transfer ``tool_use`` lives inside
    the assistant message's list ``content``. Stripping the ``__handoff__``
    tool_result must also remove that block, or Anthropic rejects the history
    with 'tool_use ids were found without tool_result blocks'.
    """
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    tid = "toolu_ORPHAN"
    sub = "Market_Intelligence_Slides_Agent"
    messages = [
        HumanMessage(content="hi", id="h1"),
        AIMessage(
            content=[
                {"type": "thinking", "thinking": "", "signature": "sig"},
                {"type": "tool_use", "id": tid, "name": f"transfer_to_{sub}", "input": {}},
            ],
            tool_calls=[{"name": f"transfer_to_{sub}", "args": {}, "id": tid, "type": "tool_call"}],
            id="ai1",
        ),
        ToolMessage(
            content=f"__handoff__:{sub}",
            name=f"transfer_to_{sub}",
            tool_call_id=tid,
            id="tm1",
        ),
    ]

    cleaned = _strip(sub, messages)

    # The __handoff__ tool_result is gone …
    assert not any(isinstance(m, ToolMessage) for m in cleaned)
    # … and no orphan tool_use block survives anywhere in list content.
    for m in cleaned:
        if isinstance(m.content, list):
            assert not any(
                isinstance(b, dict) and b.get("type") == "tool_use" for b in m.content
            )
    # The transfer message carried only thinking+tool_use, so it is dropped whole.
    assert [type(m).__name__ for m in cleaned] == ["HumanMessage"]


def test_strip_keeps_visible_text_but_drops_tool_use_block():
    """When the transfer message also has real text, keep the text and strip
    only the tool_use block (and its tool_calls entry)."""
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    tid = "toolu_X"
    sub = "Support_Agent"
    messages = [
        HumanMessage(content="hi", id="h1"),
        AIMessage(
            content=[
                {"type": "text", "text": "Sure, one moment."},
                {"type": "tool_use", "id": tid, "name": f"transfer_to_{sub}", "input": {}},
            ],
            tool_calls=[{"name": f"transfer_to_{sub}", "args": {}, "id": tid, "type": "tool_call"}],
            id="ai1",
        ),
        ToolMessage(content=f"__handoff__:{sub}", name=f"transfer_to_{sub}", tool_call_id=tid, id="tm1"),
    ]

    cleaned = _strip(sub, messages)

    assert [type(m).__name__ for m in cleaned] == ["HumanMessage", "AIMessage"]
    ai = cleaned[1]
    assert ai.tool_calls == []
    assert all(
        not (isinstance(b, dict) and b.get("type") == "tool_use") for b in ai.content
    )
    assert any(
        isinstance(b, dict) and b.get("type") == "text" for b in ai.content
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tool-input normalization — Bedrock requires toolUse.input to be a JSON object
# ─────────────────────────────────────────────────────────────────────────────


def test_coerce_tool_args_to_object_handles_common_invalid_shapes():
    from naas_abi_core.services.agent.Agent import Agent

    assert Agent._coerce_tool_args_to_object(None) == {}
    assert Agent._coerce_tool_args_to_object([]) == {}
    assert Agent._coerce_tool_args_to_object("") == {}
    assert Agent._coerce_tool_args_to_object("{}") == {}
    assert Agent._coerce_tool_args_to_object('{"path": "a.py"}') == {"path": "a.py"}
    assert Agent._coerce_tool_args_to_object([{"path": "a.py"}]) == {"path": "a.py"}
    assert Agent._coerce_tool_args_to_object({"path": "a.py"}) == {"path": "a.py"}
    assert Agent._coerce_tool_args_to_object("not-json") == {}
    assert Agent._coerce_tool_args_to_object([1, 2]) == {}


def test_normalize_ai_message_tool_inputs_fixes_empty_list_in_content_blocks():
    """Bedrock/boto3 can decode empty tool input ``{}`` as ``[]`` inside content
    blocks. LangChain's ``tool_calls.args`` is already typed as dict, so the
    invalid shape usually survives only in ``content``."""
    from langchain_core.messages import AIMessage

    from naas_abi_core.services.agent.Agent import Agent

    message = AIMessage(
        content=[
            {
                "type": "tool_use",
                "id": "call-1",
                "name": "git_push",
                "input": [],
            }
        ],
        tool_calls=[
            {"name": "git_push", "args": {}, "id": "call-1", "type": "tool_call"}
        ],
        id="ai1",
    )

    normalized = Agent._normalize_ai_message_tool_inputs(message)

    assert normalized is not message
    assert normalized.tool_calls[0]["args"] == {}
    assert normalized.content[0]["input"] == {}


def test_normalize_ai_message_tool_inputs_fixes_missing_or_string_content_input():
    from langchain_core.messages import AIMessage

    from naas_abi_core.services.agent.Agent import Agent

    message = AIMessage(
        content=[
            {
                "type": "tool_use",
                "id": "call-1",
                "name": "git_status",
                "input": "",
            },
            {
                "type": "tool_use",
                "id": "call-2",
                "name": "git_push",
                "input": None,
            },
        ],
        tool_calls=[
            {"name": "git_status", "args": {}, "id": "call-1", "type": "tool_call"},
            {"name": "git_push", "args": {}, "id": "call-2", "type": "tool_call"},
        ],
        id="ai1",
    )

    normalized = Agent._normalize_ai_message_tool_inputs(message)

    assert normalized.content[0]["input"] == {}
    assert normalized.content[1]["input"] == {}


def test_normalize_tool_inputs_in_messages_only_rewrites_ai_messages():
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    from naas_abi_core.services.agent.Agent import Agent

    messages = [
        HumanMessage(content="push please", id="h1"),
        AIMessage(
            content=[
                {
                    "type": "tool_use",
                    "id": "call-1",
                    "name": "git_status",
                    "input": [],
                }
            ],
            tool_calls=[
                {
                    "name": "git_status",
                    "args": {},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
            id="ai1",
        ),
        ToolMessage(content="ok", name="git_status", tool_call_id="call-1", id="tm1"),
    ]

    normalized = Agent._normalize_tool_inputs_in_messages(messages)

    assert normalized[0] is messages[0]
    assert normalized[2] is messages[2]
    assert normalized[1].content[0]["input"] == {}
