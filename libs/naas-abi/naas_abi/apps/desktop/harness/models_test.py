"""Wire-format contract for normalized harness events.

The dicts produced by ``to_dict()`` must stay byte-compatible with what
the web UI consumes over SSE today (the legacy OpencodeClient shapes).
"""

from desktop.harness.models import (
    DoneEvent,
    ErrorEvent,
    HarnessModel,
    HarnessProvider,
    ReasoningEvent,
    TextEvent,
    ToolEvent,
)


def test_text_event_matches_legacy_wire_shape() -> None:
    event = TextEvent(text="Hello world", part_id="prt_1")
    assert event.to_dict() == {
        "type": "text",
        "text": "Hello world",
        "part_id": "prt_1",
    }


def test_reasoning_event_matches_legacy_wire_shape() -> None:
    assert ReasoningEvent().to_dict() == {"type": "reasoning"}


def test_tool_event_matches_legacy_wire_shape() -> None:
    event = ToolEvent(call_id="call_1", name="bash", status="running", title="ls -la")
    assert event.to_dict() == {
        "type": "tool",
        "tool": "bash",
        "status": "running",
        "title": "ls -la",
        "call_id": "call_1",
    }


def test_tool_event_optional_input_output_are_superset_keys() -> None:
    event = ToolEvent(
        call_id="call_2",
        name="read",
        status="completed",
        title="main.py",
        input={"filePath": "main.py"},
        output="print('hi')",
    )
    payload = event.to_dict()
    assert payload["input"] == {"filePath": "main.py"}
    assert payload["output"] == "print('hi')"
    # Legacy keys must still be present and unchanged.
    assert payload["type"] == "tool"
    assert payload["tool"] == "read"


def test_error_event_matches_legacy_wire_shape() -> None:
    assert ErrorEvent(message="boom").to_dict() == {"type": "error", "message": "boom"}


def test_done_event_serializes_as_complete() -> None:
    assert DoneEvent(text="final").to_dict() == {"type": "complete", "text": "final"}
    assert DoneEvent().to_dict() == {"type": "complete", "text": ""}


def test_provider_and_model_match_api_models_shape() -> None:
    provider = HarnessProvider(
        id="anthropic",
        name="Anthropic",
        models=(HarnessModel(id="claude-4", name="Claude 4"),),
    )
    assert provider.to_dict() == {
        "id": "anthropic",
        "name": "Anthropic",
        "models": [
            {"id": "claude-4", "name": "Claude 4", "supports_tools": True},
        ],
    }
