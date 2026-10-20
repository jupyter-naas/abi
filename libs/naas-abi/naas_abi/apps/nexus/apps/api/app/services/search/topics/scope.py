"""Narrow a workspace's graph scope to the graphs a topic names."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.graph.access import GraphAccessScope


def topic_scope(scope: GraphAccessScope, graphs: tuple[str, ...] | list[str]) -> GraphAccessScope:
    """A read-only scope: the topic's graphs that the workspace may read, or all of them.

    A topic never widens access. Naming a graph the workspace cannot read
    leaves it out rather than failing, so a topic shared across workspaces
    reads what each one is allowed to.
    """
    readable = scope.readable & frozenset(graphs) if graphs else scope.readable
    return GraphAccessScope(scope.workspace_id, readable, frozenset())
