from naas_abi_core.services.agent.OpencodeSessionService import OpencodeSessionService


def test_extract_file_events_maps_supported_tools():
    parts = [
        {"type": "tool_use", "name": "read", "input": {"path": "a.py"}},
        {
            "type": "tool_use",
            "name": "write",
            "input": {"path": "b.py", "diff": "@@"},
        },
        {
            "type": "tool_use",
            "name": "edit",
            "input": {"path": "c.py", "new_string": "x"},
        },
        {
            "type": "tool_use",
            "name": "bash",
            "input": {"command": "pytest"},
        },
        {"type": "tool_use", "name": "glob", "input": {"pattern": "*.py"}},
    ]

    events = OpencodeSessionService.extract_file_events(parts)

    assert len(events) == 4
    assert events[0]["event_type"] == "read"
    assert events[1]["event_type"] == "write"
    assert events[2]["event_type"] == "edit"
    assert events[3]["event_type"] == "bash"


def test_extract_text_joins_text_like_parts():
    parts = [
        {"type": "text", "text": "hello"},
        {"type": "text", "content": "world"},
    ]

    assert OpencodeSessionService.extract_text(parts) == "hello\nworld"
