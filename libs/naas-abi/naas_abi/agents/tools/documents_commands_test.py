from naas_abi.agents.tools.documents_commands import (
    PAGE_BREAK_HTML,
    apply_document_commands,
    heading_outline,
    insert_heading,
    insert_page_break,
    insert_paragraph,
    last_rename_document_title,
    update_document_title,
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
    assert "<h2>Findings</h2>" in html
    html = insert_paragraph(html, "A new sentence.", after_heading=2)
    assert "<p>A new sentence.</p>" in html


def test_batch_commands_page_break_then_heading() -> None:
    result = apply_document_commands(
        _SAMPLE,
        [
            {"type": "insert_page_break", "after_heading": 1},
            {"type": "insert_heading", "after_heading": 1, "title": "Annex", "level": 2},
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
            {"type": "replace_text", "find": "Document Title", "replace": "Board update"},
            {"type": "update_paragraph_style", "heading_index": 1, "style": "heading3"},
        ],
    )
    assert result["ok"] is True
    assert "Board update" in result["html"]
    assert "<h3>Introduction</h3>" in result["html"]


def test_delete_range_refuses_last_heading() -> None:
    one = "<main class='document'><section class='page'><h1>Only</h1><p>x</p></section></main>"
    result = apply_document_commands(one, [{"type": "delete_range", "heading_index": 0}])
    assert "error" in result


def test_unknown_command_is_rejected() -> None:
    result = apply_document_commands(_SAMPLE, [{"type": "insert_slide"}])
    assert "error" in result
    assert "insert_page_break" in result["error"]


def test_empty_requests_rejected() -> None:
    assert "error" in apply_document_commands(_SAMPLE, [])


def test_update_document_title_sets_tab_and_cover() -> None:
    html = "<html><head><title>Document Title</title></head><body>" + _SAMPLE + "</body></html>"
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
    assert last_rename_document_title([{"type": "update_title", "title": "Cover only"}]) == ""


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
