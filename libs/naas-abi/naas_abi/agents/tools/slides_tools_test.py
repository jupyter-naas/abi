"""Unit tests for slides tool helpers (no Forgejo)."""

from __future__ import annotations

from pathlib import Path

from naas_abi.agents.tools.slides_tools import (
    _DATA_URL_RE,
    _REDACTED_PLACEHOLDER,
    _apply_replacements,
    _apply_replacements_in_section,
    _cover_h1_text,
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
  <h1>Data Governance &amp; Quality Program</h1>
  <img src="data:image/png;base64,AAAA" />
</section>
<!-- gap -->
<section id="slide-agenda" class="slide">
  <h1>Agenda</h1>
  <p>Program details</p>
</section>
</main>
<script>const IMG = {"hero": "data:image/png;base64,HEAVYASSETDATA"}</script>
</body></html>
"""

_TEMPLATE_CANDIDATES = (
    Path(__file__).resolve().parents[2]
    / "apps"
    / "nexus"
    / "assets"
    / "slides"
    / "templates"
    / "bob-fmz-v1.html",
    Path("/Users/jrvmac/abi-naas/src/zen/assets/slides/templates/bob-fmz-v1.html"),
)
_TEMPLATE = next((p for p in _TEMPLATE_CANDIDATES if p.is_file()), _TEMPLATE_CANDIDATES[0])


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
    assert "Program" in meta["title"]
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
    assert len(sections) == 22
    assert prefix + "".join(sections) + suffix == html
    assert "Program" in sections[0]
    view = _view_for_llm(html)
    # Editable surface must stay far below the ~256k-token failure mode.
    assert view["chars_redacted"] < 120_000
    assert view["section_count"] == 22


def test_replace_string_pairs_covers_amp_entity():
    pairs = _replace_string_pairs(
        "Data Governance & Quality Program",
        "Data Governance & Quality Program test",
    )
    olds = {o for o, _ in pairs}
    news = {n for _, n in pairs}
    assert "Data Governance & Quality Program" in olds
    assert "Data Governance &amp; Quality Program" in olds
    assert "Data Governance &amp; Quality Program test" in news


def test_apply_replacements_updates_h1_and_script_footer():
    """Cover-like HTML: same title as both ``&amp;`` (H1) and ``&`` (script)."""
    html = (
        "<!DOCTYPE html><html><body><main>"
        '<section id="slide-cover" class="slide cover">'
        "<h1>Data Governance &amp; Quality Program</h1>"
        "</section>"
        "</main>"
        '<script>const FOOTER_TXT = "Data Governance & Quality Program";</script>'
        "</body></html>"
    )
    applied = _apply_replacements(
        html,
        "Data Governance & Quality Program",
        "Data Governance & Quality Program test",
        0,
    )
    assert not isinstance(applied, dict)
    updated, found, replaced = applied
    assert found == 2
    assert replaced == 2
    assert "<h1>Data Governance &amp; Quality Program test</h1>" in updated
    assert 'FOOTER_TXT = "Data Governance & Quality Program test"' in updated
    assert "Data Governance &amp; Quality Program</h1>" not in updated
    assert _cover_h1_text(updated) == "Data Governance & Quality Program test"


def test_section_scoped_replace_updates_cover_h1_not_document_title():
    """occurrence=1 document-wide hits <title>; section_index=0 hits cover H1."""
    html = (
        "<!DOCTYPE html><html><head>"
        "<title>Data Governance &amp; Quality Program | ISO</title>"
        "</head><body><main>"
        '<section id="slide-cover">'
        "<h1>Data Governance &amp; Quality Program</h1>"
        "</section>"
        "<section id=\"slide-two\"><h1>Agenda</h1></section>"
        "</main>"
        '<script>const FOOTER_TXT = "Data Governance & Quality Program";</script>'
        "</body></html>"
    )
    doc_first = _apply_replacements(
        html,
        "Data Governance & Quality Program",
        "Data Governance & Quality Program COCO",
        1,
    )
    assert not isinstance(doc_first, dict)
    updated_doc, found, replaced = doc_first
    assert found >= 3
    assert replaced == 1
    # Document-order first hit is <title>, not the visible cover H1.
    assert "<title>Data Governance &amp; Quality Program COCO | ISO</title>" in updated_doc
    assert _cover_h1_text(updated_doc) == "Data Governance & Quality Program"

    scoped = _apply_replacements_in_section(
        html,
        "Data Governance & Quality Program",
        "Data Governance & Quality Program COCO",
        0,
        section_index=0,
    )
    assert not isinstance(scoped, dict)
    updated, found, replaced, section_idx = scoped
    assert section_idx == 0
    assert found == 1
    assert replaced == 1
    assert _cover_h1_text(updated) == "Data Governance & Quality Program COCO"
    assert "<title>Data Governance &amp; Quality Program | ISO</title>" in updated


def test_apply_replacements_real_template_cover_title():
    if not _TEMPLATE.is_file():
        return
    html = _TEMPLATE.read_text()
    before = _cover_h1_text(html)
    assert before == "Data Governance & Quality Program"
    applied = _apply_replacements(
        html,
        "Data Governance & Quality Program",
        "Data Governance & Quality Program test",
        0,
    )
    assert not isinstance(applied, dict)
    updated, found, replaced = applied
    # Template has 3 literal-& script hits + many &amp; HTML hits.
    assert found >= 4
    assert replaced == found
    assert "<h1>Data Governance &amp; Quality Program test</h1>" in updated
    assert 'const FOOTER_TXT = "Data Governance & Quality Program test' in updated
    assert _cover_h1_text(updated) == "Data Governance & Quality Program test"
