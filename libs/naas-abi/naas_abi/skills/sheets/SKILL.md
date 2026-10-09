---
name: Sheets
description: Spreadsheet work in Nexus Sheets. Hand workbooks to SheetsAgent instead of building a spreadsheet file yourself.
when_to_use: The user wants a spreadsheet, workbook, budget, schedule, or calculated table.
---

# Sheets

Nexus Sheets is the workbook. SheetsAgent edits it.

Do not assemble a spreadsheet with a library, and do not invent a second grid format. When no workbook is open, call create_sheets_project. Change cells with update_sheets_cells. Use write_sheets_workbook only when the tab structure itself should change. After formula edits, call evaluate_sheets_formulas and fix breakages before you claim the sheet is done.

The workbook contract already lives in the module skill nexus-sheets at agents/sheets/skills/nexus-sheets/SKILL.md. Leave that package where it is.

For figures that depend on the outside world, call web_search first and keep the source URL on the sheet.

Hand the workbook to SheetsAgent and call read_sheets_skill before changing a cell.
