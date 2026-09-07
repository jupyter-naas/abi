"""The app's navigation configuration: `config.yaml` in, typed objects out.

`config.yaml` names the sections, their pages, the order of both, and what is
visible - everything the chrome used to hardcode. The web app is a static
export, so nothing fetches this at runtime: `emit_ts` compiles it into
`web/src/lib/appConfig.generated.ts`, which the components import, and
`pnpm build` / `pnpm dev` regenerate that file first.

Run it directly to regenerate or to verify:

```bash
uv run python -m naas_abi_marketplace.applications.x.apps.x_proxy.app_config --write
uv run python -m naas_abi_marketplace.applications.x.apps.x_proxy.app_config --check
```

Validation is deliberately strict: a typo in a key or an icon is a broken app,
and this is the only place that can catch it before the export is published.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.yaml"
GENERATED_TS = APP_DIR / "web" / "src" / "lib" / "appConfig.generated.ts"

# Rail icons drawn by `Shell.tsx`. A section may only ask for one of these:
# the SVG lives in the component, the choice lives in the config.
ICONS = ("posts", "users", "gear")

Place = Literal["main", "bottom"]
PLACES = ("main", "bottom")

#: Which favorites bar a section or page carries. The two bars never mix: each
#: has its own chips and its own storage.
FAVORITES = ("none", "users", "posts")


class ConfigError(ValueError):
    """`config.yaml` says something the app cannot honour."""


@dataclass(frozen=True)
class PageConfig:
    """One page: a tab in its section's strip, and a real exported route."""

    key: str
    label: str
    path: str
    visible: bool
    #: Whether the Scenario / Query dropdowns show on this page.
    filters: bool
    #: Whether the page has a search box, whose needle lives in ``?q=``.
    search_box: bool
    #: Overrides the section's favorites bar for this page. ``None`` inherits.
    favorites: str | None
    #: Tab to light up while this page is open, when it is not a tab itself.
    tab: str | None


@dataclass(frozen=True)
class SectionConfig:
    """One section: a rail entry, and the pages that tab under the top bar."""

    key: str
    label: str
    icon: str
    visible: bool
    place: str
    #: False hides the "X Proxy - <section>" bar while in this section.
    top_nav: bool
    #: Which favorites bar this section carries - see :data:`FAVORITES`.
    favorites: str
    pages: tuple[PageConfig, ...]


@dataclass(frozen=True)
class FavoritesLimits:
    max_users: int
    max_folders: int
    max_folder_name: int


@dataclass(frozen=True)
class ResultsConfig:
    #: Results per page, shared by both search pages.
    per_page: int


#: The feed's tabs. Keys are the split the data carries, values are the words.
FEED_TABS = ("all", "matched", "referenced")


@dataclass(frozen=True)
class ChartsConfig:
    """Shapes the *publisher* honours, unlike everything else here."""

    top_authors_bars: int
    top_locations_bars: int


@dataclass(frozen=True)
class FeedConfig:
    #: Posts per batch in the author feed - the first page, and each "show more".
    batch: int
    #: Label per tab key, in :data:`FEED_TABS` order.
    tabs: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class AppConfig:
    name: str
    #: Top-bar heading, with `{app}` / `{section}` placeholders.
    title: str
    default_page: str
    favorites: FavoritesLimits
    results: ResultsConfig
    charts: ChartsConfig
    feed: FeedConfig
    sections: tuple[SectionConfig, ...]

    @property
    def pages(self) -> tuple[PageConfig, ...]:
        return tuple(page for section in self.sections for page in section.pages)

    def page(self, key: str) -> PageConfig:
        for page in self.pages:
            if page.key == key:
                return page
        raise KeyError(key)

    def section_of(self, page_key: str) -> SectionConfig:
        for section in self.sections:
            if any(page.key == page_key for page in section.pages):
                return section
        raise KeyError(page_key)

    def favorites_on(self, page_key: str) -> str:
        """Which favorites bar *page_key* carries - its own, else its section's."""
        page = self.page(page_key)
        if page.favorites is not None:
            return page.favorites
        return self.section_of(page_key).favorites

    def tab_for(self, page_key: str) -> str:
        """The tab to light up while *page_key* is open - itself by default."""
        return self.page(page_key).tab or page_key

    def title_for(self, section_key: str) -> str:
        section = next(s for s in self.sections if s.key == section_key)
        return self.title.format(app=self.name, section=section.label)


