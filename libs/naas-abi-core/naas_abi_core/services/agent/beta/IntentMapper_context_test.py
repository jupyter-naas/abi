"""The intent index embeds as whoever started the warmup.

The warmup runs on a background thread and splits the embeddings over a worker
pool; neither inherits the caller's ``CallContext`` by itself.
"""

from __future__ import annotations

import threading

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from naas_abi_core.engine.call_context import (
    CallContext,
    as_service_account,
    current_call_context,
)
from naas_abi_core.services.agent.beta.IntentMapper import (
    Intent,
    IntentMapper,
    IntentType,
)


class _UnusedEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("embedded through the mapper's own method")

    def embed_query(self, text: str) -> list[float]:
        raise AssertionError("not queried")


def test_the_warmup_embeds_in_the_context_that_started_it():
    seen: list[CallContext] = []
    lock = threading.Lock()
    mapper = IntentMapper(
        [Intent(f"intent {n}", IntentType.RAW, f"answer {n}") for n in range(4)],
        embedding_model=_UnusedEmbeddings(),
        model=FakeListChatModel(responses=["unused"]),
        embedding_workers=2,
    )

    def embed(texts: list[str]) -> list[list[float]]:
        with lock:
            seen.append(current_call_context())
        return [[1.0, float(len(text))] for text in texts]

    mapper._embed_documents = embed  # type: ignore[method-assign]

    with as_service_account("engine") as engine:
        IntentMapper.warm_all_in_background().join(timeout=30)

    assert mapper._index_built
    assert len(seen) == 2  # one per worker batch
    assert all(context == engine for context in seen)
