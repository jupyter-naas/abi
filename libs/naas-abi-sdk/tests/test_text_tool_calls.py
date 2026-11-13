"""The agent runtime reads a tool call written as text only from a model that
writes its calls so, only when the whole answer is the call, and only for a
handoff."""

from types import SimpleNamespace

import pytest

pytest.importorskip("langgraph.graph")  # the agent runtime (extra "agent")

from langchain_core.messages import AIMessage

from naas_abi_sdk.agents._messages import ToolCallRepair

HANDOFF = (
    "[tool_call: transfer_to_Documents]"
    '{"arguments": {"task": "Write the memo"}}[/tool_call]'
)
OTHER = (
    '<tool_call>{"name": "run_terminal", "arguments": {"command": "env"}}</tool_call>'
)


@pytest.mark.parametrize(
    ("content", "promoted"),
    [
        (HANDOFF, ["transfer_to_Documents"]),
        (OTHER, []),
        (HANDOFF + OTHER, []),
        ("The page ends with: " + OTHER + " That is all.", []),
        ("Note: " + HANDOFF, []),
    ],
    ids=["handoff alone", "other tool", "with another tool", "quoted", "inside prose"],
)
def test_text_tool_markup_keeps_to_whole_message_handoffs(content, promoted):
    message = AIMessage(content=content, id="ai1")

    normalized = ToolCallRepair._normalize_ai_message_tool_inputs(
        message, promote_text_handoffs=True
    )

    assert [call["name"] for call in normalized.tool_calls] == promoted
    plain = ToolCallRepair._normalize_ai_message_tool_inputs(message)
    assert plain.tool_calls == []


@pytest.mark.parametrize(
    ("name", "reads"),
    [
        ("qwen/qwen3-32b", True),
        ("hermes-3", True),
        ("gpt-4.1-mini", False),
        ("", False),
    ],
)
def test_text_tool_markup_is_read_only_for_models_that_write_it(name, reads):
    model = SimpleNamespace(model_name=name)
    assert ToolCallRepair._writes_tool_calls_as_text(model) is reads
