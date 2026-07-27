"""Search Recent Tweets page — kpis / barcharts / linecharts / tables."""

from naas_abi_marketplace.applications.x.apps.x.api.common import SnapshotContext
from naas_abi_marketplace.applications.x.apps.x.api.search_recents_tweets import (
    barcharts as _barcharts,
)
from naas_abi_marketplace.applications.x.apps.x.api.search_recents_tweets import (
    kpis as _kpis,
)
from naas_abi_marketplace.applications.x.apps.x.api.search_recents_tweets import (
    linecharts as _linecharts,
)
from naas_abi_marketplace.applications.x.apps.x.api.search_recents_tweets import (
    tables as _tables,
)


def publish_page(ctx: SnapshotContext) -> dict:
    return {
        "kpis": _kpis.publish(ctx),
        "barcharts": _barcharts.publish(ctx),
        "linecharts": _linecharts.publish(ctx),
        "tables": _tables.publish(ctx),
    }
