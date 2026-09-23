import inspect
from types import SimpleNamespace

from naas_abi.agents import SlidesAgent as slides_agent_module
from naas_abi.agents.AbiAgent import AbiAgent
from naas_abi.agents.slides import DEFAULT_SLIDES_MODEL
from naas_abi.agents.SlidesAgent import (
    SLIDES_ALLOWED_TOOLS,
    SLIDES_PROCEDURE,
    SlidesAgent,
)

_RAW_HTML_WRITERS = {
    "write_slides_section",
    "write_slides_sections",
    "write_slides_deck",
}


def test_slides_agent_is_first_class() -> None:
    assert SlidesAgent.__name__ == "SlidesAgent"
    assert SlidesAgent.name == "Slides"
    assert SlidesAgent.recursion_limit == 160
    assert "model_id" in inspect.signature(SlidesAgent.New).parameters
    assert hasattr(SlidesAgent, "get_tools")
    assert hasattr(SlidesAgent, "get_chat_model_id")


def test_slides_agent_prompt_is_the_procedure() -> None:
    """One procedure, in the prompt. No second copy of the steps anywhere."""
    prompt = SlidesAgent.system_prompt
    assert SLIDES_PROCEDURE in prompt
    assert "web_search" in prompt
    assert "build_slides_deck" in prompt
    assert "deck.html" in prompt
    assert "Context / Approach / Plan" in prompt
    assert "Do not re-read" in prompt
    # The old duplicates are gone.
    assert "<tasks>" not in prompt
    assert "Research loop" not in prompt
    for name in _RAW_HTML_WRITERS:
        assert name not in prompt


def test_slides_procedure_names_success_for_every_step() -> None:
    """Each step says what in the tool result proves it is done."""
    assert SLIDES_PROCEDURE.count("Success") >= 3
    assert "section_count" in SLIDES_PROCEDURE
    assert "cover_h1_updated" in SLIDES_PROCEDURE
    assert "replacements" in SLIDES_PROCEDURE


def test_slides_procedure_only_names_allowed_tools() -> None:
    """Every deck tool the procedure mentions is one the model is given."""
    assert set(SLIDES_ALLOWED_TOOLS) == {
        "create_slides_project",
        "build_slides_deck",
        "replace_in_slides_deck",
        "insert_slide",
        "delete_slide",
        "duplicate_slide",
        "reorder_slides",
        "slides_history",
    }
    assert not _RAW_HTML_WRITERS & set(SLIDES_ALLOWED_TOOLS)
    for name in SLIDES_ALLOWED_TOOLS:
        if name != "slides_history":
            assert f"`{name}`" in SLIDES_PROCEDURE, name


def test_slides_agent_prompt_covers_creating_a_deck_from_the_main_chat() -> None:
    prompt = SlidesAgent.system_prompt
    assert "create_slides_project" in prompt
    assert "no deck is open" in prompt.lower()


def test_slides_agent_prompt_names_the_deck_after_its_topic() -> None:
    procedure = SLIDES_PROCEDURE.lower()
    assert "user's language" in procedure
    assert "untitled" in procedure
    assert "cover" in procedure


def test_slides_agent_default_model_is_the_policy_fallback() -> None:
    assert SlidesAgent.get_chat_model_id() == DEFAULT_SLIDES_MODEL
    assert SlidesAgent.get_chat_model_ids() == [DEFAULT_SLIDES_MODEL]


def test_slides_agent_binds_exactly_the_allowed_tools_plus_search() -> None:
    """The model sees SLIDES_ALLOWED_TOOLS and web_search. Nothing that takes HTML."""
    names = {tool.name for tool in SlidesAgent.get_tools()}
    assert set(SLIDES_ALLOWED_TOOLS) <= names
    assert "web_search" in names
    # Escape hatches: raw HTML in, or a page the model then rewrites as HTML.
    assert not _RAW_HTML_WRITERS & names
    assert "web_fetch" not in names
    assert "read_slides_deck" not in names
    assert "list_slides_sections" not in names
    source = inspect.getsource(SlidesAgent.get_tools)
    assert "slides_research_tools" in source
    assert "nexus_admin_tools" not in source


def test_slides_agent_has_no_module_create_agent() -> None:
    """ModuleAgentLoader binds create_agent over New. That pair recurses on boot."""
    assert not hasattr(slides_agent_module, "create_agent")


def test_new_loads_the_slides_model_and_keeps_write_tools(monkeypatch) -> None:
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, BaseMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    class _DummyChatModel(BaseChatModel):
        @property
        def _llm_type(self) -> str:
            return "dummy-slides-model"

        @property
        def _identifying_params(self) -> dict:
            return {}

        def _generate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager=None,
            **kwargs,
        ) -> ChatResult:
            del messages, stop, run_manager, kwargs
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])

    dummy = _DummyChatModel()
    monkeypatch.setattr(
        "naas_abi.agents.SlidesAgent.load_slides_chat_model",
        lambda model_id: dummy,
    )
    monkeypatch.setattr(
        "naas_abi.agents.SlidesAgent.resolve_slides_llm_model",
        lambda incoming, slides_default=None: "anthropic/claude-sonnet-5",
    )
    monkeypatch.setattr(
        "naas_abi.agents.SlidesAgent.bind_slides_reasoning",
        lambda chat_model, model_id, force=False: chat_model,
    )

    agent = SlidesAgent.New(model_id="gpt-4.1-mini")
    names = {tool.name for tool in agent.tools}

    assert isinstance(agent, SlidesAgent)
    assert agent.name == "Slides"
    assert "create_slides_project" in names
    assert "web_search" in names


def test_abi_get_intents_include_slides_handoff() -> None:
    """A deck brief on Abi must resolve to Slides, not to Abi's own write tools."""
    slides = SimpleNamespace(
        name=SlidesAgent.name,
        description=SlidesAgent.description,
        intents=SlidesAgent.handoff_intents(),
    )
    intents = AbiAgent.get_intents(agents=[slides])
    slides_intents = [intent for intent in intents if intent.intent_target == "Slides"]
    values = " ".join(intent.intent_value.lower() for intent in slides_intents)

    assert slides_intents
    assert "create a presentation" in values
    assert "fais des slides" in values
    assert SlidesAgent.description in {intent.intent_value for intent in slides_intents}
