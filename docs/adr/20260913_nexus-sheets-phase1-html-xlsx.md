# Nexus Sheets workbook model and editor

- **Status:** Accepted; updated 2026-09-22
- **Date:** 2026-09-13
- **Context:** [Issue #1254](https://github.com/jupyter-naas/abi/issues/1254) asks for a usable Sheets application in Nexus, with the same project and chat integration as the other office surfaces.
- **Decision:** Keep the embedded `application/vnd.nexus.sheet+json` model in `workbook.html` as the persisted source of truth. Store projects through the configured source-control adapter under `sheets/<workspace>/<slug>/workbook.html`. Render a native virtualized grid with column letters, row numbers, a formula bar, and sheet tabs. Persist sparse pixel column widths and row heights with each sheet. Keep raw formula expressions in storage; calculate a separate display model through the authenticated preview endpoint. SheetsAgent uses the same model, formula engine, template catalog, and bounded cell-edit helpers. Export formulas and dimensions to XLSX using openpyxl.
- **Consequences:** Marketplace Sheets opens a usable editor. Cell edits, clipboard operations, tab mutations, resizing, undo/redo, and keyboard or mouse formula references use the existing autosave endpoint. The shared office shell remains responsible for project navigation and workbook chat context. The Python engine deliberately supports a limited function set; XLSX export is not a full Excel round trip. Rich formatting, reference rewriting during row insertion, sort/filter, XLSX import, charts, pivots, and concurrent-edit conflict resolution remain outside this change. An office SDK migration is not required for this editor.


## Merge hardening

Git content is authoritative. Sidecar files are best-effort mirrors and are no
longer used to choose the workbook returned to clients. GET/save responses carry
a SHA-256 `revision`; whole-workbook PUT and template replacement require
`expected_revision`. A stale save returns HTTP 409 before touching the mirror.
The editor preserves its draft and pauses autosave until an explicit refresh.
Older clients without a revision receive 422 and must reload/upgrade.

The source-control port provides atomic `compare_and_swap_file`: Forgejo uses
its conditional blob-SHA update, local Git uses a private index plus conditional
`update-ref`, and the in-memory adapter serializes conditional writes.
Unsupported adapters fail closed. Local Git tree writes also use private indexes
so metadata saves cannot revert workbook changes through a stale shared index.
References: [Git update-ref](https://git-scm.com/docs/git-update-ref/2.46.0).

All Sheets mutation routes require owner/admin/member membership. SheetsAgent
checks the same writer roles before persistence; full replacements require the
revision returned by its read tool. Bounded edits read the current workbook and
conditionally commit their transformation.

Calculation memoizes dependencies per request, caps reference depth at 64,
charges expression/range work against a shared budget, and limits workbook size.
Budget/dependency failures produce cell errors. ROUND uses decimal half-away-from-zero
ties, including negative digits, following [Excel ROUND](https://support.microsoft.com/en-us/excel/functions/round-function).
Numeric reference substitution preserves float round-trip precision.

Development output uses `.next-dev`; production builds retain `.next`, preventing
`make check` from replacing chunks underneath a running dev server. This uses
[Next.js distDir](https://nextjs.org/docs/14/app/api-reference/next-config-js/distDir).
