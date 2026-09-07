from __future__ import annotations

import json
from unittest.mock import patch

from naas_abi_core.services.coding_environment.adapters.secondary.OpencodeHarnessClient import (
    _extract_text,
    create_session,
    is_healthy,
    run_task,
)


def test_extract_text_joins_parts() -> None:
    assert _extract_text([{"type": "text", "text": "hello"}, {"text": "world"}]) == (
        "hello\nworld"
    )


def test_is_healthy_true() -> None:
    payload = json.dumps({"healthy": True}).encode()

    class FakeResp:
        def read(self) -> bytes:
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        assert is_healthy("http://127.0.0.1:18200") is True


def test_create_session_parses_id() -> None:
    payload = json.dumps({"id": "sess-1"}).encode()

    class FakeResp:
        def read(self) -> bytes:
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        assert create_session("http://127.0.0.1:18200") == "sess-1"


def test_run_task_unhealthy() -> None:
    with patch(
        "naas_abi_core.services.coding_environment.adapters.secondary.OpencodeHarnessClient.wait_for_healthy",
        return_value=False,
    ):
        result = run_task("http://127.0.0.1:18200", "fix tests")
    assert result["error"]
    assert "not healthy" in result["error"]
