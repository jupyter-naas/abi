"""Web apps a module serves over NATS (docs/adr/20261012_remote-module-apps.md).

A module ships an app as a folder next to its package, as in-engine modules do:
``apps/<name>/manifest.json`` plus its HTML, scripts and styles. Discovery
announces each one, Nexus lists it and forwards its requests under
``/app-html/remote/<module_id>/<name>/``, and the module's ``AppHost`` answers
them: a file of the folder, or, for any other path, the ASGI application bound
with ``BaseModule.expose_app`` (FastAPI, Starlette).
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from naas_abi_proto.discovery.v1 import discovery_pb2 as pb

APP_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}")
MAX_APPS = 16
DEFAULT_ENTRY = "index.html"
# The largest request body an app takes when its manifest sets none.
DEFAULT_MAX_UPLOAD_BYTES = 1024 * 1024 * 1024


@dataclass(frozen=True)
class AppDescriptor:
    name: str
    title: str = ""
    description: str = ""
    category: str = "module"
    icon_emoji: str = ""
    entry: str = DEFAULT_ENTRY
    contract_major: int = 1
    # Largest request body it takes; 0: DEFAULT_MAX_UPLOAD_BYTES (1 GiB).
    max_upload_bytes: int = 0
    # The folder its files are served from; None: the ASGI app serves everything.
    root: Path | None = None

    def __post_init__(self) -> None:
        if not APP_NAME.fullmatch(self.name):
            raise ValueError(
                f"App name {self.name!r}: 1 to 64 letters, digits, '_' or '-' "
                "(it is a URL segment)"
            )
        if self.entry.startswith("/") or ".." in self.entry.split("/"):
            raise ValueError(f"App {self.name}: entry must be a relative path")
        if self.max_upload_bytes < 0:
            raise ValueError(f"App {self.name}: max_upload_bytes must not be negative")

    @property
    def upload_limit(self) -> int:
        """The largest request body the app takes: Nexus refuses more, and the
        module stops reading past it whatever the request says."""
        return self.max_upload_bytes or DEFAULT_MAX_UPLOAD_BYTES

    def to_pb(self) -> pb.AppDescriptor:
        return pb.AppDescriptor(
            name=self.name,
            title=self.title,
            description=self.description,
            category=self.category,
            icon_emoji=self.icon_emoji,
            entry=self.entry,
            contract_major=self.contract_major,
            max_upload_bytes=self.max_upload_bytes,
        )


def _entry(url: Any) -> str:
    """``html:<file>`` (the manifest shorthand Nexus uses) names the entry page."""
    if isinstance(url, str) and url.startswith("html:") and len(url) > 5:
        return url[5:]
    return DEFAULT_ENTRY


def _text(manifest: dict, key: str, default: str = "") -> str:
    value = manifest.get(key, default)
    return value if isinstance(value, str) else default


def _size(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("max_upload_bytes must be a non-negative integer")
    return value


def read_app(folder: Path) -> AppDescriptor:
    """The app in ``folder``, described by its ``manifest.json``."""
    try:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Unreadable app manifest in {folder}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise TypeError(f"App manifest in {folder} must be a JSON object")
    return AppDescriptor(
        name=folder.name,
        title=_text(manifest, "name", folder.name),
        description=_text(manifest, "description"),
        category=_text(manifest, "category", "module"),
        icon_emoji=_text(manifest, "icon_emoji"),
        entry=_entry(manifest.get("url")),
        max_upload_bytes=_size(manifest.get("max_upload_bytes")),
        root=folder,
    )


def module_apps_dir(module_type: type) -> Path | None:
    """``apps/`` next to the module's package (its ``__init__.py``)."""
    module = sys.modules.get(module_type.__module__)
    file = getattr(module, "__file__", None)
    if not file:
        return None
    folder = Path(file).resolve().parent / "apps"
    return folder if folder.is_dir() else None


def discover_apps(module_type: type) -> tuple[AppDescriptor, ...]:
    """Every ``apps/<name>/manifest.json`` of the module, sorted by name."""
    folder = module_apps_dir(module_type)
    if folder is None:
        return ()
    apps = tuple(
        read_app(child)
        for child in sorted(folder.iterdir())
        if child.is_dir() and (child / "manifest.json").is_file()
    )
    if len(apps) > MAX_APPS:
        raise ValueError(f"A module serves at most {MAX_APPS} apps")
    return apps
