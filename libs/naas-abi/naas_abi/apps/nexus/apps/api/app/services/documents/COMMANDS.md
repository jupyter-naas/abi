# Documents commands

Nexus Documents stores git-backed HTML (`document.html`). The command
surface is the contract. The file format is an implementation detail.

This note is the verb set. It is inspired by Google Docs
`documents.batchUpdate`, OASIS OpenDocument text operations, and the
Pandoc AST. It is not an ODF writer and not a Google Docs clone.

## Architecture

HTTP is the public contract. Named verbs (`rename_document`,
`insert_heading`, `apply_template`, …) are the product surface. The
agent calls those same names. A future `abi documents <verb>` would
wrap the same HTTP routes. That is API first, with CLI-shaped verbs
on top. It is not a CLI that owns the logic.

`POST /api/documents/projects/{slug}/commands` applies an ordered
list of verbs (Google Docs `batchUpdate` style). That is not a shell
CLI. There is no `abi documents rename` today. The `abi` Click CLI
is workspace, user, stack, and dev. Do not invent a Documents Click
group until a wrapper is a product need, and do not put business
logic in the agent.

What actually runs:

1. Verb functions live in `documents_commands.py` (HTML).
   `rename_document` also writes `project.json` `title`.
2. FastAPI `POST /commands` calls those verbs and writes the
   git-backed store (sidecar plus Forgejo).
3. Agent tools use the same names and the same Python mutators. They
   talk to sidecar and git directly. They are not HTTP clients of
   the API.
4. The web UI calls the HTTP API (PATCH for a sidebar-typed rename,
   `POST /commands` for outline edits).

Target: one named command per user-facing function, callable from
HTTP and from the agent. A later CLI is a thin wrapper of the API.

## Supported commands

`POST /api/documents/projects/{slug}/commands` applies an ordered list.
The first error aborts the batch (same idea as Docs `batchUpdate`).

| Command | What it does | Source |
|---|---|---|
| `insert_text` | Insert text as a paragraph after a heading | Docs `insertText`; ODF `addParagraph` / `insert` |
| `insert_paragraph` | Insert a `<p>` after a heading | Pandoc `Para`; ODF paragraph |
| `insert_heading` | Insert `h1`/`h2`/`h3` after a heading | Pandoc `Header`; Docs `updateParagraphStyle` HEADING_* |
| `insert_page_break` | Insert a hard page break (same section) | Docs `insertPageBreak`; ODF `fo:break-before=page`; Word `w:br w:type="page"`; Pandoc pagebreak |
| `delete_range` | Delete a heading block (that heading through the next) | Docs `deleteContentRange` |
| `replace_text` | Replace a substring | Docs `replaceAllText` |
| `replace_class` | Replace or delete the first element with that class | fill a seed slot (palette, note) |
| `update_paragraph_style` | Retag a heading (`heading1`/`heading2`/`heading3`/`paragraph`) | Docs `updateParagraphStyle` |
| `update_title` | Change the tab `<title>` and cover H1 only | heading-only retitle |
| `rename_document` | Sidebar display name plus tab `<title>`, cover H1, and footer titles | "rename this document" |

Positioning is a heading index (`after_heading` / `heading_index`), not a
UTF-16 offset. That matches ODF "insert relative to a paragraph" more
than Docs character indexes.

Inserts land inside the `.doc-body` that owns the heading. They never
concatenate markup after `</footer>`. A persist pass moves stray nodes
that already landed after a footer back into that page's `.doc-body`.

## Fill the open template

When the user asks for a memo or report on an untitled seed:

1. `rename_document` from the brief.
2. Adapt every seed slot. Do not append a new article after the seed.
   - Cover H1, kicker or subtitle, intro paragraphs
   - Official heading styles
   - Tables: replace headers and rows with topic data (no
     "Assumption / Replace with the working premise")
   - Quotes, lists, discussion blocks
   - Colour swatches stay only as brand specimens. For a memo, replace
     the palette (`replace_class` on `palette`) with a real table or
     delete it
3. Writes go into `.doc-body` via `apply_document_commands` /
   `replace_text` / `replace_class` / heading plus paragraph. Never
   concatenate HTML after `</footer>`.
4. If `leftover_placeholders` is not empty, replace those slots. Do
   not stop while instructional seed copy remains.

Fill the open template. Do not leave seed placeholder copy. Do not
append after the footer.

## Rename vs heading

"Rename this document" (or "rename this doc") is one product action:
`rename_document`. It updates the project display name the sidebar tree
reads (`project.json` `title`) and the visible document title (tab and
cover H1). The slug and git folder stay put. `Untitled document` is that
display name, not only the slug.

"Change the title" or "change the heading" is heading-only: `update_title`.
It does not rename the sidebar folder.

Agent tools use the same names. Internal helpers can still split
project write vs HTML write; the command the agent and the user see
must not.

Read and project verbs already exist:

| Route / tool | What it does | Source |
|---|---|---|
| `GET /projects`, `list_documents_projects` | List documents | Docs `documents.list` analog |
| `POST /projects`, `create_documents_project` | Create from a seed | Docs `documents.create` |
| `GET /projects/{slug}/document`, `read_document` | Read stored HTML (tools return an outline by default) | Docs `documents.get` |
| `PUT /projects/{slug}/document`, `write_document` | Replace the whole document | full-document write |
| `GET /projects/{slug}/outline` | Heading outline | Pandoc `Header` walk |
| `GET /projects/{slug}/history` | Git history | versioning, not a Docs API |
| File print / HTML export | Print and download | Docs export / Pandoc convert |

Agent tools with the same names call the same mutators:
`insert_page_break`, `insert_heading`, `insert_paragraph`,
`apply_paragraph_style`, `apply_document_commands`, `rename_document`,
`update_title`.

## Leftover section API

These are slide-shaped leftovers. They still work on `<section class="page">`
blocks. Do not use them as the model for new prose features.

- `GET /projects/{slug}/sections`
- `POST .../sections/insert` (`cover` / `section-divider` / `content`)
- `POST .../sections/delete`
- `POST .../sections/duplicate`
- `POST .../sections/reorder`
- Agent tools `insert_section`, `delete_section`, `duplicate_section`,
  `reorder_sections`, `write_document_section(s)`

An ODF `text:section` is a named region (columns, notes). It is not a
slide and not a page. Docs `insertSectionBreak` changes headers, footers,
and margins. Neither is "new slide".

## Explicit non-goals

- Full ODF / OOXML writer or reader
- Docs UTF-16 indexes, suggestions, comments, tabs, named ranges
- Headers, footers, footnotes, tables, images, bullets as first-class
  commands (Pandoc and Docs have them; add later if a product need appears)
- Changing Slides

## Citations

- OASIS OpenDocument TC: https://www.oasis-open.org/committees/tc_home.php?wg_abbrev=office
- Google Docs requests: https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/request
- Pandoc AST (`Para`, `Header`, `Table`, `Image`): https://hackage.haskell.org/package/pandoc-types-1.23/docs/Text-Pandoc-Definition.html
- Word `w:p` / `w:br w:type="page"`: ECMA-376 / ISO/IEC 29500
