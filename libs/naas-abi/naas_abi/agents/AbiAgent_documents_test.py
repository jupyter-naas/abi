import inspect
from types import SimpleNamespace

from naas_abi.agents.AbiAgent import AbiAgent
from naas_abi.agents.DocumentsAgent import DocumentsAgent


def test_abi_registers_configured_documents_agent_routing() -> None:
    agent = SimpleNamespace(
        name=DocumentsAgent.name,
        description=DocumentsAgent.description,
        intents=[],
    )
    intents = AbiAgent.get_intents([agent])
    assert any(
        intent.intent_target == DocumentsAgent.name
        and intent.intent_value == f"Chat with {DocumentsAgent.name} Agent"
        for intent in intents
    )
    assert any(
        intent.intent_target == DocumentsAgent.name
        and intent.intent_value == DocumentsAgent.description
        for intent in intents
    )
    prompt = AbiAgent.system_prompt
    assert "create_documents_project" not in prompt
    assert "<sections_guidelines>" not in prompt


def test_new_accepts_model_id() -> None:
    assert "model_id" in inspect.signature(AbiAgent.New).parameters


def test_abi_get_tools_does_not_register_sections_writes() -> None:
    source = inspect.getsource(AbiAgent.get_tools)
    assert "documents_tools" not in source
    assert "documents_research_tools" not in source


def test_create_documents_project_is_registered_on_sections_agent() -> None:
    names = {tool.name for tool in DocumentsAgent.get_tools()}
    assert "create_documents_project" in names