def _require(mapping: Any, key: str, where: str) -> Any:
    if not isinstance(mapping, dict) or key not in mapping:
        raise ConfigError(f"{where}: missing '{key}'")
    return mapping[key]


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where}: expected a non-empty string, got {value!r}")
    return value


def _flag(mapping: dict, key: str, where: str, default: bool) -> bool:
    value = mapping.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"{where}: '{key}' must be true or false, got {value!r}")
    return value


def _positive_int(mapping: dict, key: str, where: str) -> int:
    value = _require(mapping, key, where)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ConfigError(f"{where}: '{key}' must be a positive integer, got {value!r}")
    return value


def _favorites(mapping: dict, where: str) -> str:
    value = mapping.get("favorites", "none")
    if value not in FAVORITES:
        raise ConfigError(
            f"{where}.favorites: expected one of {FAVORITES}, got {value!r}"
        )
    return value


def _parse_page(raw: Any, where: str) -> PageConfig:
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: expected a mapping, got {raw!r}")
    key = _text(_require(raw, "key", where), f"{where}.key")
    path = _text(_require(raw, "path", where), f"{where}.path")
    if not path.startswith("/"):
        raise ConfigError(f"{where}.path: must start with '/', got {path!r}")
    favorites = raw.get("favorites")
    if favorites is not None and favorites not in FAVORITES:
        raise ConfigError(
            f"{where}.favorites: expected one of {FAVORITES}, got {favorites!r}"
        )
    tab = raw.get("tab")
    if tab is not None and not isinstance(tab, str):
        raise ConfigError(f"{where}.tab: expected a page key, got {tab!r}")
    return PageConfig(
        key=key,
        label=_text(_require(raw, "label", where), f"{where}.label"),
        path=path,
        visible=_flag(raw, "visible", where, True),
        filters=_flag(raw, "filters", where, False),
        search_box=_flag(raw, "search_box", where, False),
        favorites=favorites,
        tab=tab,
    )


def _parse_section(raw: Any, where: str) -> SectionConfig:
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: expected a mapping, got {raw!r}")
    key = _text(_require(raw, "key", where), f"{where}.key")
    icon = _text(_require(raw, "icon", where), f"{where}.icon")
    if icon not in ICONS:
        raise ConfigError(
            f"{where}.icon: unknown icon {icon!r}, expected one of {ICONS}"
        )
    place = _text(raw.get("place", "main"), f"{where}.place")
    if place not in PLACES:
        raise ConfigError(f"{where}.place: expected one of {PLACES}, got {place!r}")
    pages_raw = _require(raw, "pages", where)
    if not isinstance(pages_raw, list) or not pages_raw:
        raise ConfigError(f"{where}.pages: expected a non-empty list")
    pages = tuple(
        _parse_page(page, f"{where}.pages[{i}]") for i, page in enumerate(pages_raw)
    )
    return SectionConfig(
        key=key,
        label=_text(_require(raw, "label", where), f"{where}.label"),
        icon=icon,
        visible=_flag(raw, "visible", where, True),
        place=place,
        top_nav=_flag(raw, "top_nav", where, True),
        favorites=_favorites(raw, where),
        pages=pages,
    )


