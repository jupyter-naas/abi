"""Unit tests for speech text preparation and language routing (no network)."""

from naas_abi.apps.nexus.apps.api.app.api.endpoints.speech import (
    MAX_INPUT_CHARS,
    detect_speech_language,
    prepare_speech_text,
)


def test_prepare_speech_text_strips_markdown() -> None:
    raw = "# Title\n\n**Hello** [Naas](https://naas.ai) and `code`\n\n```python\nprint(1)\n```"
    assert prepare_speech_text(raw) == "Title Hello Naas and code."


def test_prepare_speech_text_truncates() -> None:
    raw = "a" * (MAX_INPUT_CHARS + 50)
    out = prepare_speech_text(raw)
    assert len(out) == MAX_INPUT_CHARS
    assert out.endswith("...")


def test_prepare_speech_text_empty() -> None:
    assert prepare_speech_text("   ") == ""
    assert prepare_speech_text("```\nonly code\n```") == ""


def test_detect_speech_language_french() -> None:
    text = "Bonjour Jeremy. Je t'entends parfaitement. Je vais très bien, merci."
    assert detect_speech_language(text) == "fr"


def test_detect_speech_language_english() -> None:
    text = "Hello Jeremy. I hear you perfectly. I am doing very well, thank you."
    assert detect_speech_language(text) == "en"
