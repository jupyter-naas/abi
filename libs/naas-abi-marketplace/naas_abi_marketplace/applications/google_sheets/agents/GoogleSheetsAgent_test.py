import pytest
from naas_abi_marketplace.applications.google_sheets.agents.GoogleSheetsAgent import (
    create_agent,
)


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Google Sheets" in result or "Sheets" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert (
        "spreadsheet" in result.lower()
        or "sheets" in result.lower()
        or "data" in result.lower()
    ), result
