from __future__ import annotations

import json

from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
from naas_abi.apps.nexus.apps.api.app.models import SearchSettingsModel, SearchTopicModel
from naas_abi.apps.nexus.apps.api.app.services.search.topics.port import SearchTopicStorePort
from naas_abi.apps.nexus.apps.api.app.services.search.topics.topics__schema import SearchTopic
from sqlalchemy import delete, select


class PostgresSearchTopicStore(SearchTopicStorePort):
    """One row per (workspace, topic); the definition is a JSON document."""

    async def list(self, workspace_id: str) -> list[SearchTopic]:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SearchTopicModel).where(SearchTopicModel.workspace_id == workspace_id)
            )
            return [
                SearchTopic.from_dict(json.loads(str(row.definition)))
                for row in result.scalars().all()
            ]

    async def save(self, workspace_id: str, topic: SearchTopic, *, user_id: str | None) -> None:
        async with AsyncSessionLocal() as db:
            row = await db.get(SearchTopicModel, (workspace_id, topic.id))
            definition = json.dumps(topic.to_dict())
            if row is None:
                db.add(
                    SearchTopicModel(
                        workspace_id=workspace_id,
                        topic_id=topic.id,
                        definition=definition,
                        updated_by=user_id,
                    )
                )
            else:
                row.definition = definition  # type: ignore[assignment]
                row.updated_by = user_id  # type: ignore[assignment]
            await db.commit()

    async def delete(self, workspace_id: str, topic_id: str) -> bool:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(SearchTopicModel).where(
                    (SearchTopicModel.workspace_id == workspace_id)
                    & (SearchTopicModel.topic_id == topic_id)
                )
            )
            await db.commit()
            return bool(getattr(result, "rowcount", 0))

    async def get_disabled_scopes(self, workspace_id: str) -> set[str] | None:
        async with AsyncSessionLocal() as db:
            row = await db.get(SearchSettingsModel, workspace_id)
            if row is None:
                return None
            return set(json.loads(str(row.settings)).get("disabled_scopes", []))

    async def set_disabled_scopes(
        self, workspace_id: str, scope_ids: set[str], *, user_id: str | None
    ) -> None:
        async with AsyncSessionLocal() as db:
            row = await db.get(SearchSettingsModel, workspace_id)
            settings = json.dumps({"disabled_scopes": sorted(scope_ids)})
            if row is None:
                db.add(
                    SearchSettingsModel(
                        workspace_id=workspace_id, settings=settings, updated_by=user_id
                    )
                )
            else:
                row.settings = settings  # type: ignore[assignment]
                row.updated_by = user_id  # type: ignore[assignment]
            await db.commit()
