from naas_abi.tools.documents_commands import (
    FILL_SLOT_KEYS,
    PAGE_BREAK_HTML,
    apply_document_commands,
    heading_outline,
    insert_heading,
    insert_page_break,
    insert_paragraph,
    last_rename_document_title,
    leftover_placeholders,
    leftover_slots,
    leftover_write_note,
    normalize_document_flow,
    replace_class,
    replace_text,
    update_document_title,
    update_paragraph_style,
)

_SAMPLE = """<!doctype html><html><body>
<main class="document">
<section class="page cover" data-layout="cover">
<h1>Document Title</h1>
<p class="deck">Summary.</p>
<h2>Introduction</h2>
<p>State the situation.</p>
</section>
<section class="page content" data-layout="content">
<div class="page-break" data-nexus-page-break></div>
<h2>Discussion</h2>
<p>Develop the argument.</p>
</section>
</main></body></html>"""


def test_heading_outline_lists_prose_headings() -> None:
    items = heading_outline(_SAMPLE)
    assert [row["title"] for row in items] == [
        "Document Title",
        "Introduction",
        "Discussion",
    ]
    assert items[0]["tag"] == "h1"
    assert items[1]["tag"] == "h2"


def test_insert_page_break_after_introduction() -> None:
    html = insert_page_break(_SAMPLE, after_heading=1)
    assert html.count(PAGE_BREAK_HTML) == 2
    assert html.index("Introduction") < html.index(PAGE_BREAK_HTML)


def test_insert_heading_and_paragraph() -> None:
    html = insert_heading(_SAMPLE, title="Findings", level=2, after_heading=1)
    assert '<h2 class="fmz-heading-1">Findings</h2>' in html
    html = insert_paragraph(html, "A new sentence.", after_heading=2)
    assert '<p class="fmz-normal">A new sentence.</p>' in html


def test_batch_commands_page_break_then_heading() -> None:
    result = apply_document_commands(
        _SAMPLE,
        [
            {"type": "insert_page_break", "after_heading": 1},
            {
                "type": "insert_heading",
                "after_heading": 1,
                "title": "Annex",
                "level": 2,
            },
        ],
    )
    assert result["ok"] is True
    assert result["applied"] == ["insert_page_break", "insert_heading"]
    assert "Annex" in result["html"]
    assert PAGE_BREAK_HTML in result["html"]
    titles = [row["title"] for row in result["outline"]]
    assert "Annex" in titles


def test_replace_text_and_style() -> None:
    result = apply_document_commands(
        _SAMPLE,
        [
            {
                "type": "replace_text",
                "find": "Document Title",
                "replace": "Board update",
            },
            {"type": "update_paragraph_style", "heading_index": 1, "style": "heading3"},
        ],
    )
    assert result["ok"] is True
    assert "Board update" in result["html"]
    assert '<h4 class="fmz-heading-3">Introduction</h4>' in result["html"]


def test_update_paragraph_style_heading1_is_not_title() -> None:
    html = (
        '<h1 class="fmz-title" data-slot="title">Cover</h1>'
        '<h2 class="fmz-heading-1" data-slot="situation-heading">Situation</h2>'
    )
    titled = update_paragraph_style(html, 1, "title")
    assert isinstance(titled, str)
    assert 'data-slot="situation-heading"' in titled
    assert titled.count("<h1") == 2
    heading1 = update_paragraph_style(html, 1, "heading1")
    assert isinstance(heading1, str)
    assert (
        '<h2 class="fmz-heading-1" data-slot="situation-heading">Situation</h2>'
        in heading1
    )


def test_delete_range_refuses_last_heading() -> None:
    one = "<main class='document'><section class='page'><h1>Only</h1><p>x</p></section></main>"
    result = apply_document_commands(
        one, [{"type": "delete_range", "heading_index": 0}]
    )
    assert "error" in result


def test_unknown_command_is_rejected() -> None:
    result = apply_document_commands(_SAMPLE, [{"type": "insert_slide"}])
    assert "error" in result
    assert "insert_page_break" in result["error"]


def test_empty_requests_rejected() -> None:
    assert "error" in apply_document_commands(_SAMPLE, [])


