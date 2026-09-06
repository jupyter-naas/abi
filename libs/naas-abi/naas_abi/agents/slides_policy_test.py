from naas_abi.agents.slides_policy import (
    DEFAULT_SLIDES_MODEL,
    MAX_SLIDES_SEARCHES,
    apply_slides_model_override,
    attach_slides_research_note,
    bind_slides_research_policy,
    is_weak_slides_model,
    note_slides_web_search,
    openrouter_slides_model_id,
    reject_unresearched_slides_write,
    resolve_slides_llm_model,
    slides_brief_requires_research,
    slides_reasoning_extra_body,
    slides_search_budget_remaining,
)
from naas_abi_core.services.agent.context import (
    slides_active_slug,
    slides_research_queries,
    slides_research_required,
)


def test_weak_models_include_mini_and_free_gemma() -> None:
    assert is_weak_slides_model("gpt-4.1-mini")
    assert is_weak_slides_model("openai/gpt-4.1-mini")
    assert is_weak_slides_model("google/gemma-4-26b-a4b-it:free")
    assert is_weak_slides_model("")
    assert not is_weak_slides_model("gpt-5")
    assert not is_weak_slides_model("openai/gpt-5")
    assert not is_weak_slides_model("gpt-5.2")
    assert not is_weak_slides_model("claude-sonnet-5")
    assert not is_weak_slides_model("anthropic/claude-sonnet-5")


def test_default_slides_model_is_claude_sonnet_5() -> None:
    assert DEFAULT_SLIDES_MODEL == "anthropic/claude-sonnet-5"


def test_openrouter_slides_model_id_keeps_anthropic_prefix() -> None:
    assert openrouter_slides_model_id("anthropic/claude-sonnet-5") == (
        "anthropic/claude-sonnet-5"
    )
    assert openrouter_slides_model_id("claude-sonnet-5") == "anthropic/claude-sonnet-5"
    assert openrouter_slides_model_id("gpt-5") == "openai/gpt-5"
    assert openrouter_slides_model_id("openai/gpt-5") == "openai/gpt-5"


def test_slides_reasoning_extra_body_for_sonnet_and_gpt5() -> None:
    assert slides_reasoning_extra_body("anthropic/claude-sonnet-5") == {
        "reasoning": {"effort": "high"}
    }
    assert slides_reasoning_extra_body("openai/gpt-5") == {
        "reasoning": {"effort": "high"}
    }
    assert slides_reasoning_extra_body("gpt-4.1-mini") is None


def test_resolve_slides_llm_model_upgrades_mini() -> None:
    assert resolve_slides_llm_model("gpt-4.1-mini", slides_default="gpt-5") == "gpt-5"
    assert (
        resolve_slides_llm_model("google/gemma-4-26b-a4b-it:free", slides_default="gpt-5")
        == "gpt-5"
    )
    assert resolve_slides_llm_model("gpt-5.2", slides_default="gpt-5") == "gpt-5.2"
    assert resolve_slides_llm_model(None, slides_default="gpt-5") == "gpt-5"
    assert resolve_slides_llm_model(None, slides_default=None) == DEFAULT_SLIDES_MODEL


def test_apply_slides_model_override_when_deck_open() -> None:
    assert apply_slides_model_override("gpt-4.1-mini", None, None) == "gpt-4.1-mini"
    assert (
        apply_slides_model_override("gpt-4.1-mini", {"slides": {}}, None) == "gpt-4.1-mini"
    )
    assert (
        apply_slides_model_override(
            "gpt-4.1-mini",
            {"slides": {"slug": "iran-now"}},
            None,
        )
        == DEFAULT_SLIDES_MODEL
    )
    assert (
        apply_slides_model_override(
            "gpt-5.2",
            {"slides": {"slug": "iran-now"}},
            None,
        )
        == "gpt-5.2"
    )


def test_first_create_brief_requires_research() -> None:
    assert slides_brief_requires_research(
        "create a presentation about what's going on in iran now",
        has_prior_assistant=False,
    )
    assert slides_brief_requires_research(
        "Iran situation briefing",
        has_prior_assistant=False,
    )


def test_copy_edit_does_not_require_research() -> None:
    assert not slides_brief_requires_research(
        "change the title to Q3 Review",
        has_prior_assistant=True,
    )
    assert not slides_brief_requires_research(
        "fix typo on slide 2",
        has_prior_assistant=False,
    )


def test_followup_news_brief_still_requires_research() -> None:
    assert slides_brief_requires_research(
        "add the latest news from today",
        has_prior_assistant=True,
    )


def test_followup_write_now_does_not_require_another_search() -> None:
    assert not slides_brief_requires_research(
        "Insert the drafted copy into the open file. Do not search.",
        has_prior_assistant=True,
    )


