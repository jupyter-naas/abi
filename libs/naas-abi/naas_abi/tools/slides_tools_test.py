"""Unit tests for slides tool helpers (no Forgejo)."""

from __future__ import annotations

from pathlib import Path

from naas_abi.tools.slides_tools import (
    _DATA_URL_RE,
    _REDACTED_PLACEHOLDER,
    _WIPED_DECK_ERROR,
    _apply_replacements,
    _apply_replacements_in_section,
    _assets_dir_from_deck,
    _cover_h1_text,
    _cover_subtitle_text,
    _deck_path,
    _ensure_coding_repo,
    _friendly_sc_error,
    _persist_asset,
    _persist_deck,
    _redact_data_urls,
    _replace_string_pairs,
    _resolve_slug,
    _restore_redacted_data_urls,
    _section_meta,
    _split_sections,
    _validate_asset_filename,
    _view_for_llm,
    slides_tools,
)
from naas_abi_core.services.agent.context import (
    agent_user_id,
    agent_workspace_id,
    slides_active_slug,
    slides_research_queries,
    slides_research_required,
)
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.SourceControlPorts import RepoNotFoundError
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)

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


def _bind_in_memory_git(monkeypatch):
    sc = SourceControlService(InMemoryAdapter())
    monkeypatch.setattr(
        "naas_abi.tools.slides_tools._get_source_control", lambda: sc
    )
    monkeypatch.setattr(
        "naas_abi.tools.slides_tools._repo_id", lambda: "abi/monorepo"
    )
    return sc


def _slides_context(*, workspace: str = "ws-test", slug: str = "untitled-local"):
    tokens = [
        agent_workspace_id.set(workspace),
        slides_active_slug.set(slug),
        agent_user_id.set("user-1"),
        slides_research_required.set(False),
        slides_research_queries.set(None),
    ]
    return tokens


def _reset_tokens(tokens) -> None:
    agent_workspace_id.reset(tokens[0])
    slides_active_slug.reset(tokens[1])
    agent_user_id.reset(tokens[2])
    slides_research_required.reset(tokens[3])
    slides_research_queries.reset(tokens[4])


def test_friendly_sc_error_never_returns_raw_repo_id():
    assert _friendly_sc_error(RepoNotFoundError("abi/monorepo")) == _WIPED_DECK_ERROR
    assert (
        _friendly_sc_error(
            RepoNotFoundError("abi/monorepo:slides/ws-test/untitled-local/deck.html")
        )
        == _WIPED_DECK_ERROR
    )
    assert (
        _friendly_sc_error(RepoNotFoundError("abi/monorepo@slides/ws-test/untitled-local"))
        == _WIPED_DECK_ERROR
    )
    assert _friendly_sc_error(RepoNotFoundError("abi/monorepo")) != "abi/monorepo"


def test_ensure_coding_repo_seeds_empty_in_memory_on_write(monkeypatch):
    sc = _bind_in_memory_git(monkeypatch)
    try:
        sc.list_branches(repo_id="abi/monorepo")
        raise AssertionError("empty in_memory should not have the coding repo")
    except RepoNotFoundError as exc:
        assert str(exc) == "abi/monorepo"
    tokens = _slides_context()
    try:
        assert _ensure_coding_repo() == "abi/monorepo"
        assert [b.name for b in sc.list_branches(repo_id="abi/monorepo")]
        result = _persist_deck(
            "untitled-local",
            "<html><body><main><section class='slide'>"
            "<h1>Iran now</h1></section></main></body></html>",
            "Write via Abi",
        )
        assert result.get("error") != "abi/monorepo"
        assert "error" not in result, result
        assert result["path"] == "slides/ws-test/untitled-local/deck.html"
        assert result["branch"] == "slides/ws-test/untitled-local"
        deck = sc.get_file(
            repo_id="abi/monorepo",
            path="slides/ws-test/untitled-local/deck.html",
            ref="slides/ws-test/untitled-local",
        )
        assert "Iran now" in (deck.text or "")
        meta = sc.get_file(
            repo_id="abi/monorepo",
            path="slides/ws-test/untitled-local/project.json",
            ref="slides/ws-test/untitled-local",
        )
        assert "ws-test" in (meta.text or "")
    finally:
        _reset_tokens(tokens)


