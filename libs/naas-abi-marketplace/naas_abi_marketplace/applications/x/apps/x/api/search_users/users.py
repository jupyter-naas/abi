"""Publish ``search_users/users.json`` — authors in the tweet graph."""

from __future__ import annotations

from naas_abi_marketplace.applications.x.apps.x.api.common import SnapshotContext


def publish(ctx: SnapshotContext) -> dict:
    """The busiest authors in the graph, with their all-time post totals.

    Deliberately *not* scoped by followed query or scenario: the Users page
    looks an author up across the whole tweet graph. This snapshot is the
    offline fallback for the picker — with a backend, the page searches the
    graph live through ``api/users`` instead, which also reaches authors past
    ``DEFAULT_USER_LIMIT``.
    """
    users = ctx.find_users("")
    doc = {"updated_at": ctx.built_at.isoformat(), "users": users}
    ctx.save_json("search_users", "users.json", doc)
    return doc