def parse_config(raw: Any) -> AppConfig:
    """Validate a parsed `config.yaml` into an `AppConfig`."""
    if not isinstance(raw, dict):
        raise ConfigError("config.yaml: expected a mapping at the top level")

    app = _require(raw, "app", "config.yaml")
    title = _text(_require(app, "title", "app"), "app.title")
    try:
        title.format(app="", section="")
    except (KeyError, IndexError) as exc:
        raise ConfigError(
            f"app.title: only {{app}} and {{section}} are available, got {title!r}"
        ) from exc

    sections_raw = _require(raw, "sections", "config.yaml")
    if not isinstance(sections_raw, list) or not sections_raw:
        raise ConfigError("sections: expected a non-empty list")
    sections = tuple(
        _parse_section(section, f"sections[{i}]")
        for i, section in enumerate(sections_raw)
    )

    seen_sections: set[str] = set()
    seen_pages: set[str] = set()
    for section in sections:
        if section.key in seen_sections:
            raise ConfigError(f"sections: duplicate section key {section.key!r}")
        seen_sections.add(section.key)
        for page in section.pages:
            if page.key in seen_pages:
                raise ConfigError(f"sections: duplicate page key {page.key!r}")
            seen_pages.add(page.key)

    for section in sections:
        for page in section.pages:
            if page.tab is not None and page.tab not in seen_pages:
                raise ConfigError(
                    f"sections: page {page.key!r} points its tab at unknown "
                    f"page {page.tab!r}"
                )

    favorites_raw = _require(raw, "favorites", "config.yaml")
    favorites = FavoritesLimits(
        max_users=_positive_int(favorites_raw, "max_users", "favorites"),
        max_folders=_positive_int(favorites_raw, "max_folders", "favorites"),
        max_folder_name=_positive_int(favorites_raw, "max_folder_name", "favorites"),
    )

    results_raw = _require(raw, "results", "config.yaml")
    results = ResultsConfig(
        per_page=_positive_int(results_raw, "per_page", "results"),
    )

    charts_raw = _require(raw, "charts", "config.yaml")
    charts = ChartsConfig(
        top_authors_bars=_positive_int(charts_raw, "top_authors_bars", "charts"),
        top_locations_bars=_positive_int(charts_raw, "top_locations_bars", "charts"),
    )

    feed_raw = _require(raw, "feed", "config.yaml")
    tabs_raw = _require(feed_raw, "tabs", "feed")
    if not isinstance(tabs_raw, dict) or set(tabs_raw) != set(FEED_TABS):
        raise ConfigError(f"feed.tabs: expected exactly the keys {FEED_TABS}")
    feed = FeedConfig(
        batch=_positive_int(feed_raw, "batch", "feed"),
        tabs=tuple(
            (key, _text(tabs_raw[key], f"feed.tabs.{key}")) for key in FEED_TABS
        ),
    )

    default_page = _text(_require(raw, "default_page", "config.yaml"), "default_page")
    config = AppConfig(
        name=_text(_require(app, "name", "app"), "app.name"),
        title=title,
        default_page=default_page,
        favorites=favorites,
        results=results,
        charts=charts,
        feed=feed,
        sections=sections,
    )
    # `/` lands here, so a hidden or unknown landing page is a dead front door.
    if default_page not in seen_pages:
        raise ConfigError(f"default_page: unknown page {default_page!r}")
    if not config.page(default_page).visible:
        raise ConfigError(f"default_page: {default_page!r} is hidden")
    return config


def load_config(path: Path | None = None) -> AppConfig:
    with open(path or CONFIG_PATH, encoding="utf-8") as fh:
        return parse_config(yaml.safe_load(fh))


@lru_cache(maxsize=1)
def app_config() -> AppConfig:
    """The app's own `config.yaml`, parsed once."""
    return load_config()


def _ts_union(values: tuple[str, ...]) -> str:
    return " | ".join(json.dumps(value) for value in values) or "never"


