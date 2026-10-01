from __future__ import annotations

import json

from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
from naas_abi.apps.nexus.apps.api.app.models import SearchTopicModel
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
