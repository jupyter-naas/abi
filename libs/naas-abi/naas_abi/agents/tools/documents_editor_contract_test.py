"""TDD: Documents editor verbs shared by CLI, HTTP, and DocumentsAgent."""

from __future__ import annotations

import inspect

from naas_abi.agents.DocumentsAgent import DOCUMENTS_GUIDELINES, DocumentsAgent
from naas_abi.agents.tools.documents_commands import (
    apply_document_commands,
    delete_block,
    insert_list,
    insert_table,
    leftover_placeholders,
    leftover_slots,
    reflow_document,
    replace_class,
    update_paragraph_style,
)
from naas_abi.agents.tools.documents_slots import fill_document_slots

_FLOWING_MEMO = """<!doctype html><html><head><title>Note au board</title></head><body>
<main class="document">
<section class="page flow" data-layout="flow">
  <div class="doc-body">
    <div class="doc-region" data-layout="cover">
      <h1 class="fmz-title" data-slot="title">Valider le cadre de réponse du cabinet aux évolutions de place qui arrivent plus vite que nos notes</h1>
      <p class="fmz-subtitle subtitle" data-slot="subtitle">Audit et conseil, Board France</p>
      <p class="intro" data-slot="intro">Cette note demande une décision, pas un débat d'actualité.</p>
      <div class="decision" data-slot="decision">
        <p class="decision-label" data-slot="decision-label">Décision demandée</p>
        <p class="decision-text" data-slot="note">Approuver un cadre de réponse unique pour la France.</p>
      </div>
      <h2 class="fmz-heading-1" data-slot="situation-heading">Situation</h2>
      <p class="fmz-normal" data-slot="situation">Les missions reçoivent déjà des questions sur un sujet de place encore instable.</p>
    </div>
    <div class="doc-region" data-layout="content">
      <h2 class="fmz-heading-1" data-slot="section-0">Ce qui a changé</h2>
      <p data-slot="section-0-body">Les signaux sont publics et simultanés.</p>
      <h3 class="fmz-heading-2" data-slot="section-1">Implications pour le cabinet</h3>
      <p data-slot="section-1-body">Quatre expositions, dans cet ordre.</p>
      <div class="cols impl">
        <h4 class="fmz-heading-3" data-slot="impl-risk-heading">Risque</h4>
        <p data-slot="impl-risk">Une phrase trop précise engage le cabinet.</p>
      </div>
    </div>
    <div class="doc-region" data-layout="tables">
      <h2 data-slot="tables-heading">Demande au board</h2>
      <p data-slot="tables-intro">Trois sujets seulement.</p>
      <table class="fmz-table" data-slot="table-0"><thead><tr><th>Sujet</th></tr></thead><tbody><tr><td>Cadre</td></tr></tbody></table>
    </div>
  </div>
  <footer class="doc-footer"><span class="doc-footer-title">Note au board</span></footer>
</section>
</main></body></html>"""

_LOCKED_THREE_PAGES = """<!doctype html><html><body>
<main class="document">
<section class="page cover" data-layout="cover">
  <div class="doc-body">
    <h1 class="fmz-title">Cover title</h1>
    <p class="intro" data-slot="intro">Cover intro stays.</p>
    <div class="decision"><p class="decision-text" data-slot="note">Décision demandée</p></div>
    <h2 data-slot="situation-heading">Situation</h2>
    <p data-slot="situation">Les missions reçoivent déjà des questions.</p>
  </div>
  <footer>1</footer>
</section>
<div class="page-break" data-nexus-page-break></div>
<section class="page content" data-layout="content">
  <div class="doc-body">
    <h2 data-slot="section-0">Discussion</h2>
    <p data-slot="section-0-body">Body that must remonter.</p>
  </div>
  <footer>2</footer>
</section>
<div class="page-break" data-nexus-page-break></div>
<section class="page tables" data-layout="tables">
  <div class="doc-body">
    <h2>Findings</h2>
    <table class="fmz-table"><tr><td>Row</td></tr></table>
  </div>
  <footer>3</footer>
</section>
</main></body></html>"""


def test_replace_class_empty_deletes_decision() -> None:
    html = '<div class="doc-body"><div class="decision"><p>Décision demandée</p></div><p>Keep</p></div>'
    updated = replace_class(html, "decision", "")
    assert isinstance(updated, str)
    assert "decision" not in updated
    assert "Keep" in updated


def test_delete_block_removes_situation_without_sidecar() -> None:
    html = (
        '<h2 data-slot="situation-heading">Situation</h2>'
        '<p data-slot="situation">Les missions reçoivent déjà des questions.</p>'
        "<p>Keep</p>"
    )
    updated = delete_block(html, slot="situation")
    assert isinstance(updated, str)
    assert "situation" not in updated
    assert "Keep" in updated


def test_style_any_block_via_slot_not_heading_index_only() -> None:
    html = '<p class="intro" data-slot="intro">Cover intro stays.</p><h2>Later</h2>'
    updated = update_paragraph_style(html, style="normal", slot="intro")
    assert isinstance(updated, str)
    assert "fmz-normal" in updated
    assert 'data-slot="intro"' in updated
    assert "Cover intro stays." in updated
    assert "<h2>Later</h2>" in updated


