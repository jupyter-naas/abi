import inspect
from types import SimpleNamespace

from naas_abi.agents import DocumentsAgent as sections_agent_module
from naas_abi.agents.AbiAgent import AbiAgent
from naas_abi.agents.documents import DEFAULT_DOCUMENTS_MODEL
from naas_abi.agents.DocumentsAgent import DOCUMENTS_GUIDELINES, DocumentsAgent


def test_sections_agent_is_first_class() -> None:
    assert DocumentsAgent.__name__ == "DocumentsAgent"
    assert DocumentsAgent.name == "Documents"
    assert DocumentsAgent.recursion_limit == 160
    assert "model_id" in inspect.signature(DocumentsAgent.New).parameters
    assert hasattr(DocumentsAgent, "get_tools")
    assert hasattr(DocumentsAgent, "get_chat_model_id")


def test_sections_agent_prompt_requires_research_then_write() -> None:
    prompt = DocumentsAgent.system_prompt
    assert "web_search" in prompt
    assert "Research loop" in prompt
    assert "Plan, then write" in prompt
    assert "write_document_sections" in prompt
    assert "Do not re-read" in prompt
    assert "start writing immediately" not in prompt
    assert "Context / Approach / Plan" in prompt
    assert "document.html" in prompt
    assert DOCUMENTS_GUIDELINES in prompt


def test_sections_agent_prompt_covers_creating_a_document_from_the_main_chat() -> None:
    prompt = DocumentsAgent.system_prompt
    assert "create_documents_project" in prompt
    assert "no document is open" in prompt.lower()


def test_sections_agent_prompt_names_the_document_after_its_topic() -> None:
    prompt = DocumentsAgent.system_prompt
    lowered = prompt.lower()
    assert "same language as the brief" in lowered
    assert "untitled" in lowered
    assert "cover" in lowered


def test_sections_agent_default_model_is_the_policy_fallback() -> None:
    assert DocumentsAgent.get_chat_model_id() == DEFAULT_DOCUMENTS_MODEL
    assert DocumentsAgent.get_chat_model_ids() == [DEFAULT_DOCUMENTS_MODEL]


def test_sections_agent_owns_the_write_and_research_tools() -> None:
    names = {tool.name for tool in DocumentsAgent.get_tools()}
    assert "create_documents_project" in names
    assert "write_document" in names
    assert "write_document_section" in names
    assert "write_document_sections" in names
    assert "replace_in_document" in names
    assert "web_search" in names
    assert "web_fetch" in names
    source = inspect.getsource(DocumentsAgent.get_tools)
    assert "naas_abi.agents.tools.web_tools" in source or "documents_research_tools" in source
    assert "nexus_admin_tools" not in source


def test_sections_agent_has_no_module_create_agent() -> None:
    """ModuleAgentLoader binds create_agent over New. That pair recurses on boot."""
    assert not hasattr(sections_agent_module, "create_agent")


def test_new_loads_the_sections_model_and_keeps_write_tools(monkeypatch) -> None:
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, BaseMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    class _DummyChatModel(BaseChatModel):
        @property
        def _llm_type(self) -> str:
            return "dummy-sections-model"

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
        "naas_abi.agents.DocumentsAgent.load_documents_chat_model",
        lambda model_id: dummy,
    )
    monkeypatch.setattr(
        "naas_abi.agents.DocumentsAgent.resolve_documents_llm_model",
        lambda incoming, sections_default=None: "anthropic/claude-sonnet-5",
    )
    monkeypatch.setattr(
        "naas_abi.agents.DocumentsAgent.bind_documents_reasoning",
        lambda chat_model, model_id, force=False: chat_model,
    )

    agent = DocumentsAgent.New(model_id="gpt-4.1-mini")
    names = {tool.name for tool in agent.tools}

    assert isinstance(agent, DocumentsAgent)
    assert agent.name == "Documents"
    assert "create_documents_project" in names
    assert "web_search" in names


def test_abi_get_intents_include_sections_handoff() -> None:
    """A document brief on Abi must resolve to Documents, not to Abi's own write tools."""
    sections = SimpleNamespace(
        name=DocumentsAgent.name,
        description=DocumentsAgent.description,
        intents=DocumentsAgent.handoff_intents(),
    )
    intents = AbiAgent.get_intents(agents=[sections])
    sections_intents = [intent for intent in intents if intent.intent_target == "Documents"]
    values = " ".join(intent.intent_value.lower() for intent in sections_intents)

    assert sections_intents
    assert "create a document" in values
    assert "fais un rapport" in values
    assert DocumentsAgent.description in {intent.intent_value for intent in sections_intents}
