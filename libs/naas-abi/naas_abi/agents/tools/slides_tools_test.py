"""Unit tests for slides tool helpers (no Forgejo)."""

from __future__ import annotations

from pathlib import Path

from naas_abi.agents.tools.slides_tools import (
    _DATA_URL_RE,
    _REDACTED_PLACEHOLDER,
    _redact_data_urls,
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

_TEMPLATE = Path(
    "/Users/jrvmac/abi-naas/src/zen/assets/slides/templates/bob-fmz-v1.html"
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
