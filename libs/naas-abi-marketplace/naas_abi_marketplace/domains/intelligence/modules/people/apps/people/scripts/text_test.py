"""Tests for the folding the exporter and the search API must agree on."""

from __future__ import annotations

from naas_abi_marketplace.domains.personnel.apps.people.scripts.text import (
    fold,
    query_tokens,
    search_text,
    truncate,
    words,
)


def test_fold_strips_accents_and_case() -> None:
    assert fold("Cédric Laümont") == "cedric laumont"


def test_words_splits_on_punctuation_but_keeps_plus() -> None:
    assert words("C++, Python 3.11") == ["c++", "python", "3", "11"]


def test_query_tokens_drops_stopwords_and_repeats() -> None:
    assert query_tokens("Head of the audit of audit") == ["head", "audit"]


def test_query_tokens_of_a_stopword_only_query_is_empty() -> None:
    assert query_tokens("of the") == []


def test_search_text_holds_each_word_once() -> None:
    text = search_text(
        {
            "full_name": ["Cédric Laumont"],
            "skills": ["Audit", "audit", "IFRS"],
        }
    )
    assert text.split() == ["cedric", "laumont", "audit", "ifrs"]


def test_search_text_of_nothing_is_empty() -> None:
    assert search_text({"about": [""], "skills": []}) == ""


def test_truncate_cuts_at_a_word_boundary() -> None:
    assert truncate("one two three four", 9) == "one two …"


def test_truncate_leaves_short_text_alone() -> None:
    assert truncate("short", 40) == "short"
