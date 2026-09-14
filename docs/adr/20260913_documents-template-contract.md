# Documents template content contract

Status: Accepted for the Documents branch
Date: 2026-09-13

## Context

The catalog, the main-chat creation tool, and slot filling did not share a contract. Blank templates lost body content, business fields were ignored, and a successful save could be mistaken for a finished document. Inline edits searched attributes and scripts as well as visible prose.

## Decision

HTML remains the persisted document. `data-slot` identifies editable text, list and table fields. Nested slots expose their leaf fields; headers, footers, scripts, styles and SVG are protected. Templates mark example values with `data-placeholder="true"`. Filling a named field acknowledges that example; unresolved fields and missing input remain explicit in results. The base content contract supports title, subtitle, intro, repeated sections and tables, and optional note/quote blocks. Template-specific values use a typed `fields` object discovered from the actual template. Unknown fields fail validation.

Source ranges come from Python's HTML parser so edits preserve assets and styles without reserializing the entire document. Ordinary replacement edits visible text and escapes replacement input. Inline formatting requires a unique visible match. The configured server template is used by both UI and main-chat creation.

`ok` means an operation was applied, while `content_complete` and `missing_slots` describe content readiness. Neither proves visual correctness. A failed mutation does not consume the successful-write allowance; existing turn limits still apply after successful writes.

## Consequences

Existing documents remain readable without new markers, with legacy placeholder detection as a fallback. New templates must expose their editable fields explicitly. There is no new library dependency. Research and final render verification remain separate responsibilities. CLI compatibility remains, but no additional CLI surface is introduced by this change.

## Paper geometry (2026-09-14)

Documents uses ISO A4 (210 x 297 mm), with template orientation selecting portrait or landscape. The editor and standalone HTML export use the same preparation function. Print changes only the canvas and page-break rules; paper dimensions, typography and margins remain identical to the preview. Preview scaling never exceeds 100%. Explicit break markers survive repeated pagination, and outline offsets include preceding pages. Legacy Letter templates render as A4 without rewriting their content.
