"""Agent behaviour both runtimes must share: graph, streaming events, memory, hooks."""

from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from tests.agent_parity.harness import ScriptedChatModel

DONE = {"event": "done", "data": "[DONE]"}


def _call(name: str, args: dict, call_id: str = "c1") -> dict:
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


def _uses(*calls: dict) -> AIMessage:
    return AIMessage(content="", tool_calls=list(calls))


@tool
def add(a: int, b: int) -> int:
    """Add two numbers.

    Args:
        a (int): first
        b (int): second
    """
    return a + b


@tool
def shout(text: str) -> str:
    """Upper-case a text.

    Args:
        text (str): input
    """
    return text.upper()


@tool(return_direct=True)
def card(title: str) -> str:
    """Render a card the user sees as is.

    Args:
        title (str): card title
    """
    return f"[card] {title}"


@tool
def explode(reason: str) -> str:
    """Always fails.

    Args:
        reason (str): why
    """
    raise ValueError(f"boom: {reason}")


@tool
def fetch(url: str) -> str:
    """Fetch a large page.

    Args:
        url (str): page
    """
    return "x" * 9_000


# --- answers -----------------------------------------------------------------------


def test_plain_answer(runner):
    agent = runner.make(ScriptedChatModel(script=[AIMessage("Hello there")]))

    assert runner.events(agent, "hi") == [
        {"event": "call_model", "data": "Parity"},
        {"event": "ai_message", "data": "Hello there"},
        {"event": "message", "data": "Hello there"},
        DONE,
    ]


def test_multiline_answer_is_replayed_line_by_line(runner):
    agent = runner.make(ScriptedChatModel(script=[AIMessage("one\n\ntwo\nthree")]))

    events = runner.events(agent, "hi")

    assert events[-5:] == [
        {"event": "message", "data": "one"},
        {"event": "message", "data": ""},
        {"event": "message", "data": "two"},
        {"event": "message", "data": "three"},
        DONE,
    ]


def test_invoke_returns_the_final_text(runner):
    agent = runner.make(ScriptedChatModel(script=[AIMessage("final words")]))

    assert runner.invoke(agent, "hi") == "final words"


# --- system prompt -----------------------------------------------------------------


def test_system_prompt_gets_the_current_date(runner):
    model = ScriptedChatModel(script=[AIMessage("ok")])
    runner.events(runner.make(model, system_prompt="Be terse."), "hi")

    system = model.received[0][0]
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    assert isinstance(system, SystemMessage)
    assert system.content == f"Be terse.\nCURRENT_DATE: The current date is {today}\n"
    assert isinstance(model.received[0][-1], HumanMessage)


def test_callable_system_prompt_sees_the_messages(runner):
    model = ScriptedChatModel(script=[AIMessage("ok")])
    configuration = runner.Configuration(
        system_prompt=lambda messages: f"{len(messages)} messages"
    )
    runner.events(runner.make(model, configuration=configuration), "hi")

    assert model.received[0][0].content.startswith("1 messages\nCURRENT_DATE")


# --- tools -------------------------------------------------------------------------


def test_tool_call_then_answer(runner):
    model = ScriptedChatModel(
        script=[_uses(_call("add", {"a": 2, "b": 3})), AIMessage("It is 5")]
    )

    assert runner.events(runner.make(model, [add]), "2+3?") == [
        {"event": "call_model", "data": "Parity"},
        {"event": "tool_usage", "data": "add"},
        {"event": "tool_response", "data": "5"},
        {"event": "call_model", "data": "Parity"},
        {"event": "ai_message", "data": "It is 5"},
        {"event": "message", "data": "It is 5"},
        DONE,
    ]
    tool_message = model.received[1][-1]
    assert isinstance(tool_message, ToolMessage) and tool_message.content == "5"


def test_parallel_tools_name_the_first_and_report_every_response(runner):
    model = ScriptedChatModel(
        script=[
            _uses(
                _call("add", {"a": 1, "b": 1}, "c1"),
                _call("shout", {"text": "hey"}, "c2"),
            ),
            AIMessage("done"),
        ]
    )

    events = runner.events(runner.make(model, [add, shout]), "go")

    assert events[:4] == [
        {"event": "call_model", "data": "Parity"},
        {"event": "tool_usage", "data": "add"},
        {"event": "tool_response", "data": "2"},
        {"event": "tool_response", "data": "HEY"},
    ]


def test_return_direct_tool_answers_without_calling_the_model_again(runner):
    model = ScriptedChatModel(script=[_uses(_call("card", {"title": "Q3"}))])

    assert runner.events(runner.make(model, [card]), "card") == [
        {"event": "call_model", "data": "Parity"},
        {"event": "tool_usage", "data": "card"},
        {"event": "tool_response", "data": "[card] Q3"},
        {"event": "ai_message", "data": "[card] Q3"},
        {"event": "message", "data": "[card] Q3"},
        DONE,
    ]
    assert len(model.received) == 1


def test_unknown_tool_is_reported_to_the_model(runner):
    model = ScriptedChatModel(script=[_uses(_call("nope", {})), AIMessage("sorry")])

    events = runner.events(runner.make(model, [add]), "go")

    response = next(e for e in events if e["event"] == "tool_response")
    assert response["data"].startswith(
        "Tool 'nope' is not available to agent 'Parity'."
    )
    assert events[-2:] == [{"event": "message", "data": "sorry"}, DONE]


def test_tool_exception_is_reported_to_the_model(runner):
    model = ScriptedChatModel(
        script=[_uses(_call("explode", {"reason": "x"})), AIMessage("recovered")]
    )

    events = runner.events(runner.make(model, [explode]), "go")

    assert {
        "event": "tool_response",
        "data": "Tool call explode failed: boom: x",
    } in events
    assert events[-2:] == [{"event": "message", "data": "recovered"}, DONE]


