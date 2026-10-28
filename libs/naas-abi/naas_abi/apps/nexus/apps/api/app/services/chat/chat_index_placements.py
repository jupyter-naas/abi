"""Where a conversation's file index lives, for the kernel.

An ingested file is chunked and embedded into the vector collection
``chat_<conversation>``, and its embeddings are cached under
``embeddings:<workspace>:…``. Both belong to the conversation's workspace: IAM
places them there, or no workspace role would reach them and the ingestion job
(which runs as the uploader) would be denied by the kernel.
"""

from __future__ import annotations

from collections.abc import Iterable

from naas_abi.apps.nexus.apps.api.app.services.chat.chat_file_embeddings import (
    build_chat_collection_name,
    embedding_cache_prefix,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import placements
from naas_abi.apps.nexus.apps.api.app.services.iam.placements import Placement, placement_source
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

VECTOR_STORE = "vector_store"
CACHE = "cache"


def collection_placements(workspace_id: str, conversation_id: str) -> list[Placement]:
    """The collection itself and the vectors in it."""
    collection = build_chat_collection_name(conversation_id)
    return [
        Placement(VECTOR_STORE, (collection,), workspace_id),
        Placement(VECTOR_STORE, (collection,), workspace_id, prefix=True),
    ]


def cache_placement(workspace_id: str) -> Placement:
    return Placement(
        CACHE,
        embedding_cache_prefix(workspace_id),
        workspace_id,
        prefix=True,
        kind="opaque",
    )


async def place_conversation_index(workspace_id: str, conversation_id: str) -> None:
    """Place what the ingestion of a file into this conversation will create."""
    await placements.place_many(
        [*collection_placements(workspace_id, conversation_id), cache_placement(workspace_id)]
    )


@placement_source
async def conversation_indexes(db: AsyncSession) -> Iterable[Placement]:
    """The indexes of conversations that already ingested a file."""
    from naas_abi.apps.nexus.apps.api.app.models import ChatIngestionJobModel

    rows = (
        await db.execute(
            select(
                ChatIngestionJobModel.workspace_id, ChatIngestionJobModel.conversation_id
            ).distinct()
        )
    ).all()
    found: list[Placement] = []
    for workspace_id, conversation_id in rows:
        found.extend(collection_placements(workspace_id, conversation_id))
    found.extend(cache_placement(workspace_id) for workspace_id in {row[0] for row in rows})
    return found
