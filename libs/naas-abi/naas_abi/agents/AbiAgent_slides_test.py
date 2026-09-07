import inspect

from naas_abi.agents.AbiAgent import AbiAgent
from naas_abi.agents.SlidesAgent import SlidesAgent


def test_abi_prompt_hands_deck_briefs_to_slides() -> None:
    prompt = AbiAgent.system_prompt
    lowered = prompt.lower()
    assert "hand off to the slides agent" in lowered
    assert "create_slides_project" not in prompt
    assert "<slides_guidelines>" not in prompt


def test_new_accepts_model_id() -> None:
    assert "model_id" in inspect.signature(AbiAgent.New).parameters


def test_abi_get_tools_does_not_register_slides_writes() -> None:
    source = inspect.getsource(AbiAgent.get_tools)
    assert "slides_tools" not in source
    assert "slides_research_tools" not in source


def test_create_slides_project_is_registered_on_slides_agent() -> None:
    names = {tool.name for tool in SlidesAgent.get_tools()}
    assert "create_slides_project" in names
