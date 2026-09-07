"""Unit tests for deriving a deck title from the user's brief."""

from __future__ import annotations

from naas_abi.agents.slides.title import (
    derive_deck_title,
    is_placeholder_deck_title,
    resolve_deck_title,
)


def test_derives_the_topic_from_a_french_brief():
    assert (
        derive_deck_title("fais des slides sur les matériaux de construction")
        == "Matériaux de construction"
    )


def test_derives_the_topic_from_a_polite_french_brief():
    assert (
        derive_deck_title("Peux-tu me préparer une présentation sur l'hydrogène vert ?")
        == "Hydrogène vert"
    )


def test_derives_the_topic_from_an_english_brief():
    assert (
        derive_deck_title("Make a deck about the latest news in AI.")
        == "Latest news in AI"
    )


def test_keeps_proper_nouns_as_written():
    assert (
        derive_deck_title(
            "fais des slides sur Saint-Gobain et les matériaux de construction"
        )
        == "Saint-Gobain et les matériaux de construction"
    )


def test_caps_a_long_brief_on_a_word_boundary():
    derived = derive_deck_title(
        "fais des slides sur les matériaux de construction durables utilisés "
        "dans le bâtiment en France et en Allemagne aujourd'hui"
    )
    assert derived == "Matériaux de construction durables utilisés dans le bâtiment"
    assert len(derived) <= 64


def test_ignores_a_message_that_is_not_a_deck_request():
    assert derive_deck_title("change the cover title to REFRESH PROBE ALPHA") == ""
    assert derive_deck_title("what is the capital of France?") == ""
    assert derive_deck_title("") == ""


def test_ignores_a_deck_request_with_no_topic():
    assert derive_deck_title("make me a deck") == ""


def test_recognises_placeholder_titles():
    assert is_placeholder_deck_title("Untitled presentation")
    assert is_placeholder_deck_title("untitled-mtq5mtz0")
    assert is_placeholder_deck_title("Untitled Mtq5Mtz0")
    assert is_placeholder_deck_title("Presentation Title")
    assert is_placeholder_deck_title("Nouvelle présentation")
    assert is_placeholder_deck_title("  ")
    assert not is_placeholder_deck_title("Matériaux de construction")


def test_resolve_keeps_a_real_title_from_the_model():
    assert (
        resolve_deck_title("Matériaux de construction", brief="fais des slides sur ça")
        == "Matériaux de construction"
    )


def test_resolve_rescues_a_raw_brief_passed_as_the_title():
    assert (
        resolve_deck_title("fais des slides sur les matériaux de construction")
        == "Matériaux de construction"
    )


def test_resolve_falls_back_to_the_turn_brief():
    assert (
        resolve_deck_title(
            "Untitled presentation",
            brief="fais des slides sur les matériaux de construction",
        )
        == "Matériaux de construction"
    )
    assert (
        resolve_deck_title("", brief="Make a deck about the latest news in AI")
        == "Latest news in AI"
    )


def test_resolve_returns_empty_when_there_is_nothing_to_go_on():
    assert resolve_deck_title("   ", brief="  ") == ""
    assert resolve_deck_title("Untitled presentation", brief="hello") == ""
