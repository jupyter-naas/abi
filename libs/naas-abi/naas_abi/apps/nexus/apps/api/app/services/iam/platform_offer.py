"""What the platform offers its organizations: "Platform access" (ADR
``20261127_platform_offer``).

The deployment's ``enabled_features`` used to be the catalog itself: a feature outside it
existed nowhere. It is now what the platform offers by default. "Platform access", a
policy the platform owns (attached to nobody, the parent of nothing), records the Nexus
features the platform offers its organizations, in the offer's form
(``workspace_offer``: its Features section). It is made once from ``enabled_features``,
at the first start that finds none, so nothing changes on deploy; the platform admin then
changes it in Platform settings › Access › Features, where every known feature is listed.

Nexus applies it as it applied ``enabled_features`` (``feature_flags.deployment_catalog``):
a feature the platform does not offer is usable by nobody, the platform admin included,
and an organization's page does not list it. Read as ``api``, kept for a few seconds by
this process; a change made here is seen at once (``forget``).
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam.names import PLATFORM
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
    Offer,
    offer_document,
    offer_of,
)
from naas_abi_core import logger

NAME = "Platform access"
DESCRIPTION = (
    "What the platform offers every organization: the Nexus features its organizations may "
    "offer their workspaces. Made from the deployment's enabled_features; changed in Platform "
    "settings › Access › Features."
)
# How long this process keeps what it read: a change made by another process is seen then.
TTL_SECONDS = 10.0

_cache: tuple[float, str | None, frozenset[str] | None] | None = None


def _platform_policies(iam: Any) -> list[Any]:
    """The policies the platform owns, read from IAM's store: Nexus reading its own
    configuration, as the engine does, asks no authorization (nor counts as one)."""
    found: list[Any] = []
    after: str | None = None
    while True:
        page = iam.store.list_policies(limit=100, after=after, owner_scopes=[PLATFORM])
        found += list(page.items)
        after = page.next_after
        if not after:
            return found


def find(iam: Any) -> Any | None:
    """ "Platform access": the platform's own policy of that name, not managed by IAM."""
    for policy in _platform_policies(iam):
        if policy.name == NAME and not policy.managed and policy.owner_scope == PLATFORM:
            return policy
    return None


def ensure(iam: Any, features: Iterable[str]) -> str:
    """ "Platform access", made from ``features`` (the deployment's ``enabled_features``)
    when there is none yet; what it offers is kept otherwise. Its id. As ``api``."""
    policy = find(iam)
    if policy is not None:
        return str(policy.id)
    document = offer_document(Offer(features=frozenset(features)))
    made = iam.create_policy(NAME, document, description=DESCRIPTION)
    logger.info(f"Platform access made from enabled_features: {sorted(features)}")
    forget()
    return str(made.id)


def _read() -> tuple[str | None, frozenset[str] | None]:
    from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
    from naas_abi_core.engine.call_context import as_service_account

    iam = runtime.iam()
    with as_service_account("api"):
        policy = find(iam)
    if policy is None:
        return None, None
    return str(policy.id), offer_of(policy.document).features


def _known() -> tuple[str | None, frozenset[str] | None]:
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < TTL_SECONDS:
        return _cache[1], _cache[2]
    try:
        policy_id, features = _read()
    except Exception:  # noqa: BLE001 - no IAM (a test, a start): the deployment's config
        return None, None
    _cache = (now, policy_id, features)
    return policy_id, features


def policy_id() -> str | None:
    """The id of "Platform access"; None while there is none."""
    return _known()[0]


def offered() -> frozenset[str] | None:
    """The features the platform offers its organizations; None while there is no
    "Platform access" (the deployment's ``enabled_features`` then decide)."""
    return _known()[1]


def forget() -> None:
    """Read "Platform access" again at the next question (a change made here)."""
    global _cache
    _cache = None


__all__ = [
    "DESCRIPTION",
    "NAME",
    "TTL_SECONDS",
    "ensure",
    "find",
    "forget",
    "offered",
    "policy_id",
]
