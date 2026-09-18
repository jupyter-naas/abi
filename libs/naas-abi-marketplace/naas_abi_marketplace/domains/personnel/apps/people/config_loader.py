"""Validated runtime configuration for the People Search app.

``config.yaml`` is the only file a client edits to retarget this app. It is
validated here, on the server, so a typo fails at startup with a named error
instead of rendering a blank section in someone's browser.

Configuration can reorder, rename, retitle and hide what is registered; it
cannot create a page or a profile section. The registered ids below are the
contract with ``web/lib/registry.js``.
"""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

APP_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = APP_ROOT / "config.yaml"
# Brand files live under web/ so one path works everywhere: the page is served
# from web/index.html by the dev server and, inside Nexus, from
# /app-html/<module>/people/web/index.html. An asset outside web/ would 404 there.
WEB_ROOT = APP_ROOT / "web"
ASSETS_ROOT = WEB_ROOT / "assets"

REGISTERED_PAGE_IDS = frozenset({"home", "results", "profile", "ontology"})
REGISTERED_SECTION_IDS = (
    "about",
    "experience",
    "education",
    "skills",
    "certifications",
    "languages",
    "recommendations",
    "interests",
    "sources",
)
# Columns of the people table a facet or a header fact may be built from.
PERSON_FIELDS = (
    "slug",
    "full_name",
    "headline",
    "about",
    "quote",
    "photo_url",
    "organization",
    "office",
    "city",
    "country",
    "country_code",
    "service_line",
    "grade",
    "years_of_experience",
    "public_profile_url",
)
# Fields a search weight may be given for: people columns plus the child tables
# folded into the searchable text.
SEARCH_FIELDS = frozenset(PERSON_FIELDS) | {
    "skills",
    "experience",
    "education",
    "certifications",
    "languages",
    "interests",
}
PAGE_TOKEN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


class ConfigError(ValueError):
    """Raised when ``config.yaml`` cannot safely drive the application."""


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{path} must be a mapping")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{path} must be a non-empty string")
    return value.strip()


