# Nexus Sheets phase 1 (HTML workbook + XLSX export)

- **Status:** Accepted
- **Date:** 2026-09-13
- **Context:** [Issue #1254](https://github.com/jupyter-naas/abi/issues/1254) asks to land Sheets in Nexus on the same integration path as Slides. R&D code is not yet in-tree; we need a shippable vertical slice.
- **Decision:** Treat the workbook as a single HTML file with an embedded `application/vnd.nexus.sheet+json` model (plus a rendered `table.sheet-grid` for editing). Store projects in Forgejo under `sheets/<workspace>/<slug>/workbook.html` mirroring Slides git layout. Export to XLSX via `openpyxl` in `naas_abi.apps.nexus.sheets` (CLI + `GET /api/sheets/projects/{slug}/export/xlsx`). Defer SheetsAgent, formula engine, and live connectors to later phases.
- **Consequences:** Marketplace Sheets tile is available and routes into Nexus. UI reuses the Slides office shell with workbook naming. Slide-mutation API routes copied from Slides remain unused until grid-native editing lands.
