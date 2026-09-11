import time

import pytest
from naas_abi_core.services.agent.Agent import (
    _OFFICE_MODEL_INVOKE_TIMEOUT_S,
    _friendly_model_invoke_error,
    _invoke_office_chat_model,
    _office_chat_model_bind_kwargs,
)
from naas_abi_core.services.agent.context import (
    DOCUMENTS_RECURSION_LIMIT,
    SLIDES_RECURSION_LIMIT,
    documents_active_slug,
    documents_research_queries,
    documents_writes_completed,
    note_documents_write,
    note_slides_write,
    slides_active_slug,
    slides_research_queries,
    slides_writes_completed,
)


def test_friendly_model_invoke_error_rewrites_429() -> None:
    raw = (
        "Error code: 429 - {'error': {'message': 'Provider returned error', "
        "'code': 429, 'metadata': {'raw': "
        "'google/gemma-4-26b-a4b-it:free is temporarily rate-limited upstream.'}}}"
    )
    assert _friendly_model_invoke_error(Exception(raw)) == (
        "This model is rate limited. Pick another model in the agent menu and try again."
    )


def test_friendly_model_invoke_error_hides_json_dump() -> None:
    raw = "Error code: 500 - {'error': {'message': 'Provider returned error', 'code': 500}}"
    assert _friendly_model_invoke_error(Exception(raw)) == (
        "The model provider failed. Pick another model and try again."
    )


def test_friendly_model_invoke_error_names_context_window() -> None:
    token = slides_active_slug.set(None)
    try:
        raw = (
            "Error code: 400 - {'error': {'message': "
            "\"litellm.ContextWindowExceededError: This model's maximum context "
            "length is 262144 tokens. However, you requested 100000 output tokens "
            'and your prompt contains at least 162145 input tokens."}}'
        )
        assert _friendly_model_invoke_error(Exception(raw)) == (
            "This request exceeded the model's context window. "
            "Do not load whole files with embedded images, then try again."
        )
    finally:
        slides_active_slug.reset(token)


def test_friendly_model_invoke_error_context_window_on_slides() -> None:
    token = slides_active_slug.set("untitled-mtsg9zse")
    try:
        raw = (
            "Error code: 400 - ContextWindowExceededError: maximum context length"
        )
        text = _friendly_model_invoke_error(Exception(raw))
        assert "list_slides_sections" in text
        assert "read_file" in text
    finally:
        slides_active_slug.reset(token)


def test_friendly_model_invoke_error_recursion_without_slides() -> None:
    tokens = (
        slides_active_slug.set(None),
        slides_writes_completed.set(None),
        slides_research_queries.set(None),
    )
    try:
        assert _friendly_model_invoke_error(Exception("Recursion limit of 25 reached")) == (
            "The agent hit its step limit before finishing. "
            "Try a smaller request, or continue from what already landed."
        )
    finally:
        slides_active_slug.reset(tokens[0])
        slides_writes_completed.reset(tokens[1])
        slides_research_queries.reset(tokens[2])


def test_friendly_model_invoke_error_recursion_names_finished_writes() -> None:
    tokens = (
        slides_active_slug.set("untitled-mtrxak0l"),
        slides_writes_completed.set(None),
        slides_research_queries.set(None),
    )
    try:
        note_slides_write("slide 1")
        note_slides_write("slide 2")
        slides_research_queries.set(["iran 2026", "hormuz"])
        text = _friendly_model_invoke_error(Exception("Recursion limit of 80 reached."))
        assert f"{SLIDES_RECURSION_LIMIT}-step limit" in text
        assert "Finished: 2 web searches; wrote slide 1, slide 2." in text
        assert "The remaining slides were not written." in text
        assert "send the brief again" not in text
    finally:
        slides_active_slug.reset(tokens[0])
        slides_writes_completed.reset(tokens[1])
        slides_research_queries.reset(tokens[2])


def test_office_chat_model_bind_kwargs_omit_max_retries() -> None:
    kwargs = _office_chat_model_bind_kwargs()
    assert "max_retries" not in kwargs
    assert kwargs == {"timeout": _OFFICE_MODEL_INVOKE_TIMEOUT_S}


def test_invoke_office_chat_model_does_not_bind_max_retries() -> None:
    seen: dict[str, object] = {}

    class _Model:
        def bind(self, **kwargs):
            seen.update(kwargs)
            return self

        def invoke(self, messages):
            del messages
            return "ok"

    assert _invoke_office_chat_model(_Model(), []) == "ok"
    assert "max_retries" not in seen
    assert seen == {"timeout": _OFFICE_MODEL_INVOKE_TIMEOUT_S}


def test_invoke_office_chat_model_fails_before_stacked_retries(monkeypatch) -> None:
    monkeypatch.setattr(
        "naas_abi_core.services.agent.Agent._OFFICE_MODEL_INVOKE_TIMEOUT_S",
        0.2,
    )

    class _Slow:
        def bind(self, **kwargs):
            del kwargs
            return self

        def invoke(self, messages):
            del messages
            time.sleep(2)
            return "late"

    started = time.monotonic()
    with pytest.raises(TimeoutError, match="timed out"):
        _invoke_office_chat_model(_Slow(), [])
    assert time.monotonic() - started < 1.0
    assert _OFFICE_MODEL_INVOKE_TIMEOUT_S == 90.0


def test_friendly_model_invoke_error_timeout_on_documents() -> None:
    token = documents_active_slug.set("untitled-mtx5hdh4")
    try:
        text = _friendly_model_invoke_error(Exception("Request timed out."))
        assert "apply_documents_template" in text
        assert "read_file" in text
    finally:
        documents_active_slug.reset(token)


def test_friendly_model_invoke_error_context_window_on_documents() -> None:
    token = documents_active_slug.set("untitled-mtsg9zse")
    try:
        raw = (
            "Error code: 400 - ContextWindowExceededError: maximum context length"
        )
        text = _friendly_model_invoke_error(Exception(raw))
        assert "list_document_sections" in text
        assert "read_file" in text
    finally:
        documents_active_slug.reset(token)


def test_friendly_model_invoke_error_recursion_names_finished_document_writes() -> None:
    tokens = (
        documents_active_slug.set("untitled-mtrxak0l"),
        documents_writes_completed.set(None),
        documents_research_queries.set(None),
    )
    try:
        note_documents_write("section 1")
        note_documents_write("section 2")
        documents_research_queries.set(["iran 2026", "hormuz"])
        text = _friendly_model_invoke_error(Exception("Recursion limit of 80 reached."))
        assert f"{DOCUMENTS_RECURSION_LIMIT}-step limit" in text
        assert "Finished: 2 web searches; wrote section 1, section 2." in text
        assert "The remaining sections were not written." in text
        assert "send the brief again" not in text
    finally:
        documents_active_slug.reset(tokens[0])
        documents_writes_completed.reset(tokens[1])
        documents_research_queries.reset(tokens[2])
