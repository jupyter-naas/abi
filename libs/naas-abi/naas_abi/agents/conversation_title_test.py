"""Unit tests for the shared Chat title helper."""

from __future__ import annotations

from types import SimpleNamespace

from naas_abi.agents.conversation_title import (
    conversation_title_from_prompt,
    first_user_prompt,
)


def test_conversation_title_clips_at_fifty_chars():
    short = "Write an executive memo on two firms"
    assert conversation_title_from_prompt(short) == short
    long = "A" * 51
    assert conversation_title_from_prompt(long) == ("A" * 50) + "..."


def test_conversation_title_trims_and_ignores_empty():
    assert conversation_title_from_prompt("  hello  ") == "hello"
    assert conversation_title_from_prompt("   ") == ""


def test_first_user_prompt_prefers_the_original_brief():
    messages = [
        SimpleNamespace(role="user", content="Write an executive memo on two firms"),
        SimpleNamespace(role="assistant", content="Working on it."),
        SimpleNamespace(role="user", content="continue"),
    ]
    assert (
        first_user_prompt("continue", messages)
        == "Write an executive memo on two firms"
    )


def test_first_user_prompt_falls_back_to_the_current_send():
    assert first_user_prompt("  draft a note  ", []) == "draft a note"
    assert first_user_prompt("draft a note", None) == "draft a note"
