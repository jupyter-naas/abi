import inspect

from naas_abi.agents import SlidesAgent as slides_agent_module
from naas_abi.agents.slides_policy import DEFAULT_SLIDES_MODEL, SLIDES_GUIDELINES
from naas_abi.agents.SlidesAgent import SlidesAgent


def test_slides_agent_is_first_class() -> None:
    assert SlidesAgent.__name__ == "SlidesAgent"
    assert SlidesAgent.name == "Slides"
    assert SlidesAgent.recursion_limit == 80
    assert "model_id" in inspect.signature(SlidesAgent.New).parameters
    assert hasattr(SlidesAgent, "get_tools")
    assert hasattr(SlidesAgent, "get_chat_model_id")


def test_slides_agent_prompt_requires_research_then_write() -> None:
    prompt = SlidesAgent.system_prompt
    assert "web_search" in prompt
    assert "Research loop" in prompt
    assert "start writing immediately" not in prompt
    assert "Context / Approach / Plan" in prompt
    assert "deck.html" in prompt
    assert SLIDES_GUIDELINES in prompt
    assert "[SKILL]" in prompt


def test_slides_agent_default_model_is_sonnet_5() -> None:
    assert SlidesAgent.get_chat_model_id() == DEFAULT_SLIDES_MODEL
    assert SlidesAgent.get_chat_model_ids() == [DEFAULT_SLIDES_MODEL]


def test_slides_agent_tool_names_are_slides_and_web() -> None:
    source = inspect.getsource(SlidesAgent.get_tools)
    assert "slides_tools" in source
    assert "naas_abi.agents.tools.web_tools" in source
    assert "make_web_search_tool" in source
    assert "make_web_fetch_tool" in source
    assert "office_skill_tools" in source
    assert "zen.tools" not in source
    assert "nexus_admin_tools" not in source
    assert "find_coding_agents" not in source


def test_slides_agent_has_no_module_create_agent() -> None:
    """ModuleAgentLoader binds create_agent over New. That pair recurses on boot."""
    assert not hasattr(slides_agent_module, "create_agent")
