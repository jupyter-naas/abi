import inspect

from naas_abi.agents.AbiAgent import AbiAgent
from naas_abi.agents.DocumentsAgent import DocumentsAgent


def test_abi_prompt_hands_document_briefs_to_sections() -> None:
    prompt = AbiAgent.system_prompt
    lowered = prompt.lower()
    assert "hand off to the sections agent" in lowered
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