def test_write_gate_blocks_until_web_search() -> None:
    slides_research_required.set(True)
    slides_research_queries.set([])
    blocked = reject_unresearched_slides_write()
    assert blocked is not None
    assert "web_search" in blocked["error"]

    note_slides_web_search("Iran latest developments 2026")
    assert reject_unresearched_slides_write() is None
    slides_research_required.set(False)
    slides_research_queries.set(None)


def test_bind_policy_sets_gate_for_open_deck() -> None:
    required = bind_slides_research_policy(
        "create a presentation about what's going on in iran now",
        has_prior_assistant=False,
        client_context={"slides": {"slug": "iran-now"}},
    )
    assert required is True
    assert slides_research_required.get() is True
    assert slides_research_queries.get() == []
    assert slides_active_slug.get() == "iran-now"
    slides_research_required.set(False)
    slides_research_queries.set(None)
    slides_active_slug.set(None)


def test_search_budget_stops_after_four_queries() -> None:
    slides_research_required.set(True)
    slides_research_queries.set([])

    class _Tool:
        def __init__(self) -> None:
            self.calls = 0

        def func(self, query: str, max_results: int = 8) -> str:
            self.calls += 1
            return f"ok:{query}"

    wrapped = attach_slides_research_note(_Tool())
    for i in range(MAX_SLIDES_SEARCHES):
        assert wrapped.func(f"q{i}").startswith("ok:")
    blocked = wrapped.func("one more")
    assert "Search budget reached" in blocked
    assert slides_search_budget_remaining() == 0
    slides_research_required.set(False)
    slides_research_queries.set(None)


def test_slides_creation_requested_detects_a_deck_brief_in_main_chat() -> None:
    from naas_abi.agents.slides_policy import slides_creation_requested

    assert slides_creation_requested("create a deck about the latest news about AI")
    assert slides_creation_requested("Make me a presentation on Q3 revenue")
    assert slides_creation_requested("build slides on the Iran situation")
    # Not a deck request.
    assert not slides_creation_requested("what is the capital of France?")
    assert not slides_creation_requested("summarise this document")
    assert not slides_creation_requested("")


def test_slides_creation_requested_detects_a_french_deck_brief() -> None:
    """A French brief must arm the slides path, not fall through to plain chat."""
    from naas_abi.agents.slides_policy import slides_creation_requested

    assert slides_creation_requested(
        "fais des slides sur les matériaux de construction"
    )
    assert slides_creation_requested("crée une présentation sur Saint-Gobain")
    assert slides_creation_requested("prépare un diaporama sur l'hydrogène vert")
    # Not a deck request.
    assert not slides_creation_requested("quelle est la capitale de la France ?")
    assert not slides_creation_requested("résume ce document")


def test_research_policy_records_the_brief_for_naming() -> None:
    """The deck name comes from the brief, so the turn has to keep it."""
    from naas_abi_core.services.agent.context import slides_brief

    token = slides_brief.set(None)
    try:
        bind_slides_research_policy(
            "fais des slides sur les matériaux de construction",
            False,
            None,
        )
        assert slides_brief.get() == "fais des slides sur les matériaux de construction"
    finally:
        slides_brief.reset(token)


def test_research_policy_arms_from_main_chat_without_an_open_deck() -> None:
    """Capability A: a news deck asked for in the main chat still researches."""
    from naas_abi_core.services.agent.context import (
        slides_creation_intent,
        slides_research_required,
    )

    tokens = (
        slides_research_required.set(False),
        slides_creation_intent.set(False),
    )
    try:
        required = bind_slides_research_policy(
            "create a deck about the latest news about AI",
            False,
            None,
        )
        assert required is True
        assert slides_research_required.get() is True
        assert slides_creation_intent.get() is True
    finally:
        slides_research_required.reset(tokens[0])
        slides_creation_intent.reset(tokens[1])


def test_research_policy_stays_off_for_ordinary_main_chat() -> None:
    from naas_abi_core.services.agent.context import (
        slides_creation_intent,
        slides_research_required,
    )

    tokens = (
        slides_research_required.set(False),
        slides_creation_intent.set(False),
    )
    try:
        assert bind_slides_research_policy("what is 2 + 2?", False, None) is False
        assert slides_research_required.get() is False
        assert slides_creation_intent.get() is False
    finally:
        slides_research_required.reset(tokens[0])
        slides_creation_intent.reset(tokens[1])


def test_model_override_upgrades_a_deck_request_from_main_chat() -> None:
    """A weak model invents filler instead of calling tools. Upgrade it even
    when no deck is open, otherwise chat-created decks are template junk.
    """
    # No deck open and no deck asked for: leave the user's choice alone.
    assert (
        apply_slides_model_override("gpt-4.1-mini", None, "what is 2 + 2?")
        == "gpt-4.1-mini"
    )
    # No deck open, but the user asked for one.
    assert (
        apply_slides_model_override(
            "gpt-4.1-mini",
            None,
            "create a deck about the latest news about AI",
        )
        == DEFAULT_SLIDES_MODEL
    )
