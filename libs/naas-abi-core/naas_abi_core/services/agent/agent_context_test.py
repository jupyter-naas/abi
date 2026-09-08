"""Tests for services/agent/context.py.

Named agent_context_test.py, not context_test.py: pytest imports test modules
by basename here and engine/context_test.py already owns that name.
"""

from __future__ import annotations

from naas_abi_core.services.agent.context import (
    SLIDES_RECURSION_LIMIT,
    note_slides_write,
    slides_active_slug,
    slides_creation_intent,
    slides_research_queries,
    slides_step_limit_message,
    slides_turn_active,
    slides_writes_completed,
)


def test_slides_turn_active_for_an_open_deck() -> None:
    tokens = (slides_active_slug.set("my-deck"), slides_creation_intent.set(False))
    try:
        assert slides_turn_active() is True
    finally:
        slides_active_slug.reset(tokens[0])
        slides_creation_intent.reset(tokens[1])


def test_slides_turn_active_when_creating_from_main_chat() -> None:
    """No deck open yet, but the user asked for one. Still a slides turn."""
    tokens = (slides_active_slug.set(None), slides_creation_intent.set(True))
    try:
        assert slides_turn_active() is True
    finally:
        slides_active_slug.reset(tokens[0])
        slides_creation_intent.reset(tokens[1])


def test_slides_turn_inactive_for_an_ordinary_chat_turn() -> None:
    tokens = (slides_active_slug.set(None), slides_creation_intent.set(False))
    try:
        assert slides_turn_active() is False
    finally:
        slides_active_slug.reset(tokens[0])
        slides_creation_intent.reset(tokens[1])


def test_slides_turn_ignores_a_blank_slug() -> None:
    tokens = (slides_active_slug.set("   "), slides_creation_intent.set(False))
    try:
        assert slides_turn_active() is False
    finally:
        slides_active_slug.reset(tokens[0])
        slides_creation_intent.reset(tokens[1])


def test_slides_recursion_limit_is_160() -> None:
    assert SLIDES_RECURSION_LIMIT == 160


def test_slides_step_limit_message_names_what_finished() -> None:
    tokens = (
        slides_writes_completed.set(None),
        slides_research_queries.set(["q1"]),
    )
    try:
        note_slides_write("slide 1")
        text = slides_step_limit_message()
        assert "160-step limit" in text
        assert "Finished: 1 web search; wrote slide 1." in text
        assert "The remaining slides were not written." in text
        assert "send the brief again" not in text
    finally:
        slides_writes_completed.reset(tokens[0])
        slides_research_queries.reset(tokens[1])