def test_apply_styles_intro_via_slot() -> None:
    result = apply_document_commands(
        '<p class="intro" data-slot="intro">Cover intro stays.</p>',
        [{"type": "update_paragraph_style", "slot": "intro", "style": "normal"}],
    )
    assert result["ok"] is True
    assert "fmz-normal" in result["html"]


def test_insert_list_and_table_are_first_class_verbs() -> None:
    html = '<div class="doc-body"><h2>Head</h2></div>'
    listed = insert_list(html, ["One", "Two"], after_heading=0)
    assert "<ul" in listed
    assert "<li>One</li>" in listed
    tabled = insert_table(listed, ["Col"], [["Cell"]], after_heading=0)
    assert "<table" in tabled
    assert "fmz-table" in tabled
    assert "Cell" in tabled
    result = apply_document_commands(
        html,
        [
            {"type": "insert_list", "items": ["A"], "after_heading": 0},
            {
                "type": "insert_table",
                "headers": ["H"],
                "rows": [["R"]],
                "after_heading": 0,
            },
        ],
    )
    assert result["ok"] is True
    assert "insert_list" in result["applied"]
    assert "insert_table" in result["applied"]


def test_reflow_after_cover_chrome_delete_remonte_le_texte() -> None:
    html = replace_class(_LOCKED_THREE_PAGES, "decision", "")
    assert isinstance(html, str)
    html = delete_block(html, slot="situation")
    assert isinstance(html, str)
    moved = reflow_document(html)
    assert "Body that must remonter." in moved
    first_close = moved.lower().index("</section>")
    assert "Body that must remonter." in moved[:first_close]
    pages = moved.lower().count("<section")
    assert pages == 2
    assert "data-nexus-page-break" in moved
    empty_bodies = moved.count('<div class="doc-body">\n  </div>')
    assert empty_bodies == 0


def test_leftover_flags_french_board_memo_seed() -> None:
    found = leftover_placeholders(_FLOWING_MEMO)
    assert any(
        "Cette note demande une décision" in item or "décision" in item.lower()
        for item in found
    )
    assert any("missions reçoivent" in item for item in found)
    assert "Décision demandée" in found
    slots = leftover_slots(_FLOWING_MEMO)
    assert "intro" in slots or "note" in slots or "situation" in slots


def test_fill_optional_note_deletes_decision_and_owns_situation() -> None:
    result = fill_document_slots(
        _FLOWING_MEMO,
        {
            "title": "CAC EDF win plan",
            "subtitle": "Board France, audit",
            "intro": "EDF opened the CAC window this week.",
            "situation": "Missions already get the same question from three desks.",
            "quote": "One owner, one line, no external phrase this week.",
            "sections": [
                {
                    "heading": "What changed",
                    "body": "Public signals arrived together.",
                },
                {
                    "heading": "What we do",
                    "body": "Name an owner and keep silence external.",
                },
                {
                    "heading": "Extra heading one",
                    "body": "This extra must append, not overwrite Risque.",
                },
            ],
            "tables_heading": "Ask",
            "tables_intro": "Three rows only.",
            "tables": [
                {"heading": "Ask table", "headers": ["Item"], "rows": [["Owner"]]},
            ],
        },
    )
    assert result["ok"] is True
    html = result["html"]
    assert "decision" not in html
    assert "Décision demandée" not in html
    assert "Missions already get the same question" in html
    assert 'data-slot="situation"' in html
    assert "Risque" in html
    assert "Une phrase trop précise engage le cabinet." in html
    assert "Extra heading one" in html
    assert "fmz-heading-1" in html
    assert html.count("Extra heading one") == 1


def test_fill_layout_range_reads_flowing_div_regions() -> None:
    result = fill_document_slots(
        _FLOWING_MEMO,
        {
            "title": "Topic title",
            "subtitle": "Line",
            "intro": "Intro sentence for the board.",
            "note": "Keep the decision box this time.",
            "situation": "Situation owned by fill.",
            "quote": "Quote for the memo.",
            "sections": [
                {"heading": "First", "body": "First body."},
                {"heading": "Second", "body": "Second body."},
            ],
            "tables_heading": "Tables",
            "tables_intro": "Table intro.",
            "tables": [{"heading": "T", "headers": ["A"], "rows": [["B"]]}],
        },
    )
    assert result["ok"] is True
    assert "First body." in result["html"]
    assert "Situation owned by fill." in result["html"]
    assert "Keep the decision box this time." in result["html"]


def test_documents_agent_has_no_sidecar_file_tools() -> None:
    source = inspect.getsource(DocumentsAgent.New)
    assert "enable_default_tools=False" in source
    names = {tool.name for tool in DocumentsAgent.get_tools()}
    assert "run_terminal" not in names
    assert "write_file" not in names
    assert "read_file" not in names
    lowered = DOCUMENTS_GUIDELINES.lower()
    assert "document.html" in lowered
    assert "server applies content" in lowered
    assert "successful write completes" in lowered