def test_update_document_title_sets_tab_and_cover() -> None:
    html = (
        "<html><head><title>Document Title</title></head><body>"
        + _SAMPLE
        + "</body></html>"
    )
    updated = update_document_title(html, "Forvis Mazars Story")
    assert isinstance(updated, str)
    assert "<title>Forvis Mazars Story</title>" in updated
    assert "<h1>Forvis Mazars Story</h1>" in updated
    assert "<h2>Introduction</h2>" in updated


def test_rename_document_command_updates_html_title() -> None:
    result = apply_document_commands(
        _SAMPLE,
        [{"type": "rename_document", "title": "Forvis Mazars Story"}],
    )
    assert result["ok"] is True
    assert "<h1>Forvis Mazars Story</h1>" in result["html"]
    assert result["applied"] == ["rename_document"]


def test_update_title_command_is_heading_only_html() -> None:
    result = apply_document_commands(
        _SAMPLE,
        [{"type": "update_title", "title": "Cover only"}],
    )
    assert result["ok"] is True
    assert "<h1>Cover only</h1>" in result["html"]
    assert (
        last_rename_document_title([{"type": "update_title", "title": "Cover only"}])
        == ""
    )


_SEEDED_PAGE = """<!doctype html><html><head><title>Document title</title></head><body>
<main class="document">
<section class="page tables" data-layout="tables">
  <div class="doc-body">
    <h1>Document title</h1>
    <h2>Findings</h2>
    <h3>Shaded</h3>
    <table class="fmz-shaded">
      <tr><td>Assumption</td><td>Replace with the working premise.</td></tr>
    </table>
  </div>
  <footer class="doc-footer">
    <span class="doc-footer-title">Document title, industry or service line</span>
  </footer>
</section>
</main></body></html>"""


def test_insert_after_last_heading_stays_inside_doc_body() -> None:
    html = insert_heading(_SEEDED_PAGE, title="Synthese", level=1, after_heading=-1)
    body_close = html.lower().rfind("</div>")
    footer = html.lower().index("<footer")
    synthese = html.index("Synthese")
    assert synthese < body_close < footer
    assert html.lower().index("</footer>") < html.lower().index("</section>")
    assert "Synthese" in html[html.index("doc-body") : footer]


def test_normalize_moves_prose_from_after_footer_into_doc_body() -> None:
    broken = _SEEDED_PAGE.replace(
        "</footer>\n</section>",
        "</footer>\n<h1>Synthese de la semaine</h1>\n<p>Board note.</p>\n</section>",
    )
    assert broken.lower().index("</footer>") < broken.index("Synthese de la semaine")
    fixed = normalize_document_flow(broken)
    footer = fixed.lower().index("<footer")
    assert fixed.index("Synthese de la semaine") < footer
    assert "Synthese de la semaine" not in fixed[fixed.lower().index("</footer") :]


def test_apply_commands_does_not_append_after_footer() -> None:
    result = apply_document_commands(
        _SEEDED_PAGE,
        [
            {"type": "rename_document", "title": "Board memo"},
            {
                "type": "insert_heading",
                "after_heading": -1,
                "title": "Synthese",
                "level": 2,
            },
            {"type": "insert_paragraph", "after_heading": -1, "text": "Three signals."},
        ],
    )
    assert result["ok"] is True
    html = result["html"]
    assert "<h1>Board memo</h1>" in html or ">Board memo</h1>" in html
    assert "Board memo" in html
    footer = html.lower().index("<footer")
    assert html.index("Synthese") < footer
    assert html.index("Three signals.") < footer
    assert "Board memo" in html[html.index("doc-footer-title") :]


def test_replace_class_removes_palette() -> None:
    html = (
        '<div class="doc-body"><div class="palette" aria-label="palette">'
        '<div class="swatch">#464B4B</div></div><p>Keep</p></div>'
    )
    updated = replace_class(html, "palette", "")
    assert isinstance(updated, str)
    assert "palette" not in updated
    assert "Keep" in updated


def test_leftover_placeholders_lists_seed_copy() -> None:
    found = leftover_placeholders(_SEEDED_PAGE)
    assert "Replace with the working premise" in found
    assert "Document title, industry or service line" in found
    assert "Shaded" in found
    assert "Findings" in found


