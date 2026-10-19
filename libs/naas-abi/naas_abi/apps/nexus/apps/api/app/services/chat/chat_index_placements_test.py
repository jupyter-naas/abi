"""A conversation's file index is placed in the workspace of the conversation."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_file_embeddings import (
    build_embedding_cache_key,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.chat_index_placements import (
    conversation_indexes,
    place_conversation_index,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.names import encode_id


def _placed(nexus: NexusIam, service: str) -> dict[str, str]:
    with as_service_account("api"):
        return {p.id_key: p.workspace for p in nexus.iam.list_placements(service)}


@pytest.mark.asyncio
async def test_the_collection_its_vectors_and_the_cache_are_placed(team: NexusIam) -> None:
    await place_conversation_index("ws-1", "conv-1")

    vectors = _placed(team, "vector_store")
    assert vectors == {"chat_conv-1": "ws-1", "chat_conv-1/*": "ws-1"}
    cached = _placed(team, "cache")
    key = encode_id(build_embedding_cache_key("ws-1", "abc", "hash-v1", 32), "opaque")
    assert [prefix for prefix in cached if key.startswith(prefix.removesuffix("*"))] != []
    assert set(cached.values()) == {"ws-1"}


@pytest.mark.asyncio
async def test_placing_twice_changes_nothing(team: NexusIam) -> None:
    await place_conversation_index("ws-1", "conv-1")
    before = (_placed(team, "vector_store"), _placed(team, "cache"))

    await place_conversation_index("ws-1", "conv-1")

    assert (_placed(team, "vector_store"), _placed(team, "cache")) == before


@pytest.mark.asyncio
async def test_a_workspace_cache_prefix_does_not_cover_a_longer_workspace_id(
    team: NexusIam,
) -> None:
    await place_conversation_index("ws-1", "conv-1")

    (prefix,) = _placed(team, "cache")
    other = encode_id(build_embedding_cache_key("ws-10", "abc", "hash-v1", 32), "opaque")

    assert not other.startswith(prefix.removesuffix("*"))


@pytest.mark.asyncio
async def test_existing_indexes_are_placed_from_the_ingestion_jobs() -> None:
    class Db:
        async def execute(self, _statement):
            return SimpleNamespace(
                all=lambda: [("ws-1", "conv-1"), ("ws-1", "conv-2"), ("ws-2", "c")]
            )

    found = await conversation_indexes(Db())  # type: ignore[arg-type]

    keys = sorted((p.service, p.workspace, p.id_key()) for p in found)
    assert ("vector_store", "ws-1", "chat_conv-2/*") in keys
    assert ("vector_store", "ws-2", "chat_c") in keys
    assert sorted({p.workspace for p in found if p.service == "cache"}) == ["ws-1", "ws-2"]
