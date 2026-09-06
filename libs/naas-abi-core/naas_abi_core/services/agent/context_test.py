from __future__ import annotations

from naas_abi_core.services.agent.context import (
    slides_active_slug,
    slides_creation_intent,
    slides_turn_active,
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
