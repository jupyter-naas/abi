"""View-only tool-result compaction before call_model.invoke."""

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from naas_abi_core.services.agent.Agent import (
    _MAX_TOOL_RESULT_CHARS,
    _OLD_TOOL_RESULT_STUB,
    _truncate_tool_content,
    compact_old_tool_messages,
)


def _tool(
    content: str,
    name: str,
    tool_call_id: str,
    message_id: str | None = None,
) -> ToolMessage:
    return ToolMessage(
        content=content,
        name=name,
        tool_call_id=tool_call_id,
        id=message_id or tool_call_id,
    )


def test_compact_returns_same_list_when_nothing_to_shrink() -> None:
    messages: list[AnyMessage] = [
        HumanMessage(content="hi", id="h1"),
        AIMessage(content="ok", id="a1"),
    ]
    assert compact_old_tool_messages(messages) is messages


def test_compact_stubs_prior_turn_reads_keeps_last_list_and_write() -> None:
    prior_read = "x" * 200
    list_body = '{"sections": ["Cover"]}'
    write_body = '{"slug": "deck", "ok": true}'
    messages: list[AnyMessage] = [
        HumanMessage(content="first", id="h1"),
        _tool(prior_read, "read_slides_section", "c1"),
        _tool(list_body, "list_slides_sections", "c2"),
        _tool(write_body, "write_slides_sections", "c3"),
        HumanMessage(content="next", id="h2"),
    ]

    out = compact_old_tool_messages(messages)

    assert out is not messages
    assert out[0] is messages[0]
    stubbed = out[1]
    assert isinstance(stubbed, ToolMessage)
    assert stubbed.content == _OLD_TOOL_RESULT_STUB
    assert stubbed.tool_call_id == "c1"
    assert stubbed.name == "read_slides_section"
    assert out[2].content == list_body
    assert out[3].content == write_body
    assert out[4] is messages[4]


def test_compact_truncates_huge_current_turn_read() -> None:
    huge = "<html>" + ("A" * (_MAX_TOOL_RESULT_CHARS + 500))
    messages: list[AnyMessage] = [
        HumanMessage(content="edit slide 2", id="h1"),
        _tool(huge, "read_slides_deck", "c1"),
    ]

    out = compact_old_tool_messages(messages)

    truncated = out[1]
    assert isinstance(truncated, ToolMessage)
    assert isinstance(truncated.content, str)
    assert truncated.content.startswith("<html>")
    assert truncated.content.endswith("...[truncated]...")
    assert len(truncated.content) < len(huge)
    assert truncated.tool_call_id == "c1"


def test_compact_keeps_small_current_turn_reads() -> None:
    section = "<section>one slide</section>"
    messages: list[AnyMessage] = [
        HumanMessage(content="tweak cover", id="h1"),
        _tool(section, "read_slides_section", "c1"),
    ]

    out = compact_old_tool_messages(messages)

    assert out is messages
    assert out[1].content == section


def test_compact_truncates_huge_last_write() -> None:
    huge_write = "W" * (_MAX_TOOL_RESULT_CHARS + 10)
    messages: list[AnyMessage] = [
        HumanMessage(content="old", id="h1"),
        _tool(huge_write, "write_slides_deck", "c1"),
        HumanMessage(content="new", id="h2"),
    ]

    out = compact_old_tool_messages(messages)

    truncated = out[1]
    assert isinstance(truncated, ToolMessage)
    assert truncated.name == "write_slides_deck"
    assert isinstance(truncated.content, str)
    assert truncated.content.endswith("...[truncated]...")
    assert len(truncated.content) <= _MAX_TOOL_RESULT_CHARS + len("\n...[truncated]...")


def test_compact_keeps_handoff_and_system_messages() -> None:
    messages: list[AnyMessage] = [
        SystemMessage(content="sys"),
        HumanMessage(content="go", id="h1"),
        _tool("__handoff__:Slides", "transfer_to_Slides", "t1"),
        HumanMessage(content="again", id="h2"),
        _tool("__handoff__:Slides", "transfer_to_Slides", "t2"),
    ]

    assert compact_old_tool_messages(messages) is messages


def test_compact_keeps_last_replace_in_as_write() -> None:
    replace_body = '{"ok": true, "replacements": 1}'
    messages: list[AnyMessage] = [
        HumanMessage(content="old", id="h1"),
        _tool("<section>old</section>", "read_slides_section", "c1"),
        _tool(replace_body, "replace_in_slides_deck", "c2"),
        HumanMessage(content="new", id="h2"),
    ]

    out = compact_old_tool_messages(messages)

    assert out[1].content == _OLD_TOOL_RESULT_STUB
    assert out[2].content == replace_body


def test_compact_stubs_older_list_when_a_newer_list_exists() -> None:
    messages: list[AnyMessage] = [
        HumanMessage(content="old", id="h1"),
        _tool('{"sections": ["A"]}', "list_slides_sections", "c1"),
        HumanMessage(content="new", id="h2"),
        _tool('{"sections": ["A", "B"]}', "list_slides_sections", "c2"),
    ]

    out = compact_old_tool_messages(messages)

    assert out[1].content == _OLD_TOOL_RESULT_STUB
    assert out[3].content == '{"sections": ["A", "B"]}'


def test_truncate_tool_content_for_sse() -> None:
    small = "ok"
    assert _truncate_tool_content(small, _MAX_TOOL_RESULT_CHARS) is small
    huge = "Z" * (_MAX_TOOL_RESULT_CHARS + 20)
    out = _truncate_tool_content(huge, _MAX_TOOL_RESULT_CHARS)
    assert out.endswith("...[truncated]...")
    assert len(out) < len(huge)
