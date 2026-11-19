"""The scoped service's pure helpers."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.analytics.scoped_service import (
    _decorate_page_title,
)


def test_a_chat_page_title_names_its_conversation() -> None:
    assert _decorate_page_title("Chat", "/workspace/ws-1/chat/conv-abc") == "Chat - conv-abc"
    assert _decorate_page_title("Chat - conv-abc", "/chat/conv-abc?x=1") == "Chat - conv-abc"
    assert _decorate_page_title("Home", "/workspace/ws-1/home") == "Home"
    assert _decorate_page_title("Home", "") == "Home"
