"""Unit tests for deriving a document title from the user's brief."""

from __future__ import annotations

from naas_abi.agents.documents.title import (
    auto_document_title,
    derive_document_title,
    is_placeholder_document_title,
    resolve_document_title,
)


def test_derives_the_topic_from_a_french_brief():
    assert (
        derive_document_title("fais des sections sur les matériaux de construction")
        == "Matériaux de construction"
    )


def test_derives_the_topic_from_a_polite_french_brief():
    assert (
        derive_document_title("Peux-tu me préparer une document sur l'hydrogène vert ?")
        == "Hydrogène vert"
    )


def test_derives_the_topic_from_an_english_brief():
    assert (
        derive_document_title("Make a document about the latest news in AI.")
        == "Latest news in AI"
    )


def test_keeps_proper_nouns_as_written():
    assert (
        derive_document_title(
            "fais des sections sur Saint-Gobain et les matériaux de construction"
        )
        == "Saint-Gobain et les matériaux de construction"
    )


def test_caps_a_long_brief_on_a_word_boundary():
    derived = derive_document_title(
        "fais des sections sur les matériaux de construction durables utilisés "
        "dans le bâtiment en France et en Allemagne aujourd'hui"
    )
    assert derived == "Matériaux de construction durables utilisés dans le bâtiment"
    assert len(derived) <= 64


def test_ignores_a_message_that_is_not_a_document_request():
    assert derive_document_title("change the cover title to REFRESH PROBE ALPHA") == ""
    assert derive_document_title("what is the capital of France?") == ""
    assert derive_document_title("") == ""


def test_ignores_a_document_request_with_no_topic():
    assert derive_document_title("make me a document") == ""


def test_recognises_placeholder_titles():
    assert is_placeholder_document_title("Untitled document")
    assert is_placeholder_document_title("untitled-mtq5mtz0")
    assert is_placeholder_document_title("Untitled Mtq5Mtz0")
    assert is_placeholder_document_title("Presentation Title")
    assert is_placeholder_document_title("Nouvelle document")
    assert is_placeholder_document_title("  ")
    assert not is_placeholder_document_title("Matériaux de construction")


def test_resolve_keeps_a_real_title_from_the_model():
    assert (
        resolve_document_title("Matériaux de construction", brief="fais des sections sur ça")
        == "Matériaux de construction"
    )


def test_resolve_rescues_a_raw_brief_passed_as_the_title():
    assert (
        resolve_document_title("fais des sections sur les matériaux de construction")
        == "Matériaux de construction"
    )


def test_resolve_falls_back_to_the_turn_brief():
    assert (
        resolve_document_title(
            "Untitled document",
            brief="fais des sections sur les matériaux de construction",
        )
        == "Matériaux de construction"
    )
    assert (
        resolve_document_title("", brief="Make a document about the latest news in AI")
        == "Latest news in AI"
    )


def test_resolve_returns_empty_when_there_is_nothing_to_go_on():
    assert resolve_document_title("   ", brief="  ") == ""
    assert resolve_document_title("Untitled document", brief="hello") == ""


def test_derives_the_topic_from_an_executive_memo_brief():
    assert (
        derive_document_title("Write an executive memo on two audit firms")
        == "Two audit firms"
    )


def test_auto_title_falls_back_to_the_chat_clip():
    brief = "What is going on in France right now?"
    assert derive_document_title(brief) == ""
    assert auto_document_title(brief) == brief
