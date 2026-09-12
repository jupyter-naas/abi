"""Unit tests for sections tool helpers (no Forgejo)."""

from __future__ import annotations

import json
from pathlib import Path

from naas_abi.agents.tools.documents_tools import (
    _DATA_URL_RE,
    _REDACTED_PLACEHOLDER,
    _WIPED_DECK_ERROR,
    COMMAND_TOOL_NAMES,
    LEFTOVER_SECTION_TOOL_NAMES,
    _apply_replacements,
    _apply_replacements_in_section,
    _apply_section_writes,
    _cover_h1_text,
    _cover_subtitle_text,
    _delete_section_html,
    _document_path,
    _duplicate_section_html,
    _ensure_coding_repo,
    _forget_active_slugs,
    _friendly_sc_error,
    _insert_section_html,
    _join_sections,
    _parse_section_writes,
    _persist_document,
    _redact_data_urls,
    _reorder_sections_html,
    _replace_string_pairs,
    _resolve_slug,
    _restore_redacted_data_urls,
    _section_meta,
    _split_sections,
    _view_for_llm,
    documents_agent_tools,
    documents_tools,
    maybe_auto_title_open_document,
    resolve_documents_template_id,
)
from naas_abi_core.services.agent.context import (
    agent_user_id,
    agent_workspace_id,
    documents_active_slug,
    documents_active_title,
    documents_brief,
    documents_research_queries,
    documents_research_required,
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
<main class="document">
<section id="section-cover" class="section cover">
  <h1>Presentation Title &amp; Overview</h1>
  <img src="data:image/png;base64,AAAA" />
</section>
<!-- gap -->
<section id="section-agenda" class="section">
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
    / "sections"
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
    assert 'id="section-cover"' in sections[0]
    assert 'id="section-agenda"' in sections[1]
    assert "HEAVYASSETDATA" in suffix
    assert prefix + "".join(sections) + suffix == _SAMPLE


def test_section_meta_exposes_title_without_assets():
    _prefix, sections, _suffix = _split_sections(_SAMPLE)
    meta = _section_meta(0, sections[0])
    assert meta["index"] == 0
    assert meta["id"] == "section-cover"
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
    assert "html" not in view
    dumped = json.dumps(view)
    assert "HEAVYASSETDATA" not in dumped
    assert "data:image" not in dumped
    assert view["redacted_scripts"] >= 1
    assert view["chars_redacted"] < view["chars"]
    assert view["section_count"] == 2
    assert [row["title"] for row in view["sections"]] == [
        "Presentation Title &amp; Overview",
        "Agenda",
    ]


def test_resolve_slug_defaults_to_open_document_context():
    token = documents_active_slug.set("q3-br")
    try:
        assert _resolve_slug("") == "q3-br"
        assert _resolve_slug("other-document") == "other-document"
    finally:
        documents_active_slug.reset(token)


def test_resolve_slug_errors_without_context():
    token = documents_active_slug.set(None)
    try:
        err = _resolve_slug("")
        assert isinstance(err, dict)
        assert "error" in err
    finally:
        documents_active_slug.reset(token)


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
    assert "html" not in view
    assert view["chars_redacted"] < 120_000
    assert view["section_count"] == 10
    assert len(view["sections"]) == 10


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
        '<section id="section-cover" class="section cover">'
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
        "<title>Presentation Title &amp; Overview | Document</title>"
        "</head><body><main>"
        '<section id="section-cover">'
        "<h1>Presentation Title &amp; Overview</h1>"
        "</section>"
        '<section id="section-two"><h1>Agenda</h1></section>'
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
    assert "<title>Presentation Title &amp; Overview COCO | Document</title>" in updated_doc
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
    assert "<title>Presentation Title &amp; Overview | Document</title>" in updated


def test_apply_replacements_matches_mdash_entity_in_cover_subtitle():
    """Regression: searching unicode em dash must update ``&mdash;`` in Preview."""
    html = (
        "<!DOCTYPE html><html><body><main>"
        '<section id="section-cover" class="section cover">'
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
        "naas_abi.agents.tools.documents_tools._get_source_control", lambda: sc
    )
    monkeypatch.setattr(
        "naas_abi.agents.tools.documents_tools._repo_id", lambda: "abi/monorepo"
    )
    return sc


def _seed_in_memory_document(sc, html: str, *, slug: str = "untitled-local"):
    sc.ensure_repo(owner="abi", name="monorepo")
    branch = f"documents/ws-test/{slug}"
    names = {b.name for b in sc.list_branches(repo_id="abi/monorepo")}
    if branch not in names:
        default = "main" if "main" in names else next(iter(names))
        sc.create_branch(repo_id="abi/monorepo", name=branch, from_ref=default)
    sc.upsert_file(
        repo_id="abi/monorepo",
        path=f"documents/ws-test/{slug}/document.html",
        content=html,
        message="Seed document",
        branch=branch,
    )
    return sc


def _sections_context(*, workspace: str = "ws-test", slug: str = "untitled-local"):
    _forget_active_slugs()
    tokens = [
        agent_workspace_id.set(workspace),
        documents_active_slug.set(slug),
        agent_user_id.set("user-1"),
        documents_research_required.set(False),
        documents_research_queries.set(None),
    ]
    return tokens


def _reset_tokens(tokens) -> None:
    agent_workspace_id.reset(tokens[0])
    documents_active_slug.reset(tokens[1])
    agent_user_id.reset(tokens[2])
    documents_research_required.reset(tokens[3])
    documents_research_queries.reset(tokens[4])


def test_friendly_sc_error_never_returns_raw_repo_id():
    assert _friendly_sc_error(RepoNotFoundError("abi/monorepo")) == _WIPED_DECK_ERROR
    assert (
        _friendly_sc_error(
            RepoNotFoundError("abi/monorepo:documents/ws-test/untitled-local/document.html")
        )
        == _WIPED_DECK_ERROR
    )
    assert (
        _friendly_sc_error(RepoNotFoundError("abi/monorepo@documents/ws-test/untitled-local"))
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
    tokens = _sections_context()
    try:
        assert _ensure_coding_repo() == "abi/monorepo"
        assert [b.name for b in sc.list_branches(repo_id="abi/monorepo")]
        result = _persist_document(
            "untitled-local",
            "<html><body><main><section class='section'>"
            "<h1>Iran now</h1></section></main></body></html>",
            "Write via Abi",
        )
        assert result.get("error") != "abi/monorepo"
        assert "error" not in result, result
        assert result["path"] == "documents/ws-test/untitled-local/document.html"
        assert result["branch"] == "documents/ws-test/untitled-local"
        document = sc.get_file(
            repo_id="abi/monorepo",
            path="documents/ws-test/untitled-local/document.html",
            ref="documents/ws-test/untitled-local",
        )
        assert "Iran now" in (document.text or "")
        meta = sc.get_file(
            repo_id="abi/monorepo",
            path="documents/ws-test/untitled-local/project.json",
            ref="documents/ws-test/untitled-local",
        )
        assert "ws-test" in (meta.text or "")
    finally:
        _reset_tokens(tokens)


def test_persist_document_uses_tool_default_type_for_unprefixed_message(monkeypatch):
    """A free-text agent message with no type(scope): prefix must bucket into
    the calling tool's own Conventional Commits type (e.g. "fix" for a text
    replace), not the non-bumping "chore" fallback — otherwise the document
    version never advances even though real content changed."""
    _bind_in_memory_git(monkeypatch)
    tokens = _sections_context()
    try:
        _ensure_coding_repo()
        result = _persist_document(
            "untitled-local",
            "<html><body><main><section class='section'>"
            "<h1>Updated date</h1></section></main></body></html>",
            "Update the conference date on the cover section",
            default_type="fix",
        )
        assert "error" not in result, result
        assert result["message"].startswith("fix(sections): ")
        assert "Update the conference date" in result["message"]
    finally:
        _reset_tokens(tokens)


def test_replace_write_path_matches_ui_create(monkeypatch):
    """UI create seeds namespaced document.html; replace must edit that file."""
    sc = _bind_in_memory_git(monkeypatch)
    sc.ensure_repo(owner="abi", name="monorepo")
    sc.create_branch(
        repo_id="abi/monorepo",
        name="documents/ws-test/untitled-local",
        from_ref="main",
    )
    seed = (
        "<!DOCTYPE html><html><body><main>"
        '<section id="section-cover" class="section cover">'
        "<h1>Presentation Title</h1>"
        "</section></main></body></html>"
    )
    sc.upsert_file(
        repo_id="abi/monorepo",
        path="documents/ws-test/untitled-local/document.html",
        content=seed,
        message="Seed document",
        branch="documents/ws-test/untitled-local",
    )
    sc.upsert_file(
        repo_id="abi/monorepo",
        path="documents/ws-test/untitled-local/project.json",
        content='{"slug":"untitled-local","workspace_id":"ws-test"}\n',
        message="Seed project",
        branch="documents/ws-test/untitled-local",
    )
    tokens = _sections_context()
    try:
        assert _document_path("untitled-local") == "documents/ws-test/untitled-local/document.html"
        replace = next(
            t for t in documents_tools() if t.name == "replace_in_document"
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
        assert result["path"] == "documents/ws-test/untitled-local/document.html"
        assert result.get("cover_h1_updated") is True
        document = sc.get_file(
            repo_id="abi/monorepo",
            path="documents/ws-test/untitled-local/document.html",
            ref="documents/ws-test/untitled-local",
        )
        assert _cover_h1_text(document.text or "") == "Iran briefing"
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
        "naas_abi.agents.tools.documents_tools._get_source_control",
        lambda: _MissingRepo(),
    )
    monkeypatch.setattr(
        "naas_abi.agents.tools.documents_tools._repo_id", lambda: "abi/monorepo"
    )
    tokens = _sections_context()
    try:
        result = _persist_document(
            "untitled-local",
            "<html><body><main><section><h1>X</h1></section></main></body></html>",
            "Write via Abi",
        )
        assert result.get("error") == _WIPED_DECK_ERROR
        assert result.get("error") != "abi/monorepo"
    finally:
        _reset_tokens(tokens)


def _main_chat_context(*, workspace: str = "ws-test"):
    """Main chat surface: authenticated, but no document open."""
    _forget_active_slugs()
    return [
        agent_workspace_id.set(workspace),
        documents_active_slug.set(None),
        agent_user_id.set("user-1"),
        documents_research_required.set(False),
        documents_research_queries.set(None),
    ]


def test_create_documents_project_from_main_chat_without_an_open_document(monkeypatch):
    """Capability A: Abi can create a document from the ordinary chat surface."""
    sc = _bind_in_memory_git(monkeypatch)
    tokens = _main_chat_context()
    try:
        create = next(t for t in documents_tools() if t.name == "create_documents_project")
        result = create.invoke({"title": "Latest News About AI"})
        assert "error" not in result, result
        slug = result["slug"]
        assert slug == "latest-news-about-ai"
        assert result["branch"] == "documents/ws-test/latest-news-about-ai"
        assert result["path"] == "documents/ws-test/latest-news-about-ai/document.html"
        assert result["title"] == "Latest News About AI"

        document = sc.get_file(
            repo_id="abi/monorepo",
            path=result["path"],
            ref=result["branch"],
        )
        assert document.text and "<section" in document.text.lower()
        project = sc.get_file(
            repo_id="abi/monorepo",
            path="documents/ws-test/latest-news-about-ai/project.json",
            ref=result["branch"],
        )
        assert '"workspace_id": "ws-test"' in (project.text or "")

        # The new document becomes the active one, so a later tool call in the
        # same turn resolves to it without being passed a slug. Asserted
        # through the tool boundary because LangChain runs each tool in an
        # isolated context, where a ContextVar set by create is not visible.
        sections = next(t for t in documents_tools() if t.name == "list_document_sections")
        listed = sections.invoke({})
        assert "error" not in listed, listed
        assert listed["slug"] == slug
    finally:
        _reset_tokens(tokens)


def test_create_documents_project_avoids_colliding_with_an_existing_slug(monkeypatch):
    sc = _bind_in_memory_git(monkeypatch)
    tokens = _main_chat_context()
    try:
        create = next(t for t in documents_tools() if t.name == "create_documents_project")
        first = create.invoke({"title": "AI News"})
        second = create.invoke({"title": "AI News"})
        assert first["slug"] != second["slug"]
        assert second["slug"].startswith("ai-news")
        names = {b.name for b in sc.list_branches(repo_id="abi/monorepo")}
        assert first["branch"] in names
        assert second["branch"] in names
    finally:
        _reset_tokens(tokens)


_FRENCH_BRIEF = "fais des sections sur les matériaux de construction"


def test_create_documents_project_names_the_document_after_a_french_brief(monkeypatch):
    """The model often passes the raw request. Name the document after the topic."""
    sc = _bind_in_memory_git(monkeypatch)
    tokens = _main_chat_context()
    brief = documents_brief.set(_FRENCH_BRIEF)
    try:
        create = next(t for t in documents_tools() if t.name == "create_documents_project")
        result = create.invoke({"title": _FRENCH_BRIEF})
        assert "error" not in result, result
        assert result["title"] == "Matériaux de construction"
        # Slug is derived at creation, so the URL carries the topic too.
        assert result["slug"] == "materiaux-de-construction"
        assert result["branch"] == "documents/ws-test/materiaux-de-construction"

        # The sidebar tree reads project.json; the chat card reads the payload.
        project = sc.get_file(
            repo_id="abi/monorepo",
            path="documents/ws-test/materiaux-de-construction/project.json",
            ref=result["branch"],
        )
        assert '"title": "Matériaux de construction"' in (project.text or "")

        # And the document cover opens named, not as template filler.
        document = sc.get_file(
            repo_id="abi/monorepo",
            path=result["path"],
            ref=result["branch"],
        )
        assert _cover_h1_text(document.text or "") == "Matériaux de construction"
    finally:
        documents_brief.reset(brief)
        _reset_tokens(tokens)


def test_create_documents_project_falls_back_to_the_turn_brief(monkeypatch):
    _bind_in_memory_git(monkeypatch)
    tokens = _main_chat_context()
    brief = documents_brief.set("Make a document about the latest news in AI")
    try:
        create = next(t for t in documents_tools() if t.name == "create_documents_project")
        result = create.invoke({"title": "Untitled document"})
        assert "error" not in result, result
        assert result["title"] == "Latest news in AI"
        assert result["slug"] == "latest-news-in-ai"
    finally:
        documents_brief.reset(brief)
        _reset_tokens(tokens)


def _seed_untitled_document(sc, *, title: str = "Untitled document") -> None:
    sc.ensure_repo(owner="abi", name="monorepo")
    sc.create_branch(
        repo_id="abi/monorepo",
        name="documents/ws-test/untitled-local",
        from_ref="main",
    )
    sc.upsert_file(
        repo_id="abi/monorepo",
        path="documents/ws-test/untitled-local/document.html",
        content=(
            "<!DOCTYPE html><html><body><main>"
            '<section id="section-cover" class="section cover">'
            "<h1>Presentation Title</h1>"
            "</section></main></body></html>"
        ),
        message="Seed document",
        branch="documents/ws-test/untitled-local",
    )
    sc.upsert_file(
        repo_id="abi/monorepo",
        path="documents/ws-test/untitled-local/project.json",
        content=(
            f'{{"slug":"untitled-local","workspace_id":"ws-test","title":"{title}"}}\n'
        ),
        message="Seed project",
        branch="documents/ws-test/untitled-local",
    )


def _stored_title(sc) -> str:
    meta = sc.get_file(
        repo_id="abi/monorepo",
        path="documents/ws-test/untitled-local/project.json",
        ref="documents/ws-test/untitled-local",
    )
    return json.loads(meta.text or "{}").get("title", "")


def test_write_names_a_still_untitled_document_after_the_brief(monkeypatch):
    """A document created by the UI New button starts untitled. Name it on write."""
    sc = _bind_in_memory_git(monkeypatch)
    _seed_untitled_document(sc)
    tokens = _sections_context()
    brief = documents_brief.set(_FRENCH_BRIEF)
    title = documents_active_title.set("Untitled document")
    try:
        result = _persist_document(
            "untitled-local",
            "<html><body><main><section class='section'>"
            "<h1>Matériaux</h1></section></main></body></html>",
            "Write via Abi",
        )
        assert "error" not in result, result
        # Widget payload.
        assert result["title"] == "Matériaux de construction"
        # Sidebar tree record.
        assert _stored_title(sc) == "Matériaux de construction"
    finally:
        documents_active_title.reset(title)
        documents_brief.reset(brief)
        _reset_tokens(tokens)


def test_write_keeps_a_document_title_the_user_already_has(monkeypatch):
    sc = _bind_in_memory_git(monkeypatch)
    _seed_untitled_document(sc, title="Q3 Revenue Review")
    tokens = _sections_context()
    brief = documents_brief.set(_FRENCH_BRIEF)
    try:
        result = _persist_document(
            "untitled-local",
            "<html><body><main><section class='section'>"
            "<h1>Q3</h1></section></main></body></html>",
            "Write via Abi",
        )
        assert "error" not in result, result
        assert result["title"] == "Q3 Revenue Review"
        assert _stored_title(sc) == "Q3 Revenue Review"
    finally:
        documents_brief.reset(brief)
        _reset_tokens(tokens)


def test_write_does_not_rename_a_document_from_an_edit_instruction(monkeypatch):
    """ "Change the cover title to X" names nothing. Leave the document alone."""
    sc = _bind_in_memory_git(monkeypatch)
    _seed_untitled_document(sc)
    tokens = _sections_context()
    brief = documents_brief.set("change the cover title to REFRESH PROBE ALPHA")
    try:
        result = _persist_document(
            "untitled-local",
            "<html><body><main><section class='section'>"
            "<h1>REFRESH PROBE ALPHA</h1></section></main></body></html>",
            "Write via Abi",
        )
        assert "error" not in result, result
        assert _stored_title(sc) == "Untitled document"
    finally:
        documents_brief.reset(brief)
        _reset_tokens(tokens)


def _stored_html(sc) -> str:
    file = sc.get_file(
        repo_id="abi/monorepo",
        path="documents/ws-test/untitled-local/document.html",
        ref="documents/ws-test/untitled-local",
    )
    return file.text or ""


def test_auto_title_names_an_untitled_document_from_the_first_prompt(monkeypatch):
    sc = _bind_in_memory_git(monkeypatch)
    _seed_untitled_document(sc)
    tokens = _sections_context()
    title = documents_active_title.set("Untitled document")
    try:
        named = maybe_auto_title_open_document(
            "Write an executive memo on two audit firms"
        )
        assert named == "Two audit firms"
        assert _stored_title(sc) == "Two audit firms"
        assert "<h1>Two audit firms</h1>" in _stored_html(sc)
    finally:
        documents_active_title.reset(title)
        _reset_tokens(tokens)


def test_auto_title_keeps_a_custom_document_name(monkeypatch):
    sc = _bind_in_memory_git(monkeypatch)
    _seed_untitled_document(sc, title="Already named")
    tokens = _sections_context()
    try:
        assert maybe_auto_title_open_document("Write an executive memo on two firms") is None
        assert _stored_title(sc) == "Already named"
    finally:
        _reset_tokens(tokens)


def test_rename_document_updates_sidebar_name_and_cover(monkeypatch):
    """Rename this document updates project.json and the visible heading."""
    sc = _bind_in_memory_git(monkeypatch)
    _seed_untitled_document(sc)
    tokens = _sections_context()
    try:
        rename = next(t for t in documents_tools() if t.name == "rename_document")
        result = rename.invoke({"title": "Forvis Mazars Story"})
        assert "error" not in result, result
        assert result["title"] == "Forvis Mazars Story"
        assert result["project_renamed"] is True
        assert result["slug_changed"] is False
        assert result["slug"] == "untitled-local"
        assert _stored_title(sc) == "Forvis Mazars Story"
        html = _stored_html(sc)
        assert "<h1>Forvis Mazars Story</h1>" in html
    finally:
        _reset_tokens(tokens)


def test_update_title_leaves_the_sidebar_folder(monkeypatch):
    """Change the heading updates HTML only."""
    sc = _bind_in_memory_git(monkeypatch)
    _seed_untitled_document(sc)
    tokens = _sections_context()
    try:
        update = next(t for t in documents_tools() if t.name == "update_title")
        result = update.invoke({"title": "Cover only"})
        assert "error" not in result, result
        assert result["project_renamed"] is False
        assert _stored_title(sc) == "Untitled document"
        assert "<h1>Cover only</h1>" in _stored_html(sc)
    finally:
        _reset_tokens(tokens)


def test_apply_commands_rename_document_updates_project(monkeypatch):
    sc = _bind_in_memory_git(monkeypatch)
    _seed_untitled_document(sc)
    tokens = _sections_context()
    try:
        apply = next(t for t in documents_tools() if t.name == "apply_document_commands")
        result = apply.invoke(
            {
                "requests_json": json.dumps(
                    [{"type": "rename_document", "title": "Forvis Mazars Story"}]
                )
            }
        )
        assert "error" not in result, result
        assert result.get("project_renamed") is True
        assert _stored_title(sc) == "Forvis Mazars Story"
        assert "<h1>Forvis Mazars Story</h1>" in _stored_html(sc)
    finally:
        _reset_tokens(tokens)


def test_create_documents_project_rejects_an_empty_title(monkeypatch):
    _bind_in_memory_git(monkeypatch)
    tokens = _main_chat_context()
    try:
        create = next(t for t in documents_tools() if t.name == "create_documents_project")
        assert "error" in create.invoke({"title": "   "})
    finally:
        _reset_tokens(tokens)


def test_parse_section_writes_accepts_json_array():
    parsed = _parse_section_writes(
        '[{"index": 0, "html": "<section>A</section>"}, '
        '{"section_id": "section-agenda", "html": "<section id=\\"section-agenda\\">B</section>"}]'
    )
    assert isinstance(parsed, list)
    assert parsed[0]["index"] == 0
    assert parsed[1]["section_id"] == "section-agenda"


def test_apply_section_writes_replaces_two_sections_in_one_pass():
    applied = _apply_section_writes(
        _SAMPLE,
        [
            {
                "index": 0,
                "section_id": None,
                "html": '<section id="section-cover" class="section cover"><h1>Iran now</h1></section>',
            },
            {
                "index": 1,
                "section_id": None,
                "html": '<section id="section-agenda" class="section"><h1>What changed</h1></section>',
            },
        ],
    )
    assert not isinstance(applied, dict)
    html, written = applied
    assert written == [0, 1]
    assert "Iran now" in html
    assert "What changed" in html
    assert "Presentation Title" not in html
    assert "<!-- gap -->" in html or "<main" in html


def test_write_document_sections_persists_once(monkeypatch):
    sc = _seed_in_memory_document(_bind_in_memory_git(monkeypatch), _SAMPLE)
    tokens = _sections_context()
    try:
        write = next(t for t in documents_tools() if t.name == "write_document_sections")
        result = write.invoke(
            {
                "sections": json.dumps(
                    [
                        {
                            "index": 0,
                            "html": (
                                '<section id="section-cover" class="section cover">'
                                "<h1>Iran briefing</h1></section>"
                            ),
                        },
                        {
                            "index": 1,
                            "html": (
                                '<section id="section-agenda" class="section">'
                                "<h1>Actors</h1></section>"
                            ),
                        },
                    ]
                )
            }
        )
        assert "error" not in result, result
        assert result["sections_written"] == 2
        assert result["section_indexes"] == [0, 1]
        document = sc.get_file(
            repo_id="abi/monorepo",
            path="documents/ws-test/untitled-local/document.html",
            ref="documents/ws-test/untitled-local",
        )
        assert "Iran briefing" in (document.text or "")
        assert "Actors" in (document.text or "")
    finally:
        _reset_tokens(tokens)


def test_join_sections_round_trips_split():
    prefix, sections, suffix = _split_sections(_SAMPLE)
    assert _join_sections(prefix, sections, suffix) == _SAMPLE


def test_insert_section_appends_and_clones_content_layout():
    result = _insert_section_html(_SAMPLE, after_index=-1, layout="content", title="Risks")
    assert result["ok"] is True
    assert result["section_count"] == 3
    assert result["section_index"] == 2
    assert "html" in result
    assert "Risks" in result["html"]
    assert "HEAVYASSETDATA" in result["html"]
    prefix, sections, suffix = _split_sections(result["html"])
    assert len(sections) == 3
    assert 'id="section-001"' in sections[2]
    assert _join_sections(prefix, sections, suffix) == result["html"]


def test_insert_section_after_current_uses_catalog_when_layout_missing():
    result = _insert_section_html(_SAMPLE, after_index=0, layout="section-divider", title="Part two")
    assert result["ok"] is True
    assert result["section_index"] == 1
    assert result["section_count"] == 3
    assert "Part two" in result["html"]
    assert 'data-layout="section-divider"' in result["html"]


def test_insert_section_rejects_unknown_layout():
    result = _insert_section_html(_SAMPLE, layout="hero-grid")
    assert result["error"].startswith("Unknown layout")
    assert "html" not in result


def test_insert_section_page_break_layout_uses_catalog_marker():
    result = _insert_section_html(_SAMPLE, after_index=-1, layout="page-break", title="After")
    assert result["ok"] is True
    assert 'data-nexus-page-break' in result["html"]
    assert "After" in result["html"]


def test_delete_section_refuses_last():
    one = (
        "<!DOCTYPE html><html><body><main>"
        '<section class="section"><h1>Only</h1></section>'
        "</main></body></html>"
    )
    result = _delete_section_html(one, 0)
    assert result["error"] == "Cannot delete the last section."
    gone = _delete_section_html(_SAMPLE, 1)
    assert gone["ok"] is True
    assert gone["section_count"] == 1
    assert gone["section_index"] == 0
    assert "section-agenda" not in gone["html"]


def test_duplicate_section_keeps_title_and_new_id():
    result = _duplicate_section_html(_SAMPLE, 0)
    assert result["ok"] is True
    assert result["section_count"] == 3
    assert result["section_index"] == 1
    assert result["html"].count("Presentation Title") >= 2
    ids = [sid for sid in result["ids"] if sid]
    assert len(ids) == len(set(ids))


def test_reorder_sections_from_to_and_order_list():
    moved = _reorder_sections_html(_SAMPLE, from_index=0, to_index=1)
    assert moved["ok"] is True
    assert moved["section_index"] == 1
    _prefix, sections, _suffix = _split_sections(moved["html"])
    assert 'id="section-agenda"' in sections[0]
    assert 'id="section-cover"' in sections[1]
    permuted = _reorder_sections_html(moved["html"], order=[1, 0])
    assert permuted["ok"] is True
    _p, restored, _s = _split_sections(permuted["html"])
    assert 'id="section-cover"' in restored[0]
    assert 'id="section-agenda"' in restored[1]


def test_structure_tools_persist_without_returning_html(monkeypatch):
    sc = _seed_in_memory_document(_bind_in_memory_git(monkeypatch), _SAMPLE)
    tokens = _sections_context()
    try:
        tools = {t.name: t for t in documents_tools()}
        inserted = tools["insert_section"].invoke(
            {"after_index": 0, "layout": "content", "title": "Risks"}
        )
        assert "error" not in inserted, inserted
        assert inserted["ok"] is True
        assert inserted["section_count"] == 3
        assert inserted["section_index"] == 1
        assert "html" not in inserted
        assert "<section" not in json.dumps(inserted)
        duplicated = tools["duplicate_section"].invoke({"index": 0})
        assert duplicated["ok"] is True
        assert duplicated["section_count"] == 4
        assert "html" not in duplicated
        reordered = tools["reorder_sections"].invoke({"from_index": 0, "to_index": 1})
        assert reordered["ok"] is True
        assert "html" not in reordered
        deleted = tools["delete_section"].invoke({"index": 3})
        assert deleted["ok"] is True
        assert deleted["section_count"] == 3
        assert tools["delete_section"].invoke({"index": 0})["section_count"] == 2
        assert tools["delete_section"].invoke({"index": 0})["section_count"] == 1
        last = tools["delete_section"].invoke({"index": 0})
        assert last["error"] == "Cannot delete the last section."
        document = sc.get_file(
            repo_id="abi/monorepo",
            path="documents/ws-test/untitled-local/document.html",
            ref="documents/ws-test/untitled-local",
        )
        assert "Risks" in (document.text or "")
    finally:
        _reset_tokens(tokens)


def test_documents_tools_include_command_api():
    names = {t.name for t in documents_tools()}
    assert COMMAND_TOOL_NAMES <= names
    assert LEFTOVER_SECTION_TOOL_NAMES <= names


def test_documents_agent_tools_hide_leftover_section_crud_when_commands_exist():
    """A write-report turn cannot call list_document_sections at all."""
    catalog = {t.name for t in documents_tools()}
    bound = {t.name for t in documents_agent_tools()}
    assert "apply_document_commands" in catalog
    assert LEFTOVER_SECTION_TOOL_NAMES.isdisjoint(bound)
    assert COMMAND_TOOL_NAMES <= bound
    assert "list_document_sections" not in bound


def test_apply_document_commands_persists_without_returning_html(monkeypatch):
    sc = _seed_in_memory_document(_bind_in_memory_git(monkeypatch), _SAMPLE)
    tokens = _sections_context()
    try:
        apply = next(
            t for t in documents_tools() if t.name == "apply_document_commands"
        )
        result = apply.invoke(
            {
                "requests_json": json.dumps(
                    [
                        {
                            "type": "insert_heading",
                            "title": "Scope",
                            "level": 2,
                            "after_heading": -1,
                        },
                        {
                            "type": "insert_paragraph",
                            "text": "Audit AI covers fieldwork planning.",
                            "after_heading": -1,
                        },
                    ]
                )
            }
        )
        assert "error" not in result, result
        assert result["ok"] is True
        assert result["heading_count"] >= 2
        assert "html" not in result
        assert "<section" not in json.dumps(result)
        document = sc.get_file(
            repo_id="abi/monorepo",
            path="documents/ws-test/untitled-local/document.html",
            ref="documents/ws-test/untitled-local",
        )
        assert "Scope" in (document.text or "")
        assert "Audit AI covers fieldwork planning." in (document.text or "")
    finally:
        _reset_tokens(tokens)


def test_insert_heading_respects_research_gate(monkeypatch):
    _seed_in_memory_document(_bind_in_memory_git(monkeypatch), _SAMPLE)
    tokens = _sections_context()
    tokens.append(documents_research_required.set(True))
    tokens.append(documents_research_queries.set([]))
    try:
        insert = next(t for t in documents_tools() if t.name == "insert_heading")
        blocked = insert.invoke({"title": "Findings"})
        assert blocked is not None
        assert "web_search" in blocked["error"]
    finally:
        documents_research_required.reset(tokens[-2])
        documents_research_queries.reset(tokens[-1])
        _reset_tokens(tokens[:-2])


_CATALOG = [
    {"id": "firm/portrait-a4-v1", "name": "Portrait A4"},
    {"id": "firm/portrait-a4-blank-v1", "name": "Portrait A4 blank"},
    {"id": "firm/landscape-a4-v1", "name": "Landscape A4"},
]


def test_resolve_documents_template_id_prefers_named_portrait():
    assert (
        resolve_documents_template_id("Portrait A4", _CATALOG)
        == "firm/portrait-a4-v1"
    )
    assert (
        resolve_documents_template_id("portrait a4 theme", _CATALOG)
        == "firm/portrait-a4-v1"
    )
    assert (
        resolve_documents_template_id("Portrait A4 blank", _CATALOG)
        == "firm/portrait-a4-blank-v1"
    )
    missed = resolve_documents_template_id("", _CATALOG)
    assert isinstance(missed, dict)
    assert "templates" in missed


def test_apply_documents_template_skips_research_gate(monkeypatch):
    seed = "<html><body><h1>Portrait A4</h1><p>Introduction</p></body></html>"
    sc = _seed_in_memory_document(_bind_in_memory_git(monkeypatch), _SAMPLE)
    monkeypatch.setattr(
        "naas_abi.agents.tools.documents_tools._catalog_template_rows",
        lambda: _CATALOG,
    )
    monkeypatch.setattr(
        "naas_abi.agents.tools.documents_tools._load_catalog_seed_html",
        lambda template_id: seed,
    )
    tokens = _sections_context()
    tokens.append(documents_research_required.set(True))
    tokens.append(documents_research_queries.set([]))
    try:
        apply = next(
            t for t in documents_tools() if t.name == "apply_documents_template"
        )
        result = apply.invoke({"template_id": "Portrait A4"})
        assert "error" not in result, result
        assert result["ok"] is True
        assert result["template_id"] == "firm/portrait-a4-v1"
        document = sc.get_file(
            repo_id="abi/monorepo",
            path="documents/ws-test/untitled-local/document.html",
            ref="documents/ws-test/untitled-local",
        )
        assert "Portrait A4" in (document.text or "")
        assert "Presentation Title" not in (document.text or "")
    finally:
        documents_research_required.reset(tokens[-2])
        documents_research_queries.reset(tokens[-1])
        _reset_tokens(tokens[:-2])


def test_list_documents_projects_when_open_hides_other_docs(monkeypatch):
    sc = _bind_in_memory_git(monkeypatch)
    _seed_in_memory_document(sc, _SAMPLE, slug="untitled-local")
    _seed_in_memory_document(sc, "<html></html>", slug="untitled-other")
    tokens = _sections_context()
    try:
        listing = next(
            t for t in documents_tools() if t.name == "list_documents_projects"
        )
        result = listing.invoke({})
        assert "error" not in result, result
        slugs = {row["slug"] for row in result["projects"]}
        assert slugs == {"untitled-local"}
        assert "apply_documents_template" in result["note"]
    finally:
        _reset_tokens(tokens)
