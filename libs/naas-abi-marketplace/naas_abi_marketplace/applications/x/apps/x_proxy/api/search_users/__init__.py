"""Search Users page - users snapshot."""

from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import SnapshotContext
from naas_abi_marketplace.applications.x.apps.x_proxy.api.search_users import (
    users as _users,
)


def publish_page(
    ctx: SnapshotContext, *, full: bool = False, direct_user_limit: int = 100
) -> dict:
    return {
        "users": _users.publish(ctx, full=full, direct_user_limit=direct_user_limit),
    }
