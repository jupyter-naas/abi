"""``workspace_feature_policies``, through a session of its own per call."""

from __future__ import annotations

from collections.abc import Callable, Collection
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.feature_access.port import FeaturePolicyStore
from sqlalchemy import bindparam, text


class SqlFeaturePolicyStore(FeaturePolicyStore):
    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._sessions = session_factory

    async def policies(self, workspace_id: str) -> dict[str, str]:
        async with self._sessions() as db:
            rows = await db.execute(
                text(
                    "SELECT feature, policy_id FROM workspace_feature_policies "
                    "WHERE workspace_id = :w"
                ),
                {"w": workspace_id},
            )
            return {str(feature): str(policy_id) for feature, policy_id in rows.all()}

    async def put(self, workspace_id: str, feature: str, policy_id: str) -> None:
        async with self._sessions() as db:
            await db.execute(
                text(
                    "DELETE FROM workspace_feature_policies "
                    "WHERE workspace_id = :w AND feature = :f"
                ),
                {"w": workspace_id, "f": feature},
            )
            await db.execute(
                text(
                    "INSERT INTO workspace_feature_policies "
                    "(workspace_id, feature, policy_id, created_at) "
                    "VALUES (:w, :f, :p, CURRENT_TIMESTAMP)"
                ),
                {"w": workspace_id, "f": feature, "p": policy_id},
            )
            await db.commit()

    async def managed_among(self, policy_ids: Collection[str]) -> dict[str, str]:
        ids = sorted(set(policy_ids))
        if not ids:
            return {}
        async with self._sessions() as db:
            rows = await db.execute(
                text(
                    "SELECT policy_id, feature FROM workspace_feature_policies "
                    "WHERE policy_id IN :ids"
                ).bindparams(bindparam("ids", expanding=True)),
                {"ids": ids},
            )
            return {str(policy_id): str(feature) for policy_id, feature in rows.all()}
