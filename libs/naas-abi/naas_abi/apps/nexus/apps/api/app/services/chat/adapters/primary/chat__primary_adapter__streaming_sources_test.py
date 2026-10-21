"""Source URLs the streaming adapter lifts out of tool responses."""

from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__streaming import (
    _extract_urls_from_text,
)


def test_a_quoted_url_is_listed_once_without_its_quotes() -> None:
    output = (
        '{"website": "https://www.axa.com", "logo": "https://cdn.example.com/a.png"}'
        "\nSee https://www.axa.com for details."
    )

    assert _extract_urls_from_text(output) == [
        "https://www.axa.com",
        "https://cdn.example.com/a.png",
    ]


def test_a_python_repr_url_stops_at_the_single_quote() -> None:
    assert _extract_urls_from_text("{'uri': 'http://ontology.naas.ai/abi/1'}") == [
        "http://ontology.naas.ai/abi/1"
    ]


def test_trailing_punctuation_is_still_trimmed() -> None:
    assert _extract_urls_from_text("Read https://example.com/a.") == ["https://example.com/a"]
