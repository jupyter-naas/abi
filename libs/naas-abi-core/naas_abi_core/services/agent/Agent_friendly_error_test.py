from naas_abi_core.services.agent.Agent import _friendly_model_invoke_error
from naas_abi_core.services.agent.context import (
    SLIDES_RECURSION_LIMIT,
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
