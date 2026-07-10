"""Shell layout conventions for ABI Desktop web UI."""

from __future__ import annotations

import re
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent

DEFAULT_SECTION = "chat"
SECTION_HASH_ALIASES = {"ide": "code", "events": "table"}
VALID_SECTIONS = frozenset({"chat", "code", "graph", "table", "files", "settings"})
SETTINGS_TABS = frozenset({"general", "servers", "models"})
DEFAULT_TABLE_NAME = "processes"
TABLE_HASH_ALIASES = {"events": "processes", "sqlite": "processes"}


def parse_section_hash(raw_hash: str) -> tuple[str, str | None, str | None, bool]:
    """Mirror of parseSectionHash() in app.js for routing contract tests."""
    hash_value = (raw_hash or "").removeprefix("#").strip().lower()
    if not hash_value:
        return DEFAULT_SECTION, None, None, False

    parts = [part for part in hash_value.split("/") if part]
    slug = SECTION_HASH_ALIASES.get(parts[0], parts[0])
    if slug not in VALID_SECTIONS:
        return DEFAULT_SECTION, None, None, False

    settings_tab: str | None = None
    if slug == "settings" and len(parts) > 1:
        settings_tab = parts[1]
        if settings_tab not in SETTINGS_TABS:
            settings_tab = "general"

    table_name: str | None = None
    if slug == "table" and len(parts) > 1:
        table_name = TABLE_HASH_ALIASES.get(parts[1], parts[1])

    return slug, settings_tab, table_name, True


def _read(name: str) -> str:
    return (WEB_DIR / name).read_text(encoding="utf-8")


def test_rail_logo_workspace_switcher_in_top() -> None:
    html = _read("index.html")
    assert 'id="workspace-switcher"' in html
    assert 'id="workspace-logo"' in html
    assert 'id="workspace-name"' not in html
    assert "workspace-switcher-label" not in html
    assert "workspace-chevron" not in html
    rail_top_start = html.index('class="rail-top"')
    rail_nav_start = html.index('class="rail-nav"')
    rail_bottom_start = html.index('class="rail-bottom"')
    workspace_idx = html.index('id="workspace-switcher"')
    settings_idx = html.index('data-section="settings"')
    assert rail_top_start < workspace_idx < rail_nav_start
    assert rail_nav_start < settings_idx
    assert workspace_idx < rail_bottom_start
    assert 'aria-hidden="true"' not in html[html.index('class="rail-top"'):rail_nav_start]


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
    assert ".rail-top" in css
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
    assert "loadProcessEventsTable" in js
    assert "openProcessEventInGraph" in js
    assert "/api/tables/processes" in js
    assert "graph-subclass-select" in js
    assert "/api/graph/subclasses" in js
    css = _read("style.css")
    assert ".events-table" in css
    assert ".graph-events-panel" not in css


def test_table_section_flat_sqlite_table_list() -> None:
    html = _read("index.html")
    assert 'id="view-table"' in html
    assert 'id="table-data-host"' in html
    assert 'id="table-nav-list"' in html
    assert 'id="events-detail-panel"' in html
    assert 'data-section="table"' in html
    assert 'data-icon="table-2"' in html
    assert 'data-table-tab=' not in html
    assert 'id="table-tab-events"' not in html
    assert 'id="sqlite-table-picker"' not in html
    js = _read("app.js")
    assert 'table: { title: "Table", panel: "table-panel" }' in js
    assert '"table-2"' in js
    assert "selectTable" in js
    assert "loadTableSection" in js
    assert "renderTableNav" in js
    assert "isProcessEventsTable" in js
    assert 'DEFAULT_TABLE_NAME = "processes"' in js
    assert "/api/tables" in js
    css = _read("style.css")
    assert "#view-table" in css
    assert ".table-data-host" in css
    assert ".table-nav-list" in css


def test_files_section_full_panel_explorer() -> None:
    html = _read("index.html")
    assert 'id="view-files"' in html
    assert 'id="files-file-tree"' in html
    assert 'id="files-preview-pane"' in html
    assert 'data-section="files"' in html
    assert 'data-icon="folder-open"' in html
    assert 'id="file-tree"' not in html
    js = _read("app.js")
    assert 'files: { title: "Files", panel: "files-panel" }' in js
    assert "files-file-tree" in js
    assert "openFileInCode" in js
    assert "renderFilesPreview" in js
    css = _read("style.css")
    assert "#view-files" in css
    assert ".files-explorer" in css


def test_code_panel_has_no_file_tree() -> None:
    html = _read("index.html")
    code_panel_start = html.index('id="code-panel"')
    code_panel_end = html.index('id="graph-panel"')
    code_panel = html[code_panel_start:code_panel_end]
    assert "file-tree" not in code_panel
    assert "Explorer" not in code_panel


def test_section_hash_parse_defaults_and_aliases() -> None:
    assert parse_section_hash("") == ("chat", None, None, False)
    assert parse_section_hash("#chat") == ("chat", None, None, True)
    assert parse_section_hash("#code") == ("code", None, None, True)
    assert parse_section_hash("#ide") == ("code", None, None, True)
    assert parse_section_hash("#graph") == ("graph", None, None, True)
    assert parse_section_hash("#table") == ("table", None, None, True)
    assert parse_section_hash("#table/processes") == ("table", None, "processes", True)
    assert parse_section_hash("#table/chats") == ("table", None, "chats", True)
    assert parse_section_hash("#table/events") == ("table", None, "processes", True)
    assert parse_section_hash("#table/sqlite") == ("table", None, "processes", True)
    assert parse_section_hash("#events") == ("table", None, None, True)
    assert parse_section_hash("#files") == ("files", None, None, True)
    assert parse_section_hash("#settings") == ("settings", None, None, True)
    assert parse_section_hash("#settings/servers") == ("settings", "servers", None, True)
    assert parse_section_hash("#unknown") == ("chat", None, None, False)


def test_rail_sections_match_hash_slugs() -> None:
    html = _read("index.html")
    sections = re.findall(r'data-section="([^"]+)"', html)
    assert sections == ["chat", "code", "graph", "table", "files", "settings"]
    for section in sections:
        assert parse_section_hash(f"#{section}")[0] == section


def test_app_js_has_section_hash_routing() -> None:
    js = _read("app.js")
    assert "function parseSectionHash" in js
    assert "function setSectionHash" in js
    assert "function applySectionHash" in js
    assert 'addEventListener("hashchange", onSectionHashChange)' in js
    assert 'addEventListener("popstate", onSectionHashChange)' in js
    assert 'SECTION_HASH_ALIASES = { ide: "code", events: "table" }' in js
    assert "DEFAULT_TABLE_NAME" in js
    assert "TABLE_HASH_ALIASES" in js
