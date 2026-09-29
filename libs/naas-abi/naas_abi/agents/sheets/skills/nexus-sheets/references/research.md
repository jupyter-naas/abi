# Spreadsheet research, 2026-09-22

- Univer core UI: https://docs.univer.ai/guides/sheets/features/core
  Spreadsheet interaction includes a formula bar, visible grid headers,
  selection, scrolling, and a sheet bar. Nexus now renders these controls from
  its existing JSON model instead of scaling a presentation preview. A full
  office SDK would require a separate model migration and licensing review;
  it is not installed by this change.
- SheetJS formula representation: https://docs.sheetjs.com/docs/csf/features/formulae/
  Formula expressions and cached results are distinct. Nexus retains formulas
  in stored JSON and XLSX, calculating a separate display model. SheetJS is not
  used as a calculation engine.
- Anthropic spreadsheet skill: https://github.com/anthropics/skills/blob/main/skills/xlsx/SKILL.md
  Reference for formula-preserving edits and checking derived workbooks.
  This skill is an original Nexus-specific implementation; upstream scripts
  and templates have not been copied or installed.
- openpyxl formulas: https://openpyxl.readthedocs.io/en/stable/simple_formulae.html
  openpyxl writes formulas but does not evaluate them. Existing Nexus export
  uses openpyxl; the Python formula engine validates the supported subset.

Reusable scripts: the validation helper beside this skill, the existing Nexus
XLSX export CLI, and the new targeted A1 edit helper. Reuse these rather than
regenerating full workbooks for a few input changes.

Templates: retain the local blank grid, monthly P&L, budget versus actuals,
and cash runway templates, including their Assumptions and Checks tabs. These
already fit the application's schema and formula engine. Template examples
must remain distinguishable from researched or user-supplied financial data.

Remaining advanced capabilities require additional work: rich cell formats,
row insertion with formula reference rewriting, sort/filter,
XLSX import, charts, pivots, and simultaneous-user conflict resolution.
