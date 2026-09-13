from naas_abi.agents.tools.documents_commands import leftover_placeholders
from naas_abi.agents.tools.documents_slots import fill_document_slots

_SEED = """<!doctype html><html><head><title>Document title</title></head><body>
<main class="document">
<section class="page cover" data-layout="cover">
  <div class="doc-body">
    <h1 data-slot="title">Document title</h1>
    <p class="subtitle" data-slot="subtitle">Industry or service line</p>
    <p class="intro" data-slot="intro">Introduction. State the situation in a few sentences so the reader can scan the page before the body.</p>
    <p class="note" data-slot="note">Header text alternates between True Blue and Dark Space. Body copy stays Outer Space.</p>
    <div class="palette" aria-label="Forvis Mazars colour palette"><div class="swatch">#464B4B</div></div>
  </div>
  <footer class="doc-footer"><span class="doc-footer-title">Document title, industry or service line</span></footer>
</section>
<section class="page content" data-layout="content">
  <div class="doc-body">
    <h2 data-slot="section-0">Discussion</h2>
    <p data-slot="section-0-body">Develop the argument here. Keep paragraphs short. This heading uses the official Heading 1 style.</p>
    <ul data-slot="section-0-list">
      <li>First point, written as a complete sentence.</li>
    </ul>
    <h3 data-slot="section-1">Supporting detail</h3>
    <p data-slot="section-1-body">Heading 2 stays Outer Space. Use it when the section is still the same topic.</p>
    <blockquote data-slot="quote">Use the Quote style for a short extract that must stand apart from the body.</blockquote>
    <h4 data-slot="section-2">A narrower point</h4>
    <p data-slot="section-2-body">Heading 3 uses the mid blue. Hyperlinks in copy look like x.</p>
  </div>
  <footer class="doc-footer"><span class="doc-footer-title">Document title, industry or service line</span></footer>
</section>
<section class="page tables" data-layout="tables">
  <div class="doc-body">
    <h2 data-slot="tables-heading">Findings</h2>
    <p data-slot="tables-intro">Two official table styles. Replace the labels. Do not put confidential figures in a seed.</p>
    <h3 data-slot="table-0-heading">Non shaded</h3>
    <table class="fm-table" data-slot="table-0">
      <thead><tr><th>Topic</th><th>Owner</th><th>Status</th></tr></thead>
      <tbody><tr><td>Scope</td><td>Lead</td><td>Open</td></tr></tbody>
    </table>
    <h3 data-slot="table-1-heading">Shaded</h3>
    <table class="fm-shaded" data-slot="table-1">
      <thead><tr><th>Item</th><th>Note</th></tr></thead>
      <tbody><tr><td>Assumption</td><td>Replace with the working premise.</td></tr></tbody>
    </table>
  </div>
  <footer class="doc-footer"><span class="doc-footer-title">Document title, industry or service line</span></footer>
</section>
</main></body></html>"""

_COMPLETE = {
    "title": "Memo executif audit et conseil",
    "subtitle": "Synthese board, semaine du 1 au 12 septembre 2026",
    "intro": "Les cabinets font face a une fronde anti-ESG aux Etats-Unis et a un fini de cadre deontologique en France.",
    "note": "Confidentiel. Sources: AEF, CNCC, H2A. Periode: 1-12 septembre 2026.",
    "quote": "La fronde vise desormais ceux qui certifient et conseillent.",
    "sections": [
        {
            "heading": "Faits marquants",
            "body": "Seize procureurs generaux ont vise le Big Four le 4 septembre pour activisme climatique.",
            "bullets": [
                "Le decret 2026-176 integre les OTI au code de deontologie.",
                "Les Big Four poursuivent leurs restructurations europeennes.",
                "La correction Quemener a ete confirmee par le Conseil d Etat.",
            ],
        },
        {
            "heading": "Ce que cela change",
            "body": "Les mandats transatlantiques doivent documenter les engagements climatiques avec plus de prudence.",
        },
        {
            "heading": "Point de vigilance",
            "body": "Le board doit arbitrer l exposition ESG americaine avant la rentre des campagnes 2027.",
        },
    ],
    "tables_heading": "Signaux de la semaine",
    "tables_intro": "Quatre themes a suivre: reglementaire US, cadre FR, concurrentiel, fiscalite.",
    "tables": [
        {
            "heading": "Reglementaire",
            "headers": ["Sujet", "Acteur", "Impact"],
            "rows": [
                ["Fronde ESG", "16 AG US", "Hausse"],
                ["Decret 2026-176", "H2A", "Stable"],
            ],
        },
        {
            "heading": "A arbitrer",
            "headers": ["Dossier", "Implication"],
            "rows": [
                ["Mandats US", "Revue de documentation ESG"],
                ["Sous-traitance", "Suivi des restructurations"],
            ],
        },
    ],
}


def test_fill_document_slots_clears_seed_copy() -> None:
    result = fill_document_slots(_SEED, _COMPLETE)
    assert result["ok"] is True
    html = result["html"]
    assert leftover_placeholders(html) == []
    assert result["missing_slots"] == []
    assert result["incomplete"] is False
    assert "section_index" in result
    assert result["section_count"] >= 1
    assert "Memo executif audit et conseil" in html
    assert "Faits marquants" in html
    assert "Signaux de la semaine" in html
    assert "Sujet" in html
    assert "Industry or service line" not in html
    assert "Discussion" not in html
    assert "Findings" not in html
    assert "Topic" not in html
    assert "palette" not in html
    footer = html.lower().index("</footer>")
    section = html.lower().index("</section>", footer)
    assert not html[footer + len("</footer>") : section].strip()


def test_fill_document_slots_rejects_empty_values() -> None:
    result = fill_document_slots(_SEED, {**_COMPLETE, "intro": "   "})
    assert result.get("error")
    assert "intro" in result["error"]


def test_fill_document_slots_lists_omitted_slots() -> None:
    payload = {k: v for k, v in _COMPLETE.items() if k != "quote"}
    result = fill_document_slots(_SEED, payload)
    assert result["ok"] is True
    assert "quote" in result["missing_slots"]
    assert result["incomplete"] is True
    assert "Use the Quote style" in result["html"]


def test_fill_document_slots_ignores_unknown_keys() -> None:
    result = fill_document_slots(_SEED, {**_COMPLETE, "soundtrack": "nope"})
    assert result["ok"] is True
    assert leftover_placeholders(result["html"]) == []


def test_fill_document_slots_works_without_data_slot() -> None:
    bare = _SEED.replace(" data-slot=\"title\"", "")
    bare = bare.replace(" data-slot=\"subtitle\"", "")
    bare = bare.replace(" data-slot=\"intro\"", "")
    bare = bare.replace(" data-slot=\"note\"", "")
    result = fill_document_slots(bare, _COMPLETE)
    assert result["ok"] is True
    assert "Synthese board" in result["html"]
    assert leftover_placeholders(result["html"]) == []
