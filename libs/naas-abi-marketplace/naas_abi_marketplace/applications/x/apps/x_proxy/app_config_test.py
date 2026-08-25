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
    "results": {"per_page": 100},
    "charts": {"top_authors_bars": 20, "top_locations_bars": 10},
    "feed": {
        "batch": 10,
        "tabs": {"all": "All", "matched": "Matched Query", "referenced": "Referenced"},
    },
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


def test_landing_page_is_the_first_visible_tab_of_the_first_section():
    # `/` should open where the app's own navigation would take you.
    config = load_config()
    first = next(s for s in config.sections if s.visible)
    assert config.default_page == next(p.key for p in first.pages if p.visible)
    assert config.default_page == "tweets"


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
    assert section.favorites == "none"
    assert section.pages[0].filters is False
    assert section.pages[0].search_box is False
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


def test_feed_batch_and_tabs_reach_the_module():
    ts = emit_ts(load_config())
    assert "batch: 10," in ts
    # The keys are the data's split; only the words are configurable.
    assert '{"key": "matched", "label": "Matched Query"}' in ts
    raw = _with()
    raw["feed"]["tabs"].pop("referenced")
    with pytest.raises(ConfigError, match="feed.tabs"):
        parse_config(raw)
    raw = _with()
    raw["feed"]["batch"] = 0
    with pytest.raises(ConfigError, match="positive integer"):
        parse_config(raw)


def test_the_two_favorites_bars_never_mix():
    config = load_config()
    # Posts carries no bar at section level, but Search Tweets and the post
    # page carry the posts bar - and the authors bar belongs to Users alone.
    assert config.section_of("post").favorites == "none"
    assert config.favorites_on("post") == "posts"
    assert config.favorites_on("tweets") == "posts"
    assert config.favorites_on("search") == "none"
    assert config.favorites_on("users") == "users"
    # Users inherits: the value is the section's.
    assert config.page("users").favorites is None


def test_a_hidden_page_can_light_another_tab():
    config = load_config()
    # The post page is not a tab; it keeps Search Tweets lit, the way an
    # author's page keeps Search Users lit.
    assert config.tab_for("post") == "tweets"
    assert config.tab_for("users") == "users"
    raw = _with()
    raw["sections"][0]["pages"][0]["tab"] = "ghost"
    with pytest.raises(ConfigError, match="unknown page"):
        parse_config(raw)


def test_charts_are_publish_side_only():
    # The bar counts shape what the publisher writes; the browser never reads
    # them, so they must not reach the generated module.
    config = load_config()
    assert config.charts.top_authors_bars == 20
    assert "top_authors_bars" not in emit_ts(config)
    assert "topAuthorsBars" not in emit_ts(config)


def test_posts_tabs_lead_with_search_tweets():
    # The tab strip follows config order, so this is the config's assertion.
    pages = [page.key for page in load_config().section_of("search").pages]
    assert pages == ["tweets", "search", "post", "count"]
    # `post` is a destination, not a tab: it keeps its route and leaves the strip.
    assert [
        page.key for page in load_config().section_of("search").pages if page.visible
    ] == [
        "tweets",
        "search",
        "count",
    ]


def test_only_the_search_pages_carry_a_search_box():
    config = load_config()
    boxed = {page.key for page in config.pages if page.search_box}
    assert boxed == {"users", "tweets"}
    # Neither search page is scoped by the Scenario / Query filters: both list a
    # whole published dataset, and page it the same way.
    assert {page.key for page in config.pages if page.filters} == {"search", "count"}
    assert "perPage: 100," in emit_ts(config)


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
