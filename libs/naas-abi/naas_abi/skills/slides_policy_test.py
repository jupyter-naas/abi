from naas_abi.skills.slides_policy import (
    DEFAULT_SLIDES_MODEL,
    MAX_SLIDES_SEARCHES,
    apply_slides_model_override,
    attach_slides_research_note,
    bind_slides_research_policy,
    is_slides_agent_ref,
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


def test_is_slides_agent_ref() -> None:
    assert is_slides_agent_ref("naas_abi.agents.SlidesAgent/SlidesAgent")
    assert is_slides_agent_ref("SlidesAgent")
    assert is_slides_agent_ref("Slides")
    assert is_slides_agent_ref("naas_abi.agents.SlidesAgent/Slides")
    assert not is_slides_agent_ref("Abi")
    assert not is_slides_agent_ref("naas_abi.agents.AbiAgent/AbiAgent")
    assert not is_slides_agent_ref(None)


def test_apply_slides_model_override_only_when_deck_open() -> None:
    assert apply_slides_model_override("gpt-4.1-mini", None) == "gpt-4.1-mini"
    assert apply_slides_model_override("gpt-4.1-mini", {"slides": {}}) == "gpt-4.1-mini"
    assert (
        apply_slides_model_override(
            "gpt-4.1-mini",
            {"slides": {"slug": "iran-now"}},
        )
        == DEFAULT_SLIDES_MODEL
    )
    assert (
        apply_slides_model_override(
            "gpt-5.2",
            {"slides": {"slug": "iran-now"}},
        )
        == "gpt-5.2"
    )


def test_apply_slides_model_override_when_agent_is_slides() -> None:
    assert (
        apply_slides_model_override(
            "gpt-4.1-mini",
            None,
            "naas_abi.agents.SlidesAgent/SlidesAgent",
        )
        == DEFAULT_SLIDES_MODEL
    )
    assert (
        apply_slides_model_override("gpt-5.2", None, "SlidesAgent") == "gpt-5.2"
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
