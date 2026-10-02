from naas_abi.agents.sheets.template_resolve import (
    DEFAULT_SHEETS_TEMPLATE_ID,
    qualify_sheets_template_id,
    resolve_sheets_template_id,
)


def test_resolve_finance_templates_from_brief() -> None:
    assert (
        resolve_sheets_template_id(title="Q3 P&L", brief="Build a monthly P&L")
        == "monthly-pnl-v1"
    )
    assert (
        resolve_sheets_template_id(
            title="Ops", brief="budget vs actuals for the quarter"
        )
        == "budget-vs-actuals-v1"
    )
    assert (
        resolve_sheets_template_id(title="Cash", brief="12-month cash runway")
        == "cash-runway-v1"
    )
    assert (
        resolve_sheets_template_id(title="Scratch", brief="empty workbook")
        == DEFAULT_SHEETS_TEMPLATE_ID
    )


def test_explicit_template_id_wins() -> None:
    assert (
        resolve_sheets_template_id(
            template_id="abi/cash-runway-v1",
            title="P&L please",
            brief="profit and loss",
        )
        == "cash-runway-v1"
    )
    assert qualify_sheets_template_id("monthly-pnl-v1") == "abi/monthly-pnl-v1"
