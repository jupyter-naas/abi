---
name: Documents
description: Reports and memos in Nexus Documents. Hand the writing to DocumentsAgent and fill the open template.
when_to_use: The user wants a document, report, memo, or written brief.
---

# Documents

Nexus Documents fills a template. DocumentsAgent writes it.

Hand the memo to DocumentsAgent and fill the open document template instead of emitting a Word file.

When none is open, call create_documents_project with a short title. Read the document before editing so you use its real template fields. Fill it with fill_document_slots. For a later copy change, use apply_document_commands with the exact visible passage. If the brief needs current facts, call web_search and cite those sources in the document. Do not invent client names, fees, dates, or citations. Say what is still missing instead of pretending the draft is finished.
