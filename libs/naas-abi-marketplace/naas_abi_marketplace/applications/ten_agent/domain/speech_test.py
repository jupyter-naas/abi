from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Any

from naas_abi_marketplace.applications.ten_agent.domain.speech import (
    DEFAULT_FILLER,
    VOICE_STYLE,
    SpeechStream,
    speakable,
    to_speech,
    voice_preamble,
    voice_thread_id,
)


def _spoken(
    chunks: Sequence[str | dict[str, Any]], filler: str | None = DEFAULT_FILLER
) -> list[str]:
    async def source() -> AsyncIterator[str | dict[str, Any]]:
        for chunk in chunks:
            yield chunk

    async def collect() -> list[str]:
        return [s async for s in speakable(source(), filler)]

    return asyncio.run(collect())


def test_to_speech_strips_markdown_a_tts_would_read_aloud() -> None:
    assert to_speech("## **Open deals**") == "Open deals"
    assert to_speech("- See [the report](https://x.io/r) now") == "See the report now"
    assert to_speech("1. Visit https://naas.ai today") == "Visit today"
    assert to_speech("Done. <!-- abi-chat:0123abcd -->") == "Done."
    assert to_speech("| Acme | 40k |") == "Acme, 40k"
    assert to_speech("|---|---|") == ""
    assert to_speech("Use `kg_sparql_query` and snake_case_names") == (
        "Use kg_sparql_query and snake_case_names"
    )


def test_markers_split_across_deltas_are_still_removed() -> None:
    assert _spoken(["You have *", "*three", "** open deals.", " Acme leads."]) == [
        "You have three open deals. ",
        "Acme leads. ",
    ]


def test_sentences_are_released_as_soon_as_they_end() -> None:
    stream = SpeechStream()
    assert stream.feed("Paris is the capital.") == []
    assert stream.feed(" It has") == ["Paris is the capital."]
    assert stream.flush() == ["It has"]


def test_fenced_tool_output_is_never_spoken() -> None:
    chunks = [
        "Here it is.\n```\nSELECT ?s WHERE",
        " { ?s ?p ?o }\n```\n",
        "Three rows.",
    ]
    assert _spoken(chunks) == ["Here it is. ", "Three rows. "]


def test_first_tool_call_becomes_a_spoken_filler_once() -> None:
    chunks: list[str | dict[str, Any]] = [
        {"event": "tool_usage", "tool": "crm_search"},
        {"event": "tool_response", "output": "```json {...}```"},
        {"event": "tool_usage", "tool": "crm_search"},
        "Three deals are open.",
    ]
    assert _spoken(chunks) == [f"{DEFAULT_FILLER} ", "Three deals are open. "]


def test_no_filler_when_the_agent_already_spoke() -> None:
    chunks: list[str | dict[str, Any]] = [
        "Let me look.\n",
        {"event": "tool_usage", "tool": "crm_search"},
        "Done.",
    ]
    assert _spoken(chunks) == ["Let me look. ", "Done. "]
    assert _spoken([{"event": "tool_usage", "tool": "x"}, "Ok."], filler=None) == [
        "Ok. "
    ]


def test_voice_thread_is_stable_per_session_and_scoped_to_the_user() -> None:
    assert voice_thread_id("call-1", "u1") == voice_thread_id("call-1", "u1")
    assert voice_thread_id("call-1", "u1") != voice_thread_id("call-1", "u2")
    assert voice_thread_id(None, "u1") != voice_thread_id(None, "u1")
    assert voice_thread_id("../../etc", "u1").startswith("voice-u1-")
    assert "etc" not in voice_thread_id("../../etc", "u1")


def test_voice_preamble_always_carries_the_speaking_style() -> None:
    assert voice_preamble(None) == VOICE_STYLE
    assert voice_preamble("User: Ada").startswith(VOICE_STYLE)
    assert voice_preamble("User: Ada").endswith("User: Ada")
