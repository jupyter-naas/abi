"""The features a user may use in each workspace, as IAM decides them.

The flags Nexus shows (``/api/workspaces``) are IAM's ``nexus:UseFeature`` for
the user, within the deployment's ``enabled_features``, in one ``filter`` for
every workspace listed. They are only shown: the API decides each call again.
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Sequence
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.names import NO_ORG
from starlette.concurrency import run_in_threadpool

_log = logging.getLogger(__name__)


def _org(org_id: str | None) -> str:
    return org_id or NO_ORG


async def user_feature_flags(
    user: Any, workspaces: Sequence[tuple[str | None, str]], enabled: Collection[str]
) -> dict[str, dict[str, bool]] | None:
    """For each ``(org, workspace)``, whether ``user`` may use each feature there:
    IAM's ``nexus:UseFeature`` (the policies granting one),
    within the deployment's ``enabled`` features, in one ``filter``. None
    without IAM; when IAM fails to answer, every feature off (logged): the flags
    are only shown, the API decides each call again."""
    from naas_abi.apps.nexus.apps.api.app.core.feature_flags import KNOWN_FEATURE_KEYS
    from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ, upgrading
    from naas_abi.apps.nexus.apps.api.app.services.iam.names import nexus_resource
    from naas_abi_core.engine.call_context import use_call_context

    ctx = AUTHZ.context(user)
    keys = [key for key in KNOWN_FEATURE_KEYS if key in set(enabled)]
    names = {
        (workspace_id, key): nexus_resource(
            "feature", org=_org(org_id), workspace=workspace_id, id=key
        )
        for org_id, workspace_id in workspaces
        for key in keys
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
        except Exception:  # noqa: BLE001 - shown only: fail closed, never a 500
            _log.warning("Feature flags could not be read from IAM: shown off", exc_info=True)
            allowed = set()
        return {
            workspace_id: {
                key: names.get((workspace_id, key)) in allowed for key in KNOWN_FEATURE_KEYS
            }
            for _, workspace_id in workspaces
        }

    return await run_in_threadpool(run)


__all__ = ["user_feature_flags"]
