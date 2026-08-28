"""Global snapshots: scenarios, queries, timezone, graph totals."""

from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import SnapshotContext
from naas_abi_marketplace.applications.x.apps.x_proxy.api.globals import (
    graph as _graph,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.api.globals import (
    queries as _queries,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.api.globals import (
    scenarios as _scenarios,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.api.globals import (
    timezone as _timezone,
)


def publish_globals(ctx: SnapshotContext) -> dict:
    return {
        "scenarios": _scenarios.publish(ctx),
        "queries": _queries.publish(ctx),
        "timezone": _timezone.publish(ctx),
        "graph": _graph.publish(ctx),
    }
