"""Validated runtime configuration for Personnel Cockpit."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"
ENTITIES_PATH = Path(__file__).resolve().parent / "data" / "globals" / "entities.json"
REGISTERED_PAGE_IDS = frozenset({"dashboard", "graph", "processes", "logs"})
PAGE_TOKEN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


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


def load_default_entity() -> dict[str, Any]:
    """Load the default organization from the generated entity registry."""
    try:
        payload = json.loads(ENTITIES_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"Cannot read {ENTITIES_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {ENTITIES_PATH}: {exc}") from exc

    entities = payload.get("entities")
    if not isinstance(entities, list) or not entities:
        raise ConfigError("data/globals/entities.json must contain entities")
    organizations = [
        entity
        for entity in entities
        if isinstance(entity, dict)
        and entity.get("entity_type", "organization") == "organization"
    ]
    candidates = organizations or [entity for entity in entities if isinstance(entity, dict)]
    default = next(
        (entity for entity in candidates if entity.get("is_default") is True),
        candidates[0] if candidates else None,
    )
    if default is None:
        raise ConfigError("No valid entity exists in data/globals/entities.json")
    for field in ("entity_id", "url_slug", "display_name"):
        _text(default.get(field), f"default entity {field}")
    return deepcopy(default)


def load_config() -> dict[str, Any]:
    """Load and validate the complete server-side configuration."""
    try:
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"Cannot read {CONFIG_PATH}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {CONFIG_PATH}: {exc}") from exc

    config = _mapping(raw, "config")
    brand = _mapping(config.get("brand"), "brand")
    app = _mapping(config.get("app"), "app")
    theme = _mapping(config.get("theme"), "theme")
    _text(brand.get("name"), "brand.name")

    pages = app.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ConfigError("app.pages must be a non-empty list")

    page_ids: set[str] = set()
    urls: set[str] = set()
    orders: set[int] = set()
    for index, value in enumerate(pages):
        page = _mapping(value, f"app.pages[{index}]")
        page_id = _text(page.get("page_id"), f"app.pages[{index}].page_id")
        url = _text(page.get("url"), f"app.pages[{index}].url").strip("/")
        order = page.get("order")
        permissions = page.get("permissions")
        if page_id not in REGISTERED_PAGE_IDS:
            raise ConfigError(f"Unknown page_id: {page_id}")
        if not PAGE_TOKEN.fullmatch(url):
            raise ConfigError(f"Invalid page URL segment: {url}")
        if not isinstance(order, int) or order < 0:
            raise ConfigError(f"app.pages[{index}].order must be a non-negative integer")
        if not isinstance(permissions, list) or not all(
            isinstance(permission, str) and permission for permission in permissions
        ):
            raise ConfigError(f"app.pages[{index}].permissions must be a string list")
        if page_id in page_ids or url in urls or order in orders:
            raise ConfigError("Page ids, URLs, and order values must be unique")
        page_ids.add(page_id)
        urls.add(url)
        orders.add(order)

    default_page = _text(app.get("default_page"), "app.default_page")
    if default_page not in page_ids:
        raise ConfigError("app.default_page must reference a configured page")
    _text(app.get("banner_restore_label"), "app.banner_restore_label")
    if not isinstance(theme.get("css_variables"), dict):
        raise ConfigError("theme.css_variables must be a mapping")
    banner_icons = _mapping(theme.get("banner_icons"), "theme.banner_icons")
    _text(banner_icons.get("restore"), "theme.banner_icons.restore")
    buckets = theme.get("bfo_buckets")
    if not isinstance(buckets, list) or not buckets:
        raise ConfigError("theme.bfo_buckets must be a non-empty list")
    bucket_types = {
        bucket.get("type") for bucket in buckets if isinstance(bucket, dict)
    }
    required_buckets = {
        "Material Entity",
        "Process",
        "Temporal Region",
        "Site",
        "Quality",
        "Realizable",
        "GDC",
        "Unknown",
    }
    if not required_buckets.issubset(bucket_types):
        raise ConfigError("theme.bfo_buckets is missing required bucket types")
    _mapping(theme.get("process_slide"), "theme.process_slide")
    graph = _mapping(config.get("graph"), "graph")
    _mapping(graph.get("parameters"), "graph.parameters")
    logs = _mapping(config.get("logs"), "logs")
    if logs.get("default_operation") not in {"insert", "delete"}:
        raise ConfigError("logs.default_operation must be insert or delete")
    _text(logs.get("default_status"), "logs.default_status")
    _text(logs.get("process_label"), "logs.process_label")
    _text(logs.get("target_graph"), "logs.target_graph")
    _text(logs.get("target_graph_label"), "logs.target_graph_label")
    owner = _mapping(logs.get("owner"), "logs.owner")
    owner_person = _mapping(owner.get("person"), "logs.owner.person")
    _text(owner_person.get("entity_id"), "logs.owner.person.entity_id")
    _text(owner_person.get("display_name"), "logs.owner.person.display_name")
    owner_agent = _mapping(owner.get("agent"), "logs.owner.agent")
    _text(owner_agent.get("entity_id"), "logs.owner.agent.entity_id")
    _text(owner_agent.get("display_name"), "logs.owner.agent.display_name")
    server = _mapping(logs.get("server"), "logs.server")
    _text(server.get("site_id"), "logs.server.site_id")
    _text(server.get("display_name"), "logs.server.display_name")
    _text(server.get("ip_address"), "logs.server.ip_address")

    config = deepcopy(config)
    config["app"]["pages"] = sorted(pages, key=lambda page: page["order"])
    return config


def public_config() -> dict[str, Any]:
    """Return the browser-safe configuration.

    The current app has no authenticated session. Only pages carrying the
    explicit ``public`` permission are exposed. Other permission names are
    reserved for a future authenticated adapter and are denied by default.
    """
    loaded = load_config()
    config = {
        "schema_version": loaded.get("schema_version", "1.0"),
        "brand": deepcopy(loaded["brand"]),
        "app": deepcopy(loaded["app"]),
        "theme": deepcopy(loaded["theme"]),
        "graph": deepcopy(loaded["graph"]),
    }
    config["app"]["default_entity"] = load_default_entity()
    config["app"]["pages"] = [
        page
        for page in config["app"]["pages"]
        if page.get("enabled", False) and "public" in page.get("permissions", [])
    ]
    allowed = {page["page_id"] for page in config["app"]["pages"]}
    if config["app"]["default_page"] not in allowed:
        if not config["app"]["pages"]:
            raise ConfigError("At least one enabled public page is required")
        config["app"]["default_page"] = config["app"]["pages"][0]["page_id"]
    return config


def public_page_ids() -> frozenset[str]:
    return frozenset(page["page_id"] for page in public_config()["app"]["pages"])


def public_page_urls() -> frozenset[str]:
    return frozenset(page["url"] for page in public_config()["app"]["pages"])


def is_public_page(page_id: str) -> bool:
    return page_id in public_page_ids()
