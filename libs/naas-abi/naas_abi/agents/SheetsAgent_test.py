
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


def test_sheets_agent_tools() -> None:
    names = {tool.name for tool in SheetsAgent.get_tools()}
    assert "create_sheets_project" in names
    assert "write_sheets_workbook" in names
    assert "update_sheets_cells" in names
    assert "evaluate_sheets_formulas" in names
    assert "import_dataset_to_sheet" in names
    assert "web_search" in names


def test_sheets_agent_has_no_module_create_agent() -> None:
    assert not hasattr(sheets_agent_module, "create_agent")
