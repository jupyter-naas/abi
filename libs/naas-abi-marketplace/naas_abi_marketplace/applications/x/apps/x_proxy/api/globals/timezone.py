"""Publish ``globals/timezone.json`` — Timezone filter values."""

from __future__ import annotations

from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import SnapshotContext

DEFAULT_TIMEZONES = [
    {"id": "UTC", "label": "UTC — Coordinated Universal Time"},
    {"id": "Europe/Paris", "label": "CET — Central European Time"},
    {"id": "America/New_York", "label": "EST — Eastern Time (US)"},
    {"id": "America/Los_Angeles", "label": "PST — Pacific Time (US)"},
]


def publish(ctx: SnapshotContext) -> dict:
    doc = {
        "updated_at": ctx.built_at.isoformat(),
        "default": "UTC",
        "timezones": DEFAULT_TIMEZONES,
    }
    ctx.save_json("globals", "timezone.json", doc)
    return doc