def test_replace_write_path_matches_ui_create(monkeypatch):
    """UI create seeds namespaced deck.html; replace must edit that file."""
    sc = _bind_in_memory_git(monkeypatch)
    sc.ensure_repo(owner="abi", name="monorepo")
    sc.create_branch(
        repo_id="abi/monorepo",
        name="slides/ws-test/untitled-local",
        from_ref="main",
    )
    seed = (
        "<!DOCTYPE html><html><body><main>"
        '<section id="slide-cover" class="slide cover">'
        "<h1>Presentation Title</h1>"
        "</section></main></body></html>"
    )
    sc.upsert_file(
        repo_id="abi/monorepo",
        path="slides/ws-test/untitled-local/deck.html",
        content=seed,
        message="Seed deck",
        branch="slides/ws-test/untitled-local",
    )
    sc.upsert_file(
        repo_id="abi/monorepo",
        path="slides/ws-test/untitled-local/project.json",
        content='{"slug":"untitled-local","workspace_id":"ws-test"}\n',
        message="Seed project",
        branch="slides/ws-test/untitled-local",
    )
    tokens = _slides_context()
    try:
        assert _deck_path("untitled-local") == "slides/ws-test/untitled-local/deck.html"
        replace = next(
            t for t in slides_tools() if t.name == "replace_in_slides_deck"
        )
        result = replace.invoke(
            {
                "old": "Presentation Title",
                "new": "Iran briefing",
                "section_index": 0,
                "occurrence": 0,
            }
        )
        assert result.get("error") != "abi/monorepo"
        assert "error" not in result, result
        assert result["path"] == "slides/ws-test/untitled-local/deck.html"
        assert result.get("cover_h1_updated") is True
        deck = sc.get_file(
            repo_id="abi/monorepo",
            path="slides/ws-test/untitled-local/deck.html",
            ref="slides/ws-test/untitled-local",
        )
        assert _cover_h1_text(deck.text or "") == "Iran briefing"
    finally:
        _reset_tokens(tokens)


def test_missing_repo_error_is_wipe_message(monkeypatch):
    class _MissingRepo:
        def ensure_repo(self, **_kwargs):
            raise RepoNotFoundError("abi/monorepo")

        def list_branches(self, **_kwargs):
            raise RepoNotFoundError("abi/monorepo")

        def upsert_file(self, **_kwargs):
            raise RepoNotFoundError("abi/monorepo")

    monkeypatch.setattr(
        "naas_abi.tools.slides_tools._get_source_control",
        lambda: _MissingRepo(),
    )
    monkeypatch.setattr(
        "naas_abi.tools.slides_tools._repo_id", lambda: "abi/monorepo"
    )
    tokens = _slides_context()
    try:
        result = _persist_deck(
            "untitled-local",
            "<html><body><main><section><h1>X</h1></section></main></body></html>",
            "Write via Abi",
        )
        assert result.get("error") == _WIPED_DECK_ERROR
        assert result.get("error") != "abi/monorepo"
    finally:
        _reset_tokens(tokens)


def test_validate_asset_filename() -> None:
    assert _validate_asset_filename("hero.svg") == "hero.svg"
    assert _validate_asset_filename("../x")["error"]
    assert _assets_dir_from_deck("slides/ws-test/untitled-local/deck.html") == (
        "slides/ws-test/untitled-local/assets"
    )


def test_save_slides_asset_lands_in_assets(monkeypatch) -> None:
    sc = _bind_in_memory_git(monkeypatch)
    sc.ensure_repo(owner="abi", name="monorepo")
    sc.create_branch(
        repo_id="abi/monorepo",
        name="slides/ws-test/untitled-local",
        from_ref="main",
    )
    sc.upsert_file(
        repo_id="abi/monorepo",
        path="slides/ws-test/untitled-local/deck.html",
        content="<html></html>",
        message="Seed deck",
        branch="slides/ws-test/untitled-local",
    )
    sc.upsert_file(
        repo_id="abi/monorepo",
        path="slides/ws-test/untitled-local/project.json",
        content='{"slug":"untitled-local","workspace_id":"ws-test"}\n',
        message="Seed project",
        branch="slides/ws-test/untitled-local",
    )
    tokens = _slides_context()
    try:
        result = _persist_asset(
            "untitled-local",
            "hero.svg",
            "<svg xmlns='http://www.w3.org/2000/svg'></svg>",
            "Save hero",
        )
        assert "error" not in result, result
        assert result["path"] == "slides/ws-test/untitled-local/assets/hero.svg"
        saved = sc.get_file(
            repo_id="abi/monorepo",
            path="slides/ws-test/untitled-local/assets/hero.svg",
            ref="slides/ws-test/untitled-local",
        )
        assert "<svg" in (saved.text or "")
        tool = next(t for t in slides_tools() if t.name == "save_slides_asset")
        written = tool.invoke(
            {"filename": "logo.svg", "content": "<svg id='logo'></svg>"}
        )
        assert "error" not in written, written
        assert written["filename"] == "logo.svg"
    finally:
        _reset_tokens(tokens)
