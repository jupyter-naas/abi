import inspect

from naas_abi.agents.AbiAgent import AbiAgent


def test_slides_guidelines_require_research_before_write() -> None:
    prompt = AbiAgent.system_prompt
    assert "web_search" in prompt
    assert "Research loop" in prompt
    assert "start writing immediately" not in prompt
    assert "Context / Approach / Plan" in prompt


def test_new_accepts_model_id() -> None:
    assert "model_id" in inspect.signature(AbiAgent.New).parameters


def test_slides_guidelines_cover_creating_a_deck_from_the_main_chat() -> None:
    """Capability A: with no deck open, Abi must create one, not refuse."""
    prompt = AbiAgent.system_prompt
    assert "create_slides_project" in prompt
    # It must not stall asking the user to open Slides first.
    lowered = prompt.lower()
    assert "no deck is open" in lowered


def test_create_slides_project_is_registered_as_a_tool() -> None:
    from naas_abi.agents.tools.slides_tools import slides_tools

    assert "create_slides_project" in {t.name for t in slides_tools()}
