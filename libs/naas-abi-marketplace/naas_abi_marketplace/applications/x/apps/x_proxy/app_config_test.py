"""Unit tests for `config.yaml` parsing and the TypeScript it compiles into.

Two concerns: the config the app ships with must stay loadable and consistent
with the routes on disk, and a malformed edit must fail here rather than in a
published export.
"""

from pathlib import Path

import pytest
import yaml
from naas_abi_marketplace.applications.x.apps.x_proxy.app_config import (
    APP_DIR,
    CONFIG_PATH,
    GENERATED_TS,
    ConfigError,
    emit_ts,
    load_config,
    parse_config,
)

MINIMAL = {
    "app": {"name": "X Proxy", "title": "{app} - {section}"},
    "default_page": "count",
    "favorites": {"max_users": 60, "max_folders": 12, "max_folder_name": 32},
    "feed": {"batch": 10},
    "sections": [
        {
            "key": "posts",
            "label": "Posts",
            "icon": "posts",
            "pages": [
                {"key": "count", "label": "Count", "path": "/posts/count/"},
            ],
        }
    ],
}


def _with(**overrides):
    """MINIMAL, deep-copied, with top-level keys replaced."""
    raw = yaml.safe_load(yaml.safe_dump(MINIMAL))
    raw.update(overrides)
    return raw


# --------------------------------------------------------------------------
# The config the app ships with
# --------------------------------------------------------------------------


def test_shipped_config_loads():
    config = load_config()
    assert config.name == "X Proxy"
    assert {section.key for section in config.sections} == {
        "posts",
        "users",
        "parameters",
    }


def test_shipped_paths_are_real_exported_routes():
    # Every configured path must be a directory under `web/src/app/`, or a link
    # in the app points at a route Next never exports.
    app_router = APP_DIR / "web" / "src" / "app"
    for page in load_config().pages:
        route = app_router / page.path.strip("/")
        assert (route / "page.tsx").is_file(), f"{page.key}: no route at {page.path}"


def test_shipped_config_titles_read_as_app_dash_section():
    config = load_config()
    assert config.title_for("users") == "X Proxy - Users"
    assert config.title_for("posts") == "X Proxy - Posts"


def test_generated_module_is_in_sync_with_config():
    # The web app imports the generated file, so a stale one silently publishes
    # yesterday's navigation. `--check` runs exactly this in CI.
    assert GENERATED_TS.read_text(encoding="utf-8") == emit_ts(load_config())


def test_section_of_and_page_lookups():
    config = load_config()
    assert config.section_of("search").key == "posts"
    assert config.page("users").path == "/users/search"
    with pytest.raises(KeyError):
        config.page("nope")


# --------------------------------------------------------------------------
# Defaults and validation
# --------------------------------------------------------------------------


def test_flags_default_to_a_visible_section_with_a_top_bar():
    section = parse_config(MINIMAL).sections[0]
    assert (section.visible, section.top_nav, section.place) == (True, True, "main")
    # Favorites and filters are opt-in: most pages want neither.
    assert section.favorites is False
    assert section.pages[0].filters is False
    assert section.pages[0].visible is True


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (_with(default_page="ghost"), "unknown page"),
        (_with(sections=[]), "non-empty list"),
        (_with(app={"name": "X", "title": "{nope}"}), "app.title"),
        (
            _with(favorites={"max_users": 0, "max_folders": 1, "max_folder_name": 1}),
            "positive integer",
        ),
    ],
)
def test_rejects_broken_config(raw, message):
    with pytest.raises(ConfigError, match=message):
        parse_config(raw)


def test_rejects_a_hidden_landing_page():
    raw = _with()
    raw["sections"][0]["pages"][0]["visible"] = False
    with pytest.raises(ConfigError, match="is hidden"):
        parse_config(raw)


def test_rejects_duplicate_page_keys():
    raw = _with()
    raw["sections"][0]["pages"].append(
        {"key": "count", "label": "Again", "path": "/again/"}
    )
    with pytest.raises(ConfigError, match="duplicate page key"):
        parse_config(raw)


def test_rejects_unknown_icon_and_place():
    raw = _with()
    raw["sections"][0]["icon"] = "rocket"
    with pytest.raises(ConfigError, match="unknown icon"):
        parse_config(raw)
    raw = _with()
    raw["sections"][0]["place"] = "middle"
    with pytest.raises(ConfigError, match="place"):
        parse_config(raw)


def test_rejects_a_relative_path():
    raw = _with()
    raw["sections"][0]["pages"][0]["path"] = "posts/count/"
    with pytest.raises(ConfigError, match="must start with"):
        parse_config(raw)


def test_rejects_a_non_boolean_flag():
    raw = _with()
    raw["sections"][0]["top_nav"] = "no"
    with pytest.raises(ConfigError, match="true or false"):
        parse_config(raw)


# --------------------------------------------------------------------------
# Code generation
# --------------------------------------------------------------------------


def test_feed_batch_reaches_the_module():
    assert "batch: 10," in emit_ts(load_config())
    raw = _with(feed={"batch": 0})
    with pytest.raises(ConfigError, match="positive integer"):
        parse_config(raw)


def test_posts_tabs_lead_with_search():
    # The tab strip follows config order, so this is the config's assertion.
    pages = [page.key for page in load_config().section_of("search").pages]
    assert pages == ["search", "count"]


def test_emitted_module_carries_the_union_types_and_the_data():
    ts = emit_ts(parse_config(MINIMAL))
    assert 'export type PageKey = "count";' in ts
    assert 'export type SectionKey = "posts";' in ts
    assert 'export const DEFAULT_PAGE: PageKey = "count";' in ts
    assert '"topNav": true' in ts
    assert "maxUsers: 60," in ts


def test_emitted_module_is_stable():
    # Regeneration must not churn the file, or every build is a diff.
    config = load_config()
    assert emit_ts(config) == emit_ts(config)


def test_hidden_page_still_reaches_the_module():
    # Visibility is chrome, not routing: the page keeps its key and its path so
    # a deep link still opens it.
    raw = _with()
    raw["sections"][0]["pages"].append(
        {"key": "search", "label": "Search", "path": "/s/", "visible": False}
    )
    ts = emit_ts(parse_config(raw))
    assert '"key": "search"' in ts
    assert '"visible": false' in ts
    assert 'export type PageKey = "count" | "search";' in ts


def test_config_path_points_at_the_shipped_file():
    assert CONFIG_PATH == Path(APP_DIR) / "config.yaml"
    assert CONFIG_PATH.is_file()