def test_long_tool_responses_are_truncated_in_events(runner):
    model = ScriptedChatModel(
        script=[_uses(_call("fetch", {"url": "u"})), AIMessage("ok")]
    )

    events = runner.events(runner.make(model, [fetch]), "go")

    response = next(e for e in events if e["event"] == "tool_response")
    assert response["data"] == "x" * 8_000 + "\n...[truncated]..."


def test_tool_calls_written_as_text_are_executed(runner):
    markup = '<tool_call>\n{"name": "add", "arguments": {"a": 4, "b": 4}}\n</tool_call>'
    model = ScriptedChatModel(script=[AIMessage(markup), AIMessage("eight")])

    events = runner.events(runner.make(model, [add]), "4+4")

    assert {"event": "tool_usage", "data": "add"} in events
    assert {"event": "tool_response", "data": "8"} in events


# --- errors and limits ---------------------------------------------------------------


def test_model_failure_becomes_a_friendly_answer(runner):
    model = ScriptedChatModel(script=[RuntimeError("Error code: 429 - rate limited")])

    events = runner.events(runner.make(model), "hi")

    friendly = "This model is rate limited. Pick another model in the agent menu and try again."
    assert events == [
        {"event": "call_model", "data": "Parity"},
        {"event": "ai_message", "data": friendly},
        {"event": "message", "data": friendly},
        DONE,
    ]


def test_recursion_limit_stops_with_a_friendly_answer(runner):
    model = ScriptedChatModel(script=[_uses(_call("add", {"a": 1, "b": 1}))])
    agent = runner.make(model, [add])
    agent.recursion_limit = 6

    events = runner.events(agent, "loop")

    assert events[-2:] == [
        {
            "event": "message",
            "data": "The agent hit its step limit before finishing. "
            "Try a smaller request, or continue from what already landed.",
        },
        DONE,
    ]


# --- memory --------------------------------------------------------------------------


def test_same_thread_remembers_previous_turns(runner):
    model = ScriptedChatModel(script=[AIMessage("noted"), AIMessage("Bob")])
    agent = runner.make(model)

    runner.events(agent, "my name is Bob")
    runner.events(agent, "what is my name?")

    second = [m.content for m in model.received[1][1:]]
    assert second == ["my name is Bob", "noted", "what is my name?"]


def test_duplicate_shares_memory_but_not_threads(runner):
    model = ScriptedChatModel(script=[AIMessage("noted")])
    agent = runner.make(model)
    runner.events(agent, "remember AMBER")

    runner.events(runner.duplicate(agent, "t-1"), "again")
    runner.events(runner.duplicate(agent, "t-2"), "fresh")

    assert [m.content for m in model.received[1][1:]] == [
        "remember AMBER",
        "noted",
        "again",
    ]
    assert [m.content for m in model.received[2][1:]] == ["fresh"]


def test_old_tool_results_are_compacted_for_the_model_only(runner):
    model = ScriptedChatModel(
        script=[
            _uses(_call("fetch", {"url": "u"})),
            AIMessage("read it"),
            AIMessage("ok"),
        ]
    )
    agent = runner.make(model, [fetch])
    runner.events(agent, "fetch")
    runner.events(agent, "next")

    previous_tool = next(m for m in model.received[2] if isinstance(m, ToolMessage))
    assert previous_tool.content == (
        "[Old tool result cleared. Call the tool again if you need the full content.]"
    )


# --- hooks and callbacks -----------------------------------------------------------


def test_hooks_observe_without_breaking_the_turn(runner):
    seen: list[str] = []

    class Observed(runner.Agent):
        def onHumanMessage(self, message):
            seen.append(f"human:{message.content}")

        def onAImessage(self, message, agent_name):
            seen.append(f"ai:{agent_name}:{message.content}")
            raise RuntimeError("hooks must not break the turn")

    agent = runner.make(
        ScriptedChatModel(script=[AIMessage("hey")]), agent_class=Observed
    )

    assert runner.events(agent, "hello")[-1] == DONE
    assert seen == ["human:hello", "ai:Parity:hey"]


def test_configuration_callbacks_fire(runner):
    calls: list[str] = []
    configuration = runner.Configuration(
        system_prompt="p",
        on_tool_usage=lambda m: calls.append(f"usage:{m.tool_calls[0]['name']}"),
        on_tool_response=lambda m: calls.append(f"response:{m.content}"),
        on_ai_message=lambda m, name: calls.append(f"ai:{name}:{m.content}"),
        on_agent_calling=lambda name: calls.append(f"call:{name}"),
    )
    model = ScriptedChatModel(
        script=[_uses(_call("add", {"a": 1, "b": 2})), AIMessage("3")]
    )

    runner.events(runner.make(model, [add], configuration=configuration), "1+2")

    assert calls == [
        "call:Parity",
        "usage:add",
        "response:3",
        "call:Parity",
        "ai:Parity:3",
    ]


# --- pretty display ------------------------------------------------------------------


def test_markdown_pretty_display_reformats_the_final_answer(runner):
    model = ScriptedChatModel(
        script=[AIMessage("raw answer"), AIMessage("**Pretty** answer")]
    )

    events = runner.events(runner.make(model, markdown_pretty_display=True), "hi")

    assert events == [
        {"event": "call_model", "data": "Parity"},
        {"event": "ai_message", "data": "**Pretty** answer"},
        {"event": "message", "data": "**Pretty** answer"},
        DONE,
    ]
    assert "raw answer" in model.received[1][-1].content
