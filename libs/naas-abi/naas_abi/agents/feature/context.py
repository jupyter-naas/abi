"""Open Nexus feature for the right-hand chat pane (Slides-parity).

Slides sends ``context.slides`` and Code sends ``context.coding``. Every other
Nexus section sends one generic block::

    {"feature": {"key": "apps", "path": "/workspace/<id>/apps",
                 "resource": {"kind": "app", "id": "<app_id>", "label": "WSR"}}}

The chat boundary stores it here so feature tools default to the open item
(the ``slides_active_slug`` idea) and never ask "which app?". The same block
is rendered into the prompt so the agent knows where the user is.
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from typing import Any

# Web FeatureKey values: "apps", "graph", "settings.workspace", ...
_FEATURE_KEY_RE = re.compile(r"^[a-z]+(?:\.[a-z]+)?$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]+")
_MAX_KEY = 64
_MAX_PATH = 512
_MAX_KIND = 64
_MAX_ID = 512
_MAX_LABEL = 200
_MAX_ERRORS = 5
_MAX_ERROR = 300

nexus_feature_context: ContextVar[dict[str, Any] | None] = ContextVar(
    "nexus_feature_context", default=None
)


def _clean(value: object, limit: int) -> str:
    """One line, no control characters, capped. The block lands in a prompt."""
    return _CONTROL_RE.sub(" ", str(value or "")).strip()[:limit]


def normalize_feature_context(client_context: object) -> dict[str, Any] | None:
    """Validated ``context.feature`` from the client, or None."""
    if not isinstance(client_context, dict):
        return None
    raw = client_context.get("feature")
    if not isinstance(raw, dict):
        return None
    key = _clean(raw.get("key"), _MAX_KEY)
    if not _FEATURE_KEY_RE.match(key):
        return None
    out: dict[str, Any] = {"key": key}
    path = _clean(raw.get("path"), _MAX_PATH)
    if path:
        out["path"] = path
    resource = raw.get("resource")
    if isinstance(resource, dict):
        kind = _clean(resource.get("kind"), _MAX_KIND)
        resource_id = _clean(resource.get("id"), _MAX_ID)
        if kind and resource_id:
            item: dict[str, str] = {"kind": kind, "id": resource_id}
            label = _clean(resource.get("label"), _MAX_LABEL)
            if label:
                item["label"] = label
            out["resource"] = item
    # Recent runtime errors of the open item (the Apps preview reports them).
    raw_errors = raw.get("errors")
    if isinstance(raw_errors, list):
        errors = [
            cleaned
            for cleaned in (
                _clean(e, _MAX_ERROR) for e in raw_errors if isinstance(e, str)
            )
            if cleaned
        ][:_MAX_ERRORS]
        if errors:
            out["errors"] = errors
    return out


def bind_feature_context(client_context: object) -> dict[str, Any] | None:
    """Set the open feature for this request. Called at the chat boundary."""
    normalized = normalize_feature_context(client_context)
    nexus_feature_context.set(normalized)
    return normalized


def active_feature_resource_id(kind: str) -> str | None:
    """Id of the open item when it is of ``kind`` (e.g. ``"app"``), else None."""
    ctx = nexus_feature_context.get() or {}
    resource = ctx.get("resource")
    if not isinstance(resource, dict) or resource.get("kind") != kind:
        return None
    return str(resource.get("id") or "").strip() or None


def active_feature_errors() -> list[str]:
    """Runtime errors the open item reported (newest last), else ``[]``."""
    ctx = nexus_feature_context.get() or {}
    return list(ctx.get("errors") or [])


def render_feature_context_block(client_context: object) -> str:
    """Prompt block naming the open feature and item, or ``""``."""
    ctx = normalize_feature_context(client_context)
    if ctx is None:
        return ""
    lines = [f"- feature: {ctx['key']}"]
    if ctx.get("path"):
        lines.append(f"- route: {ctx['path']}")
    resource = ctx.get("resource")
    if resource:
        kind = resource["kind"]
        lines.append(f"- open_{kind}_id: {resource['id']}")
        if resource.get("label"):
            lines.append(f"- open_{kind}_label: {resource['label']}")
    for error in ctx.get("errors") or []:
        lines.append(f"- preview_error: {error}")
    return (
        "\n\n## Open Nexus feature\n"
        "The user opened the chat pane on this Nexus feature. Answer about this "
        "feature first. If you own tools for it, they default to the open item "
        "below: do not ask which one. If you do not own tools for it, say which "
        "Nexus feature agent does instead of guessing.\n" + "\n".join(lines) + "\n"
    )