def test_leftover_placeholders_flags_concatenated_seed_tails() -> None:
    html = (
        "<p>Synthèse hebdomadaire. in a few sentences so the reader can scan "
        "the page before the body.</p>"
        "<p>Topic sentence. Keep paragraphs short. This heading uses the official "
        "Heading 1 style.</p>"
        "<p>Body copy stays Outer Space. Secondary colours are for charts.</p>"
    )
    found = leftover_placeholders(html)
    assert "in a few sentences so the reader can scan" in found
    assert "Keep paragraphs short" in found
    assert "This heading uses the official" in found
    assert "Body copy stays Outer Space" in found
    leftover_tails = leftover_placeholders(
        "<p>Topic. the page before the body.</p>"
        "<p>Secondary colours are for charts and data.</p>"
        "<p>14pt True Blue.</p>"
        "<p>must stand apart from the body.</p>"
        "<p>Hyperlinks in copy look like x</p>"
        "<p>Replace the labels.</p>"
    )
    assert "the page before the body" in leftover_tails
    assert "Secondary colours are for charts" in leftover_tails
    assert "14pt True Blue" in leftover_tails
    assert "must stand apart from the body" in leftover_tails
    assert "Hyperlinks in copy look like" in leftover_tails
    assert "Replace the labels" in leftover_tails


def test_leftover_write_note_marks_incomplete() -> None:
    note = leftover_write_note(_SEEDED_PAGE)
    assert note["incomplete"] is True
    assert note["leftover_placeholders"]
    assert note["leftover_slots"]
    assert "placeholder copy remains" in note["warning"]
    assert "fill_document_slots" in note["warning"]
    assert "apply_document_commands" in note["warning"]
    assert "once more" not in note["warning"]
    assert all(isinstance(slot, str) for slot in note["leftover_slots"])
    assert set(note["leftover_slots"]) <= set(FILL_SLOT_KEYS)
    assert (
        "tables" in note["leftover_slots"] or "tables_heading" in note["leftover_slots"]
    )
    clean = leftover_write_note("<h1>Board memo</h1>")
    assert clean["leftover_placeholders"] == []
    assert clean["leftover_slots"] == []
    if note["leftover_placeholders"]:
        assert note["leftover_slots"]


def test_leftover_write_note_after_one_fill_says_stop() -> None:
    from naas_abi_core.services.agent.context import (
        documents_writes_completed,
        note_documents_write,
    )

    from naas_abi.agents.documents.policy import note_documents_slot_fill

    token = documents_writes_completed.set([])
    try:
        note_documents_write(note_documents_slot_fill())
        note = leftover_write_note(_SEEDED_PAGE)
        assert "placeholder copy remains" in note["warning"]
        assert "Stop and reply" in note["warning"]
        assert "once more" not in note["warning"]
        clean = leftover_write_note("<h1>Board memo</h1>")
        assert clean["leftover_placeholders"] == []
        assert "once more" not in (clean.get("warning") or "")
        assert "Stop and reply" in (clean.get("warning") or "")
    finally:
        documents_writes_completed.reset(token)


def test_leftover_placeholders_flags_seed_table_headers() -> None:
    html = (
        '<table class="fmz-table"><thead><tr>'
        "<th>Topic</th><th>Owner</th><th>Status</th>"
        "</tr></thead></table>"
        '<table class="fmz-shaded"><thead><tr>'
        "<th>Item</th><th>Note</th></tr></thead></table>"
        "<p>Heading 1 style leftover.</p>"
        "<p>Outer Space. Use it when the section is still the same topic.</p>"
    )
    found = leftover_placeholders(html)
    assert "Topic" in found
    assert "Owner" in found
    assert "Item" in found
    assert "Heading 1 style" in found
    assert "Outer Space. Use it when" in found
    assert "tables" in leftover_slots(html)
    assert not any(isinstance(slot, dict) for slot in leftover_slots(html))


def test_replace_text_refuses_a_guessed_passage() -> None:
    html = (
        '<p class="intro">Introduction. State the situation in a few sentences '
        "so the reader can scan the page before the body.</p>"
    )
    updated = replace_text(
        html,
        "State the situation in a few sentences so the reader can scan.",
        "ASIC opened five inquiries.",
    )
    assert "error" in updated