def _sequence(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ConfigError(f"{path} must be a non-empty list")
    return value


def _asset(value: Any, path: str) -> str | None:
    """Resolve a brand asset against ``assets/``; empty means 'use the mark'."""
    if value in (None, ""):
        return None
    relative = _text(value, path).lstrip("/")
    if ".." in Path(relative).parts:
        raise ConfigError(f"{path} must stay inside the app folder")
    if not relative.startswith("assets/"):
        raise ConfigError(f"{path} must be a path under assets/")
    if not (WEB_ROOT / relative).is_file():
        raise ConfigError(f"{path} points at a file that does not exist: {relative}")
    return relative


def _validate_brand(brand: dict[str, Any]) -> dict[str, Any]:
    _text(brand.get("name"), "brand.name")
    _text(brand.get("mark"), "brand.mark")
    out = deepcopy(brand)
    out["logo_src"] = _asset(brand.get("logo_src"), "brand.logo_src")
    out["favicon_src"] = _asset(brand.get("favicon_src"), "brand.favicon_src")
    return out


def _validate_pages(app: dict[str, Any]) -> list[dict[str, Any]]:
    pages = _sequence(app.get("pages"), "app.pages")
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    seen_orders: set[int] = set()
    validated: list[dict[str, Any]] = []
    for index, value in enumerate(pages):
        page = _mapping(value, f"app.pages[{index}]")
        page_id = _text(page.get("page_id"), f"app.pages[{index}].page_id")
        if page_id not in REGISTERED_PAGE_IDS:
            raise ConfigError(
                f"app.pages[{index}].page_id is not registered: {page_id}. "
                f"Registered pages: {', '.join(sorted(REGISTERED_PAGE_IDS))}"
            )
        if page_id in seen_ids:
            raise ConfigError(f"app.pages page_id is duplicated: {page_id}")
        seen_ids.add(page_id)

        # The home page owns the root path, so its url is the empty string.
        url = str(page.get("url", "")).strip("/")
        if url and not PAGE_TOKEN.match(url):
            raise ConfigError(
                f"app.pages[{index}].url must be lowercase letters, digits or '-': {url!r}"
            )
        if url in seen_urls:
            raise ConfigError(f"app.pages url is duplicated: {url!r}")
        seen_urls.add(url)

        order = page.get("order")
        if not isinstance(order, int):
            raise ConfigError(f"app.pages[{index}].order must be an integer")
        if order in seen_orders:
            raise ConfigError(f"app.pages order is duplicated: {order}")
        seen_orders.add(order)

        permissions = page.get("permissions") or ["public"]
        if not isinstance(permissions, list) or not all(
            isinstance(p, str) for p in permissions
        ):
            raise ConfigError(
                f"app.pages[{index}].permissions must be a list of strings"
            )

        validated.append(
            {
                "page_id": page_id,
                "url": url,
                "label": _text(page.get("label"), f"app.pages[{index}].label"),
                "order": order,
                "enabled": bool(page.get("enabled", True)),
                "permissions": permissions,
            }
        )

    default_page = _text(app.get("default_page"), "app.default_page")
    if default_page not in seen_ids:
        raise ConfigError(f"app.default_page is not one of the pages: {default_page}")
    return sorted(validated, key=lambda page: page["order"])


def _validate_sections(profile: dict[str, Any]) -> list[dict[str, Any]]:
    sections = _sequence(profile.get("sections"), "profile.sections")
    seen: set[str] = set()
    orders: set[int] = set()
    validated: list[dict[str, Any]] = []
    for index, value in enumerate(sections):
        section = _mapping(value, f"profile.sections[{index}]")
        section_id = _text(section.get("id"), f"profile.sections[{index}].id")
        if section_id not in REGISTERED_SECTION_IDS:
            raise ConfigError(
                f"profile.sections[{index}].id is not registered: {section_id}. "
                f"Registered sections: {', '.join(REGISTERED_SECTION_IDS)}"
            )
        if section_id in seen:
            raise ConfigError(f"profile.sections id is duplicated: {section_id}")
        seen.add(section_id)

        order = section.get("order")
        if not isinstance(order, int):
            raise ConfigError(f"profile.sections[{index}].order must be an integer")
        if order in orders:
            raise ConfigError(f"profile.sections order is duplicated: {order}")
        orders.add(order)

        validated.append(
            {
                "id": section_id,
                "label": _text(
                    section.get("label"), f"profile.sections[{index}].label"
                ),
                "order": order,
                "enabled": bool(section.get("enabled", True)),
                "empty_text": _text(
                    section.get("empty_text"), f"profile.sections[{index}].empty_text"
                ),
            }
        )
    return sorted(validated, key=lambda section: section["order"])


def _validate_facts(profile: dict[str, Any]) -> list[dict[str, Any]]:
    facts = profile.get("facts") or []
    if not isinstance(facts, list):
        raise ConfigError("profile.facts must be a list")
    validated: list[dict[str, Any]] = []
    for index, value in enumerate(facts):
        fact = _mapping(value, f"profile.facts[{index}]")
        field = _text(fact.get("field"), f"profile.facts[{index}].field")
        if field not in PERSON_FIELDS:
            raise ConfigError(
                f"profile.facts[{index}].field is not a people column: {field}. "
                f"Columns: {', '.join(PERSON_FIELDS)}"
            )
        validated.append(
            {
                "field": field,
                "label": _text(fact.get("label"), f"profile.facts[{index}].label"),
                "suffix": fact.get("suffix") or "",
            }
        )
    return validated


def _validate_search(search: dict[str, Any]) -> dict[str, Any]:
    fields = _sequence(search.get("fields"), "search.fields")
    weights: dict[str, float] = {}
    for index, value in enumerate(fields):
        field = _mapping(value, f"search.fields[{index}]")
        name = _text(field.get("name"), f"search.fields[{index}].name")
        if name not in SEARCH_FIELDS:
            raise ConfigError(
                f"search.fields[{index}].name is not searchable: {name}. "
                f"Searchable: {', '.join(sorted(SEARCH_FIELDS))}"
            )
        weight = field.get("weight")
        if not isinstance(weight, int | float) or weight <= 0:
            raise ConfigError(
                f"search.fields[{index}].weight must be a positive number"
            )
        weights[name] = float(weight)

    facet_field = _text(search.get("facet_field"), "search.facet_field")
    if facet_field not in PERSON_FIELDS:
        raise ConfigError(
            f"search.facet_field is not a people column: {facet_field}. "
            f"Columns: {', '.join(PERSON_FIELDS)}"
        )

    out = deepcopy(search)
    out["weights"] = weights
    out["facet_field"] = facet_field
    out["facet_label"] = _text(search.get("facet_label"), "search.facet_label")
    out["all_facet_label"] = search.get("all_facet_label") or "All"
    out["and_semantics"] = bool(search.get("and_semantics", True))
    for key, default in (
        ("snippet_length", 220),
        ("min_autocomplete_chars", 2),
        ("max_suggestions", 6),
        ("page_size", 20),
    ):
        value = search.get(key, default)
        if not isinstance(value, int) or value <= 0:
            raise ConfigError(f"search.{key} must be a positive integer")
        out[key] = value
    return out


def _validate_data(data: dict[str, Any]) -> dict[str, Any]:
    namespace = _text(data.get("namespace"), "data.namespace")
    if not IDENTIFIER.match(namespace):
        raise ConfigError(
            f"data.namespace must be a SQL identifier (letter, then letters, "
            f"digits or underscore): {namespace!r}"
        )
    tables = _mapping(data.get("tables"), "data.tables")
    required = {
        "people",
        "experience",
        "education",
        "skills",
        "certifications",
        "languages",
        "recommendations",
        "interests",
        "sources",
    }
    missing = sorted(required - set(tables))
    if missing:
        raise ConfigError(f"data.tables is missing: {', '.join(missing)}")
    for key, value in tables.items():
        name = _text(value, f"data.tables.{key}")
        if not IDENTIFIER.match(name):
            raise ConfigError(f"data.tables.{key} must be a SQL identifier: {name!r}")
    return {"namespace": namespace, "tables": dict(tables)}


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load and validate the complete server-side configuration."""
    config_path = path or CONFIG_PATH
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"Cannot read {config_path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc

    config = _mapping(raw, "config")
    _text(config.get("schema_version"), "schema_version")
    app = _mapping(config.get("app"), "app")
    profile = _mapping(config.get("profile"), "profile")

    return {
        "schema_version": config["schema_version"],
        "brand": _validate_brand(_mapping(config.get("brand"), "brand")),
        "app": {
            "default_page": app["default_page"],
            "pages": _validate_pages(app),
        },
        "theme": _mapping(config.get("theme"), "theme"),
        "search": _validate_search(_mapping(config.get("search"), "search")),
        "profile": {
            "facts": _validate_facts(profile),
            "sections": _validate_sections(profile),
        },
        "data": _validate_data(_mapping(config.get("data"), "data")),
        "privacy": config.get("privacy") or {},
        "graph": config.get("graph") or {},
    }


def public_config(path: Path | None = None) -> dict[str, Any]:
    """The configuration the browser may see.

    Table names, the namespace and the privacy rules stay on the server: the
    browser asks this app for people, never the dataset service directly.
    Pages without the ``public`` permission are dropped rather than hidden, so
    turning one off is not merely cosmetic.
    """
    config = load_config(path)
    pages = [
        page
        for page in config["app"]["pages"]
        if page["enabled"] and "public" in page["permissions"]
    ]
    sections = [
        section for section in config["profile"]["sections"] if section["enabled"]
    ]
    search = deepcopy(config["search"])
    search.pop("fields", None)
    return {
        "schema_version": config["schema_version"],
        "brand": config["brand"],
        "app": {"default_page": config["app"]["default_page"], "pages": pages},
        "theme": config["theme"],
        "search": search,
        "profile": {"facts": config["profile"]["facts"], "sections": sections},
        "graph": config.get("graph") or {},
    }


def public_page_urls(path: Path | None = None) -> set[str]:
    """URL segments the dev server should hand back to the single-page app."""
    return {page["url"] for page in public_config(path)["app"]["pages"] if page["url"]}


def section_ids(path: Path | None = None) -> list[str]:
    return [section["id"] for section in public_config(path)["profile"]["sections"]]
