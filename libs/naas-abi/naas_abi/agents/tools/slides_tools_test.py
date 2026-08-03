"""Unit tests for slides tool helpers (no Forgejo)."""

from __future__ import annotations

from pathlib import Path

from naas_abi.agents.tools.slides_tools import (
    _DATA_URL_RE,
    _REDACTED_PLACEHOLDER,
    _apply_replacements,
    _apply_replacements_in_section,
    _cover_h1_text,
    _cover_subtitle_text,
    _redact_data_urls,
    _replace_string_pairs,
    _resolve_slug,
    _restore_redacted_data_urls,
    _section_meta,
    _split_sections,
    _view_for_llm,
)
from naas_abi_core.services.agent.context import slides_active_slug

_SAMPLE = """<!DOCTYPE html>
<html><head></head><body>
<main class="deck">
<section id="slide-cover" class="slide cover">
  <h1>Presentation Title &amp; Overview</h1>
  <img src="data:image/png;base64,AAAA" />
</section>
<!-- gap -->
<section id="slide-agenda" class="slide">
  <h1>Agenda</h1>
  <p>Session details</p>
</section>
</main>
<script>const IMG = {"hero": "data:image/png;base64,HEAVYASSETDATA"}</script>
</body></html>
"""

_TEMPLATE = (
    Path(__file__).resolve().parents[2]
    / "apps"
    / "nexus"
    / "assets"
    / "slides"
    / "templates"
    / "minimal-light-v1.html"
)


def test_redact_data_urls_shrinks_payload_and_counts():
    html = "x" + ("data:image/jpeg;base64," + ("A" * 5000)) + "y"
    redacted, count = _redact_data_urls(html)
    assert count == 1
    assert _REDACTED_PLACEHOLDER in redacted
    assert len(redacted) < len(html)


def test_split_sections_preserves_prefix_suffix_and_ids():
    prefix, sections, suffix = _split_sections(_SAMPLE)
    assert "<main" in prefix
    assert len(sections) == 2
    assert 'id="slide-cover"' in sections[0]
    assert 'id="slide-agenda"' in sections[1]
    assert "HEAVYASSETDATA" in suffix
    assert prefix + "".join(sections) + suffix == _SAMPLE


def test_section_meta_exposes_title_without_assets():
    _prefix, sections, _suffix = _split_sections(_SAMPLE)
    meta = _section_meta(0, sections[0])
    assert meta["index"] == 0
    assert meta["id"] == "slide-cover"
    assert "Presentation" in meta["title"]
    assert meta["redacted_assets"] == 1


def test_restore_redacted_data_urls_round_trip():
    original = (
        '<section><img src="data:image/png;base64,QQQQ"/>'
        '<img src="data:image/png;base64,RRRR"/></section>'
    )
    redacted, count = _redact_data_urls(original)
    assert count == 2
    edited = redacted.replace("<section>", '<section data-x="1">')
    restored = _restore_redacted_data_urls(edited, original)
    assert _DATA_URL_RE.findall(restored) == _DATA_URL_RE.findall(original)
    assert _REDACTED_PLACEHOLDER not in restored


def test_view_for_llm_strips_heavy_scripts():
    view = _view_for_llm(_SAMPLE)
    assert "HEAVYASSETDATA" not in view["html"]
    assert view["redacted_scripts"] >= 1
    assert view["chars_redacted"] < view["chars"]


def test_resolve_slug_defaults_to_open_deck_context():
    token = slides_active_slug.set("q3-br")
    try:
        assert _resolve_slug("") == "q3-br"
        assert _resolve_slug("other-deck") == "other-deck"
    finally:
        slides_active_slug.reset(token)


def test_resolve_slug_errors_without_context():
    token = slides_active_slug.set(None)
    try:
        err = _resolve_slug("")
        assert isinstance(err, dict)
        assert "error" in err
    finally:
        slides_active_slug.reset(token)


def test_real_template_sections_round_trip_and_compact_view():
    if not _TEMPLATE.is_file():
        return
    html = _TEMPLATE.read_text()
    prefix, sections, suffix = _split_sections(html)
    assert len(sections) == 10
    assert prefix + "".join(sections) + suffix == html
    assert "Presentation Title" in sections[0]
    low = html.lower()
    assert "forvis" not in low
    assert "mazars" not in low
    assert "iso 27001" not in low
    view = _view_for_llm(html)
    # Editable surface must stay far below the ~256k-token failure mode.
    assert view["chars_redacted"] < 120_000
    assert view["section_count"] == 10


def test_replace_string_pairs_covers_amp_entity():
    pairs = _replace_string_pairs(
        "Presentation Title & Overview",
        "Presentation Title & Overview test",
    )
    olds = {o for o, _ in pairs}
    news = {n for _, n in pairs}
    assert "Presentation Title & Overview" in olds
    assert "Presentation Title &amp; Overview" in olds
    assert "Presentation Title &amp; Overview test" in news