def emit_ts(config: AppConfig) -> str:
    """The generated TypeScript module the web app imports."""
    sections = [
        {
            "key": section.key,
            "label": section.label,
            "icon": section.icon,
            "visible": section.visible,
            "place": section.place,
            "topNav": section.top_nav,
            "favorites": section.favorites,
            "pages": [
                {
                    "key": page.key,
                    "label": page.label,
                    "path": page.path,
                    "visible": page.visible,
                    "filters": page.filters,
                    "searchBox": page.search_box,
                    "favorites": page.favorites,
                    "tab": page.tab,
                }
                for page in section.pages
            ],
        }
        for section in config.sections
    ]
    body = json.dumps(sections, indent=2, ensure_ascii=False)
    feed_tabs = json.dumps(
        [{"key": key, "label": label} for key, label in config.feed.tabs],
        ensure_ascii=False,
    )
    page_keys = tuple(page.key for page in config.pages)
    section_keys = tuple(section.key for section in config.sections)
    return f"""\
/**
 * Generated from `config.yaml` - do not edit.
 *
 * Regenerate with:
 *   uv run python -m naas_abi_marketplace.applications.x.apps.x_proxy.app_config --write
 * (`pnpm build` and `pnpm dev` do it for you.)
 *
 * This is data only. The lookups the components use are in `lib/appConfig.ts`.
 */

/** Every configured page, visible or not - what the components switch on. */
export type PageKey = {_ts_union(page_keys)};

export type SectionKey = {_ts_union(section_keys)};

/** Rail icons drawn by `Shell.tsx`. */
export type IconName = {_ts_union(ICONS)};

/** Which favorites bar a section or page carries - pinned authors, or posts. */
export type FavoritesBar = {_ts_union(FAVORITES)};

export type PageConfig = {{
  key: PageKey;
  label: string;
  path: string;
  visible: boolean;
  /** Whether the Scenario / Query dropdowns show on this page. */
  filters: boolean;
  /** Whether the page has a search box, whose needle lives in `?q=`. */
  searchBox: boolean;
  /** Overrides the section's favorites bar for this page. `null` inherits. */
  favorites: FavoritesBar | null;
  /** Tab to light up while this page is open. `null` means the page itself. */
  tab: PageKey | null;
}};

export type SectionConfig = {{
  key: SectionKey;
  label: string;
  icon: IconName;
  visible: boolean;
  /** `main` is the top group of the rail, `bottom` the group under the rule. */
  place: "main" | "bottom";
  /** False hides the "<app> - <section>" bar while in this section. */
  topNav: boolean;
  /** Which favorites bar this section carries. The two never mix. */
  favorites: FavoritesBar;
  pages: PageConfig[];
}};

export const APP_NAME = {json.dumps(config.name, ensure_ascii=False)};

/** Top-bar heading, with `{{app}}` / `{{section}}` placeholders. */
export const APP_TITLE = {json.dumps(config.title, ensure_ascii=False)};

/** Where `/` sends a visitor who named no page. */
export const DEFAULT_PAGE: PageKey = {json.dumps(config.default_page)};

export const FAVORITES_LIMITS = {{
  maxUsers: {config.favorites.max_users},
  maxFolders: {config.favorites.max_folders},
  maxFolderName: {config.favorites.max_folder_name},
}};

/* `charts:` is deliberately absent: it shapes what the publisher writes, and
 * the browser never needs it. */

/** Results per page on the search pages - both page the same way. */
export const RESULTS = {{
  perPage: {config.results.per_page},
}};

/** The author feed on the Users page. */
export const FEED = {{
  /** Posts the feed opens with, and each "show more" adds. */
  batch: {config.feed.batch},
  /** The feed's tabs, in the order they are shown. */
  tabs: {feed_tabs},
}};

export const SECTIONS: SectionConfig[] = {body};
"""


def write_ts(config: AppConfig, path: Path | None = None) -> bool:
    """Write the generated module. True when it changed."""
    target = path or GENERATED_TS
    wanted = emit_ts(config)
    if target.exists() and target.read_text(encoding="utf-8") == wanted:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(wanted, encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Regenerate web/src/lib/appConfig.generated.ts from config.yaml.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when the generated module is stale (for CI).",
    )
    parser.add_argument("--config", default=None, help="Path to config.yaml.")
    parser.add_argument("--out", default=None, help="Path to the generated module.")
    args = parser.parse_args(argv)

    config = load_config(Path(args.config) if args.config else None)
    out = Path(args.out) if args.out else GENERATED_TS

    if args.check:
        current = out.read_text(encoding="utf-8") if out.exists() else ""
        if current != emit_ts(config):
            print(f"{out} is stale - run app_config --write", file=sys.stderr)
            return 1
        print(f"{out} is up to date")
        return 0

    if args.write:
        changed = write_ts(config, out)
        print(f"{'wrote' if changed else 'unchanged'} {out}")
        return 0

    # No flag: describe what the config says, which is the quickest way to see
    # what a visibility edit actually did.
    for section in config.sections:
        shown = "visible" if section.visible else "hidden"
        flags = f"{section.place}, {shown}"
        if not section.top_nav:
            flags += ", no top bar"
        if section.favorites:
            flags += ", favorites"
        print(f"{section.key} ({flags}) - {config.title_for(section.key)}")
        for page in section.pages:
            mark = " " if page.visible else "×"
            print(f"  {mark} {page.key:<12} {page.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
