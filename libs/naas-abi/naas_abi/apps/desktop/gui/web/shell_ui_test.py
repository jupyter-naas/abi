"""Shell layout conventions for ABI Desktop web UI."""

from __future__ import annotations

import re
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent

DEFAULT_SECTION = "chat"
SECTION_HASH_ALIASES = {"ide": "code"}
VALID_SECTIONS = frozenset({"chat", "code", "graph", "events", "settings"})
SETTINGS_TABS = frozenset({"general", "servers", "models"})


def parse_section_hash(raw_hash: str) -> tuple[str, str | None, bool]:
    """Mirror of parseSectionHash() in app.js for routing contract tests."""
    hash_value = (raw_hash or "").removeprefix("#").strip().lower()
    if not hash_value:
        return DEFAULT_SECTION, None, False

    parts = [part for part in hash_value.split("/") if part]
    slug = SECTION_HASH_ALIASES.get(parts[0], parts[0])
    if slug not in VALID_SECTIONS:
        return DEFAULT_SECTION, None, False

    settings_tab: str | None = None
    if slug == "settings" and len(parts) > 1:
        settings_tab = parts[1]
        if settings_tab not in SETTINGS_TABS:
            settings_tab = "general"

    return slug, settings_tab, True


def _read(name: str) -> str:
    return (WEB_DIR / name).read_text(encoding="utf-8")


def test_rail_logo_workspace_switcher_in_bottom() -> None:
    html = _read("index.html")
    assert 'id="workspace-switcher"' in html
    assert 'id="workspace-logo"' in html
    assert 'id="workspace-name"' not in html
    assert "workspace-switcher-label" not in html
    assert "workspace-chevron" not in html
    rail_bottom_start = html.index('class="rail-bottom"')
    rail_nav_start = html.index('class="rail-nav"')
    workspace_idx = html.index('id="workspace-switcher"')
    settings_idx = html.index('data-section="settings"')
    assert rail_nav_start < workspace_idx
    assert workspace_idx < settings_idx
    assert html.index('class="rail-bottom"', rail_bottom_start) == rail_bottom_start
    assert workspace_idx > rail_bottom_start
    assert 'class="rail-top"' in html
    rail_top_end = html.index("</div>", html.index('class="rail-top"'))
    assert html.index('id="workspace-switcher"') > rail_top_end


def test_status_bar_shows_workspace_name() -> None:
    html = _read("index.html")
    assert 'id="status-workspace"' in html
    assert 'id="status-git"' in html
    assert html.index('id="status-workspace"') < html.index('id="status-git"')


def test_workspace_menu_nexus_style() -> None:
    html = _read("index.html")
    assert 'id="workspace-menu"' in html
    assert 'class="workspace-menu glass-card' in html
    assert "workspace-menu-heading" in html
    assert "Workspaces" in html
    assert 'id="workspace-menu-open-folder"' in html
    assert "workspace-menu-path" not in html


def test_app_shell_status_bar_layout() -> None:
    html = _read("index.html")
    assert 'id="app-shell"' in html
    assert 'id="status-bar"' in html
    assert html.index('id="app-shell"') < html.index('id="status-bar"')


def test_workspace_switcher_js_uses_status_not_rail_name() -> None:
    js = _read("app.js")
    assert "status-workspace" in js
    assert "workspace-name" not in js
    assert "workspace-menu-path" not in js
    assert "rect.right + 8" in js


def test_workspace_switcher_css_logo_button() -> None:
    css = _read("style.css")
    assert ".glass-card" in css
    assert ".workspace-switcher" in css
    assert ".rail-bottom .workspace-switcher" in css
    assert "workspace-switcher-label" not in css
    assert "#workspace-name" not in css


def test_graph_overview_has_bfo_bucket_filters() -> None:
    html = _read("index.html")
    assert 'id="graph-bucket-filters"' in html
    assert 'id="graph-view-toggle"' in html
    assert 'data-graph-view="abox"' in html
    assert 'id="graph-events-panel"' not in html
    assert 'id="graph-events-table-host"' not in html
    assert 'id="graph-bucket-legend"' not in html
    assert 'id="graph-layer-filters"' not in html
    js = _read("app.js")
    assert "DEFAULT_BFO_BUCKETS" in js
    assert "renderGraphBucketFilters" in js
    assert "switchGraphView" in js
    assert "renderGraphBfoAspectsTable" in js
    assert "renderEventsTable" in js
    assert "loadEvents" in js
    assert "openProcessEventInGraph" in js
    assert "/api/processes" in js
    assert "graph-subclass-select" in js
    assert "/api/graph/subclasses" in js
    css = _read("style.css")
    assert ".events-table" in css
    assert ".graph-events-panel" not in css


def test_events_section_full_panel() -> None:
    html = _read("index.html")
    assert 'id="view-events"' in html
    assert 'id="events-table-host"' in html
    assert 'id="events-detail-panel"' in html
    assert 'data-section="events"' in html
    assert 'data-icon="scroll-text"' in html
    js = _read("app.js")
    assert 'events: { title: "Events", panel: "events-panel" }' in js
    assert '"scroll-text"' in js
    css = _read("style.css")
    assert "#view-events" in css
    assert ".events-table-host" in css


def test_section_hash_parse_defaults_and_aliases() -> None:
    assert parse_section_hash("") == ("chat", None, False)
    assert parse_section_hash("#chat") == ("chat", None, True)
    assert parse_section_hash("#code") == ("code", None, True)
    assert parse_section_hash("#ide") == ("code", None, True)
    assert parse_section_hash("#graph") == ("graph", None, True)
    assert parse_section_hash("#events") == ("events", None, True)
    assert parse_section_hash("#settings") == ("settings", None, True)
    assert parse_section_hash("#settings/servers") == ("settings", "servers", True)
    assert parse_section_hash("#unknown") == ("chat", None, False)


def test_rail_sections_match_hash_slugs() -> None:
    html = _read("index.html")
    sections = re.findall(r'data-section="([^"]+)"', html)
    assert sections == ["chat", "code", "graph", "events", "settings"]
    for section in sections:
        assert parse_section_hash(f"#{section}")[0] == section


def test_app_js_has_section_hash_routing() -> None:
    js = _read("app.js")
    assert "function parseSectionHash" in js
    assert "function setSectionHash" in js
    assert "function applySectionHash" in js
    assert 'addEventListener("hashchange", onSectionHashChange)' in js
    assert 'addEventListener("popstate", onSectionHashChange)' in js
    assert 'SECTION_HASH_ALIASES = { ide: "code" }' in js