def test_apply_skips_a_missing_find_and_keeps_the_batch() -> None:
    result = apply_document_commands(
        _SEEDED_PAGE,
        [
            {"type": "replace_text", "find": "Kicker or subtitle", "replace": "Audit"},
            {
                "type": "replace_text",
                "find": "Replace with the working premise",
                "replace": "PE is buying the mid-tier.",
            },
            {"type": "rename_document", "title": "Board memo"},
        ],
    )
    assert result["ok"] is True
    assert "replace_text" in result["applied"]
    assert "rename_document" in result["applied"]
    assert result["skipped"]
    assert "Kicker or subtitle" in result["skipped"][0]
    assert "PE is buying the mid-tier." in result["html"]
    assert "Replace with the working premise" not in result["html"]
    assert "Board memo" in result["html"]


def test_last_rename_document_title_reads_the_batch() -> None:
    assert (
        last_rename_document_title(
            [
                {"type": "update_title", "title": "Heading only"},
                {"type": "rename_document", "title": "Forvis Mazars Story"},
            ]
        )
        == "Forvis Mazars Story"
    )
    assert last_rename_document_title([{"type": "update_title", "title": "X"}]) == ""


def test_leftover_placeholders_ignores_css_and_svg_hex() -> None:
    html = (
        "<style>.swatch.ink { background: #464B4B; } .true { color: #0072CE; }</style>"
        '<svg><path fill="#171c8f"/></svg>'
        "<main><p>Board memo this week.</p></main>"
    )
    found = leftover_placeholders(html)
    assert "swatch hex" not in found
    assert "colour palette" not in found
    assert leftover_slots(html) == []


def test_leftover_placeholders_flags_empty_seed_blocks() -> None:
    html = (
        '<section class="page cover"><p class="intro"></p>'
        '<p class="subtitle"></p></section>'
        '<section class="page tables" data-layout="tables">'
        "<h2></h2></section>"
    )
    found = leftover_placeholders(html)
    assert "empty intro" in found
    assert "empty subtitle" in found
    assert "empty heading" in found
    assert "missing tables" in found
    keys = leftover_slots(html)
    assert "intro" in keys
    assert "subtitle" in keys
    assert "tables" in keys


def test_apply_skips_empty_replace_and_keeps_seed_copy() -> None:
    result = apply_document_commands(
        _SEEDED_PAGE,
        [
            {
                "type": "replace_text",
                "find": "Replace with the working premise",
                "replace": "",
            },
            {"type": "rename_document", "title": "Board memo"},
        ],
    )
    assert result["ok"] is True
    assert "rename_document" in result["applied"]
    assert result["skipped"]
    assert "non-empty topic copy" in result["skipped"][0]
    assert "Replace with the working premise" in result["html"]
    assert "Board memo" in result["html"]


def test_apply_failure_does_not_ask_for_another_apply() -> None:
    result = apply_document_commands(
        "<h1>Board memo</h1>",
        [{"type": "replace_text", "find": "<h2>Missing</h2>", "replace": "Nope"}],
    )
    assert result.get("error")
    assert "find and class_name" not in result["error"]
    assert "Do not apply again" in result["error"]
    assert "once more" not in result["error"]
    assert "do not call fill_document_slots" in result["error"]
    assert all(isinstance(slot, str) for slot in result.get("leftover_slots", []))


def test_inline_mark_targets_visible_text_and_preserves_head():
    from naas_abi.tools.documents_commands import apply_mark

    seed = '<html><head><title>Proposal</title><style>.Proposal{}</style></head><body><h1 title="Proposal">Proposal</h1></body></html>'
    result = apply_mark(seed, "Proposal")
    assert "<title>Proposal</title>" in result
    assert '<h1 title="Proposal"><strong>Proposal</strong></h1>' in result


def test_inline_mark_refuses_ambiguous_text_and_unsafe_link():
    from naas_abi.tools.documents_commands import apply_mark, insert_link

    assert "error" in apply_mark("<p>Same</p><p>Same</p>", "Same")
    assert "error" in insert_link("<p>Open</p>", "Open", "javascript:alert(1)")


def test_replace_text_preserves_attributes_and_escapes_user_text():
    result = replace_text('<p title="Old">Old</p>', "Old", "<script>bad()</script>")
    assert result == '<p title="Old">&lt;script&gt;bad()&lt;/script&gt;</p>'
