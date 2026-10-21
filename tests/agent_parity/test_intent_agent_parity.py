"""IntentAgent behaviour both runtimes must share: intent mapping and routing."""

from __future__ import annotations

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from tests.agent_parity.harness import ScriptedChatModel, TableEmbeddings

DONE = {"event": "done", "data": "[DONE]"}


@tool
def add(a: int, b: int) -> int:
    """Add two numbers.

    Args:
        a (int): first
        b (int): second
    """
    return a + b


def _no_defaults(**kwargs):
    return {"enable_default_intents": False, "markdown_pretty_display": False, **kwargs}


def test_raw_intent_answers_without_calling_the_model(runner):
    model = ScriptedChatModel(script=[AIMessage("should not be used")])
    intents = [
        runner.Intent(
            "open the pod bay doors", runner.IntentType.RAW, "I'm afraid I can't."
        )
    ]
    agent = runner.make_intent(
        model, intents=intents, embedding_model=TableEmbeddings(), **_no_defaults()
    )

    events = runner.events(agent, "open the pod bay doors")

    assert events == [
        {"event": "ai_message", "data": "I'm afraid I can't."},
        {"event": "message", "data": "I'm afraid I can't."},
        DONE,
    ]
    assert model.received == []


def test_no_matching_intent_calls_the_model(runner):
    model = ScriptedChatModel(script=[AIMessage("model answer")])
    intents = [runner.Intent("open the pod bay doors", runner.IntentType.RAW, "no")]
    agent = runner.make_intent(
        model, intents=intents, embedding_model=TableEmbeddings(), **_no_defaults()
    )

    assert runner.events(agent, "what's the weather") == [
        {"event": "call_model", "data": "Parity"},
        {"event": "ai_message", "data": "model answer"},
        {"event": "message", "data": "model answer"},
        DONE,
    ]


def test_markdown_pretty_display_is_on_by_default(runner):
    model = ScriptedChatModel(script=[AIMessage("raw"), AIMessage("**pretty**")])
    agent = runner.make_intent(
        model, embedding_model=TableEmbeddings(), enable_default_intents=False
    )

    assert runner.events(agent, "anything")[-2:] == [
        {"event": "message", "data": "**pretty**"},
        DONE,
    ]


def test_tool_intent_injects_rules_into_the_system_prompt(runner):
    model = ScriptedChatModel(
        script=[
            AIMessage(
                "",
                tool_calls=[
                    {
                        "name": "add",
                        "args": {"a": 1, "b": 2},
                        "id": "c1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage("3"),
        ]
    )
    intents = [runner.Intent("add two numbers", runner.IntentType.TOOL, "add")]
    agent = runner.make_intent(
        model,
        [add],
        intents=intents,
        embedding_model=TableEmbeddings(),
        **_no_defaults(),
    )

    events = runner.events(agent, "add two numbers")

    system = model.received[0][0].content
    assert "<intents_rules>" in system
    assert "-Mapped intent: `add two numbers`, tool to call: `add`" in system
    assert {"event": "tool_response", "data": "3"} in events
    assert events[-2:] == [{"event": "message", "data": "3"}, DONE]


def test_close_tool_intents_ask_the_user_to_choose(runner, monkeypatch):
    monkeypatch.setattr(runner.IntentAgent, "_extract_entities", lambda self, text: [])
    embeddings = TableEmbeddings(
        {
            "sum values": [1.0, 0.0, 0.0],
            "sum the numbers": [1.0, 0.10, 0.0],
            "total the numbers": [1.0, 0.0, 0.12],
        }
    )
    intents = [
        runner.Intent("sum the numbers", runner.IntentType.TOOL, "add"),
        runner.Intent("total the numbers", runner.IntentType.TOOL, "total"),
    ]
    model = ScriptedChatModel(
        script=[
            AIMessage(
                "",
                tool_calls=[
                    {
                        "name": "filter_intents",
                        "args": {"bool_list": [True, True]},
                        "id": "f1",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )
    agent = runner.make_intent(
        model,
        [add],
        intents=intents,
        embedding_model=embeddings,
        direct_intent_score=1.01,
        **_no_defaults(),
    )

    events = runner.events(agent, "sum values")

    menu = events[0]
    assert menu["event"] == "ai_message"
    assert menu["data"].startswith(
        "I found multiple intents that could handle your request:"
    )
    assert "1. **add** (confidence: 99.5%)" in menu["data"]
    assert "2. **total** (confidence: 99.3%)" in menu["data"]
    assert events[-1] == DONE
    assert len(model.received) == 1


def test_numeric_reply_without_a_matching_agent_falls_back_to_the_model(
    runner, monkeypatch
):
    monkeypatch.setattr(runner.IntentAgent, "_extract_entities", lambda self, text: [])
    embeddings = TableEmbeddings(
        {
            "sum values": [1.0, 0.0, 0.0],
            "sum the numbers": [1.0, 0.10, 0.0],
            "total the numbers": [1.0, 0.0, 0.12],
        }
    )
    intents = [
        runner.Intent("sum the numbers", runner.IntentType.TOOL, "add"),
        runner.Intent("total the numbers", runner.IntentType.TOOL, "total"),
    ]
    filter_call = AIMessage(
        "",
        tool_calls=[
            {
                "name": "filter_intents",
                "args": {"bool_list": [True, True]},
                "id": "f1",
                "type": "tool_call",
            }
        ],
    )
    model = ScriptedChatModel(
        script=[filter_call, AIMessage("ok, using the first one")]
    )
    agent = runner.make_intent(
        model,
        [add],
        intents=intents,
        embedding_model=embeddings,
        direct_intent_score=1.01,
        **_no_defaults(),
    )
    runner.events(agent, "sum values")

    events = runner.events(agent, "1")

    assert events[0] == {"event": "call_model", "data": "Parity"}
    assert events[-2:] == [
        {"event": "message", "data": "ok, using the first one"},
        DONE,
    ]


def test_embedding_failure_degrades_to_the_model(runner):
    model = ScriptedChatModel(script=[AIMessage("still here")])
    intents = [runner.Intent("open the pod bay doors", runner.IntentType.RAW, "no")]
    agent = runner.make_intent(
        model,
        intents=intents,
        embedding_model=TableEmbeddings(fail=True),
        **_no_defaults(),
    )

    assert runner.events(agent, "open the pod bay doors")[-2:] == [
        {"event": "message", "data": "still here"},
        DONE,
    ]


def test_default_intents_answer_greetings(runner):
    from naas_abi_core.services.agent.intents.default_intents import DEFAULT_INTENTS

    greeting = next(i for i in DEFAULT_INTENTS if i.intent_type.value == "raw")
    model = ScriptedChatModel(script=[AIMessage("unused")])
    agent = runner.make_intent(
        model, embedding_model=TableEmbeddings(), markdown_pretty_display=False
    )

    events = runner.events(agent, greeting.intent_value)

    assert events[0] == {"event": "ai_message", "data": greeting.intent_target}
    assert model.received == []
