"""Count Recent Tweets page — kpis / barcharts / linecharts snapshots."""

from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import SnapshotContext
from naas_abi_marketplace.applications.x.apps.x_proxy.api.count_recent_tweets import (
    barcharts as _barcharts,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.api.count_recent_tweets import (
    kpis as _kpis,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.api.count_recent_tweets import (
    linecharts as _linecharts,
)


def publish_page(ctx: SnapshotContext) -> dict:
    return {
        "kpis": _kpis.publish(ctx),
        "barcharts": _barcharts.publish(ctx),
        "linecharts": _linecharts.publish(ctx),
    }
