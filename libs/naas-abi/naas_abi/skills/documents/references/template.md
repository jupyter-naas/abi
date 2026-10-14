# Document template

Nexus Documents fills the open template. DocumentsAgent does not author a Word file.

Read the document before editing. `read_document` returns `template_fields` with the real field names. Fill them once with `fill_document_slots`: title, subtitle, intro, sections (`heading`, `body`, optional `bullets`), quote, and tables (`heading`, `headers`, `rows`). Extra business fields go in `fields`.

Preserve `document.html` styles, logos, headers, and footers. Do not append after the footer. A later copy change uses `apply_document_commands` with the exact visible passage. If the brief needs current facts, call `web_search` and cite those sources. Report missing client names, fees, dates, and citations instead of inventing them.
