"""The features a user may use in each workspace, as IAM decides them.

The flags Nexus shows (``/api/workspaces``) are IAM's ``nexus:UseFeature`` for
the user, within the deployment's ``enabled_features``, in one ``filter`` for
every workspace listed. They are only shown: the API decides each call again.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Collection, Sequence
from typing import Any, Final

from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from starlette.concurrency import run_in_threadpool

_log = logging.getLogger(__name__)

# Shown as IAM says, whatever the workspace offers: who administers it keeps its settings.
ALWAYS_SHOWN: Final = frozenset({"settings"})
# A feature shown only to whoever may also do what it is for: chatting is writing a
# conversation, which a Viewer's level never does, whatever a policy gives of the
# feature (the chat and its agents would be shown, then every message refused).
NEEDS: Final = {"chat": ("nexus:CreateConversation", "conversation")}


async def user_feature_flags(
    user: Any, workspaces: Sequence[tuple[str | None, str]], enabled: Collection[str]
) -> dict[str, dict[str, bool]] | None:
    """For each ``(org, workspace)``, whether ``user`` may use each feature there:
    IAM's ``nexus:UseFeature`` (the policies granting one),
    within the deployment's ``enabled`` features, in one ``filter``. None
    without IAM; when IAM fails to answer, every feature off (logged): the flags
    are only shown, the API decides each call again.

    What a workspace shows is within its offer ("<W> access", ``AUTHZ.offer_of``),
    for everyone: a platform admin or an organization's admin, whom IAM lets use
    more, sees the workspace as its people do, as its lists show its offer
    (``filter_scopes``). ``ALWAYS_SHOWN`` stays as IAM says: whoever may administer
    the workspace keeps its settings, to offer a feature again."""
    from naas_abi.apps.nexus.apps.api.app.core.feature_flags import KNOWN_FEATURE_KEYS
    from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ, upgrading
    from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
        nexus_resource,
        workspace_container,
    )
    from naas_abi_core.engine.call_context import use_call_context

    ctx = AUTHZ.context(user)
    keys = [key for key in KNOWN_FEATURE_KEYS if key in set(enabled)]
    names = {
        (workspace_id, key): nexus_resource(
            "feature", container=workspace_container(org_id, workspace_id), id=key
        )
        for org_id, workspace_id in workspaces
        for key in keys
    }

    # None: nothing to narrow by (no record, or no allow-list yet).
    offers = dict(
        zip(
            [workspace_id for _, workspace_id in workspaces],
            await asyncio.gather(
                *(AUTHZ.offer_of(workspace_container(org_id, ws)) for org_id, ws in workspaces)
            ),
            strict=True,
        )
    )

    def shown(workspace_id: str, key: str) -> bool:
        offer = offers.get(workspace_id)
        return key in ALWAYS_SHOWN or offer is None or key in offer.features

    user_id = str(getattr(user, "id", user))
    needs = {
        (workspace_id, key): nexus_resource(
            type_name, container=workspace_container(org_id, workspace_id), id=(user_id, "-")
        )
        for org_id, workspace_id in workspaces
        for key, (_action, type_name) in NEEDS.items()
        if key in keys
    }

    def run() -> dict[str, dict[str, bool]] | None:
        try:
            iam = runtime.iam()
        except runtime.IAMUnavailableError:
            return None  # no IAM at all: the caller shows every feature off
        if upgrading():
            return {ws: dict.fromkeys(KNOWN_FEATURE_KEYS, False) for _, ws in workspaces}
        try:
            with use_call_context(ctx):
                allowed = set(iam.filter("nexus:UseFeature", list(names.values())).allowed)
                for key, (action, _type) in NEEDS.items():
                    wanted = [name for (_ws, k), name in needs.items() if k == key]
                    if wanted:
                        allowed |= {("needs", n) for n in iam.filter(action, wanted).allowed}
        except Exception:  # noqa: BLE001 - shown only: fail closed, never a 500
            _log.warning("Feature flags could not be read from IAM: shown off", exc_info=True)
            allowed = set()
        return {
            workspace_id: {
                key: names.get((workspace_id, key)) in allowed
                and shown(workspace_id, key)
                and (
                    (workspace_id, key) not in needs
                    or ("needs", needs[(workspace_id, key)]) in allowed
                )
                for key in KNOWN_FEATURE_KEYS
            }
            for _, workspace_id in workspaces
        }

    return await run_in_threadpool(run)


__all__ = ["user_feature_flags"]
