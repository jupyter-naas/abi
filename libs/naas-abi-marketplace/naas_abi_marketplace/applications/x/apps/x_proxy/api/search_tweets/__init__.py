"""Search Tweets page - full-graph post index."""

from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import SnapshotContext
from naas_abi_marketplace.applications.x.apps.x_proxy.api.search_tweets import (
    posts as _posts,
)


def publish_page(ctx: SnapshotContext) -> dict:
    return {
        "posts": _posts.publish(ctx),
    }