def test_apply_replacements_updates_h1_and_script_footer():
    """Cover-like HTML: same title as both ``&amp;`` (H1) and ``&`` (script)."""
    html = (
        "<!DOCTYPE html><html><body><main>"
        '<section id="slide-cover" class="slide cover">'
        "<h1>Presentation Title &amp; Overview</h1>"
        "</section>"
        "</main>"
        '<script>const FOOTER_TXT = "Presentation Title & Overview";</script>'
        "</body></html>"
    )
    applied = _apply_replacements(
        html,
        "Presentation Title & Overview",
        "Presentation Title & Overview test",
        0,
    )
    assert not isinstance(applied, dict)
    updated, found, replaced = applied
    assert found == 2
    assert replaced == 2
    assert "<h1>Presentation Title &amp; Overview test</h1>" in updated
    assert 'FOOTER_TXT = "Presentation Title & Overview test"' in updated
    assert "Presentation Title &amp; Overview</h1>" not in updated
    assert _cover_h1_text(updated) == "Presentation Title & Overview test"


def test_section_scoped_replace_updates_cover_h1_not_document_title():
    """occurrence=1 document-wide hits <title>; section_index=0 hits cover H1."""
    html = (
        "<!DOCTYPE html><html><head>"
        "<title>Presentation Title &amp; Overview | Deck</title>"
        "</head><body><main>"
        '<section id="slide-cover">'
        "<h1>Presentation Title &amp; Overview</h1>"
        "</section>"
        '<section id="slide-two"><h1>Agenda</h1></section>'
        "</main>"
        '<script>const FOOTER_TXT = "Presentation Title & Overview";</script>'
        "</body></html>"
    )
    doc_first = _apply_replacements(
        html,
        "Presentation Title & Overview",
        "Presentation Title & Overview COCO",
        1,
    )
    assert not isinstance(doc_first, dict)
    updated_doc, found, replaced = doc_first
    assert found >= 3
    assert replaced == 1
    # Document-order first hit is <title>, not the visible cover H1.
    assert "<title>Presentation Title &amp; Overview COCO | Deck</title>" in updated_doc
    assert _cover_h1_text(updated_doc) == "Presentation Title & Overview"

    scoped = _apply_replacements_in_section(
        html,
        "Presentation Title & Overview",
        "Presentation Title & Overview COCO",
        0,
        section_index=0,
    )
    assert not isinstance(scoped, dict)
    updated, found, replaced, section_idx = scoped
    assert section_idx == 0
    assert found == 1
    assert replaced == 1
    assert _cover_h1_text(updated) == "Presentation Title & Overview COCO"
    assert "<title>Presentation Title &amp; Overview | Deck</title>" in updated


def test_apply_replacements_matches_mdash_entity_in_cover_subtitle():
    """Regression: searching unicode em dash must update ``&mdash;`` in Preview."""
    html = (
        "<!DOCTYPE html><html><body><main>"
        '<section id="slide-cover" class="slide cover">'
        "<h1>Presentation Title</h1>"
        '<p class="subtitle">Securing quality certification &mdash; best practices '
        "and a phased delivery roadmap.</p>"
        "</section>"
        "</main>"
        '<script>const NOTE = "certification — best practices";</script>'
        "</body></html>"
    )
    assert _cover_subtitle_text(html)
    assert "—" in _cover_subtitle_text(html)  # unescaped view
    # Search with entity form (what Abi often copies from read tools).
    applied = _apply_replacements(
        html,
        "certification &mdash; best practices",
        "certification: best practices",
        0,
    )
    assert not isinstance(applied, dict)
    updated, found, replaced = applied
    assert found >= 2  # subtitle entity + script unicode
    assert replaced == found
    assert "&mdash;" not in updated
    assert "—" not in updated.split("<script>")[0]
    assert "certification: best practices" in updated
    assert "certification: best practices" in (_cover_subtitle_text(updated) or "")

    # Search with literal unicode em dash must also hit ``&mdash;``.
    applied2 = _apply_replacements(
        html,
        "certification — best practices",
        "certification: best practices",
        0,
    )
    assert not isinstance(applied2, dict)
    updated2, found2, _replaced2 = applied2
    assert found2 >= 2
    assert "certification: best practices" in (_cover_subtitle_text(updated2) or "")


def test_apply_replacements_real_template_cover_title():
    if not _TEMPLATE.is_file():
        return
    html = _TEMPLATE.read_text()
    before = _cover_h1_text(html)
    assert before == "Presentation Title"
    applied = _apply_replacements(
        html,
        "Presentation Title",
        "Presentation Title test",
        0,
    )
    assert not isinstance(applied, dict)
    updated, found, replaced = applied
    assert found >= 2
    assert replaced == found
    assert "<h1>Presentation Title test</h1>" in updated
    assert _cover_h1_text(updated) == "Presentation Title test"
