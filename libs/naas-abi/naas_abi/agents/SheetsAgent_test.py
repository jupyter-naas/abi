
from naas_abi.agents import SheetsAgent as sheets_agent_module
from naas_abi.agents.sheets import DEFAULT_SHEETS_MODEL
from naas_abi.agents.SheetsAgent import (
    SHEETS_GUIDELINES,
    SHEETS_OUTPUT_QUALITY,
    SheetsAgent,
)
from naas_abi_core.services.agent.context import SHEETS_RECURSION_LIMIT


def test_sheets_agent_is_first_class() -> None:
    assert SheetsAgent.__name__ == "SheetsAgent"
    assert SheetsAgent.name == "Sheets"
    assert SheetsAgent.recursion_limit == SHEETS_RECURSION_LIMIT
    assert hasattr(SheetsAgent, "get_tools")


def test_sheets_agent_prompt_mentions_workbook_tools() -> None:
    prompt = SheetsAgent.system_prompt
    assert "create_sheets_project" in prompt
    assert "write_sheets_workbook" in prompt
    assert SHEETS_GUIDELINES in prompt
    assert SHEETS_OUTPUT_QUALITY in prompt
    assert "monthly-pnl-v1" in prompt
    assert "budget-vs-actuals-v1" in prompt
    assert "cash-runway-v1" in prompt
    assert "4-row sample grid" in prompt
    assert "Formulas over literals" in prompt


def test_sheets_agent_default_model() -> None:
    assert SheetsAgent.get_chat_model_id() == DEFAULT_SHEETS_MODEL


_SHEETS_BODY_SENTENCE = (
    "The workbook JSON inside `workbook.html` is authoritative."
)


def test_sheets_prompt_lists_the_skill_catalog_and_not_the_body() -> None:
    prompt = SheetsAgent.system_prompt
    assert "name: nexus-sheets" in prompt
    assert "Create, edit, and validate Nexus spreadsheet workbooks" in prompt
    assert "read_sheets_skill" in prompt
    assert _SHEETS_BODY_SENTENCE not in prompt
    from naas_abi.agents.sheets.skill_catalog import read_sheets_skill_body

    body = read_sheets_skill_body("nexus-sheets")
    assert _SHEETS_BODY_SENTENCE in body


def test_read_sheets_skill_tool_returns_the_full_body() -> None:
    tool = next(tool for tool in SheetsAgent.get_tools() if tool.name == "read_sheets_skill")
    result = tool.invoke({"name": "nexus-sheets"})
    assert _SHEETS_BODY_SENTENCE in result
    assert "name: nexus-sheets" in result


def test_sheets_agent_tools() -> None:
    names = {tool.name for tool in SheetsAgent.get_tools()}
    assert "read_sheets_skill" in names
    assert "create_sheets_project" in names
    assert "write_sheets_workbook" in names
    assert "update_sheets_cells" in names
    assert "evaluate_sheets_formulas" in names
    assert "import_dataset_to_sheet" in names
    assert "web_search" in names


def test_sheets_agent_has_no_module_create_agent() -> None:
    assert not hasattr(sheets_agent_module, "create_agent")


def test_workbook_tool_does_not_edit_before_read_sheets_skill(monkeypatch) -> None:
    from naas_abi.agents.sheets.skill_catalog import reset_sheets_skill_loaded
    from naas_abi.tools import sheets_workbook_storage as store

    reset_sheets_skill_loaded()

    def _refuse(*_args, **_kwargs):
        raise AssertionError("workbook edit ran without read_sheets_skill")

    monkeypatch.setattr(store, "persist_workbook", _refuse)
    monkeypatch.setattr(store, "load_workbook_text", _refuse)
    monkeypatch.setattr(store, "resolve_slug", _refuse)
    tool = next(item for item in SheetsAgent.get_tools() if item.name == "update_sheets_cells")
    result = tool.invoke(
        {"sheet_name": "Sheet1", "cells_json": '{"A1": 1}', "slug": "budget"}
    )

    assert "read_sheets_skill" in result["error"]
    assert "ok" not in result


def test_workbook_tool_reaches_storage_after_read_sheets_skill(monkeypatch) -> None:
    from naas_abi.agents.sheets.skill_catalog import reset_sheets_skill_loaded
    from naas_abi.tools import sheets_workbook_storage as store

    from naas_abi_core.services.agent.context import agent_user_id

    reset_sheets_skill_loaded()
    reader = next(item for item in SheetsAgent.get_tools() if item.name == "read_sheets_skill")
    assert "workbook.html" in reader.invoke({"name": "nexus-sheets"})
    monkeypatch.setattr(store, "resolve_slug", lambda _slug: {"error": "missing workbook"})
    tool = next(item for item in SheetsAgent.get_tools() if item.name == "update_sheets_cells")
    token = agent_user_id.set("user-1")
    try:
        result = tool.invoke(
            {"sheet_name": "Sheet1", "cells_json": '{"A1": 1}', "slug": "budget"}
        )
    finally:
        agent_user_id.reset(token)
    assert result == {"error": "missing workbook"}
