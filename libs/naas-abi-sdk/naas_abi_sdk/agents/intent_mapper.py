"""Embedding-based intent matching, async, same scores as core's IntentMapper.

Core keeps the index in an in-memory Qdrant collection with cosine distance; a
plain cosine search gives the same scores without the dependency. Embeddings come
from any LangChain ``Embeddings`` (the SDK registry proxy in modules).
"""

from __future__ import annotations

import asyncio
import math
from typing import Any

from naas_abi_sdk.agents.intents import Intent


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class IntentMapper:
    def __init__(self, intents: list[Intent], embedding_model: Any | None = None):
        self.intents = intents
        self._embedding_model = embedding_model
        self._vectors: list[list[float]] | None = None
        self._lock = asyncio.Lock()

    async def _ensure_index(self) -> None:
        if self._vectors is not None:
            return
        async with self._lock:
            if self._vectors is not None:
                return
            values = [intent.intent_value for intent in self.intents]
            if not values:
                self._vectors = []
                return
            if self._embedding_model is None:
                raise RuntimeError(
                    "IntentMapper needs an embedding_model to map intents"
                )
            vectors = await self._embedding_model.aembed_documents(values)
            if not vectors or not vectors[0]:
                raise ValueError(
                    "Unable to build intent index: empty embedding vectors"
                )
            self._vectors = vectors

    async def map_intent(self, text: str, k: int = 1) -> list[dict]:
        await self._ensure_index()
        if not self._vectors:
            return []
        query = await self._embedding_model.aembed_query(text)
        scored = sorted(
            (
                (_cosine(query, vector), index)
                for index, vector in enumerate(self._vectors)
            ),
            key=lambda pair: (-pair[0], pair[1]),
        )[:k]
        return [
            {
                "text": self.intents[index].intent_value,
                "metadata": {"index": index},
                "score": score,
                "intent": self.intents[index],
            }
            for score, index in scored
        ]

    async def map_prompt(
        self, prompt: str, k: int = 1
    ) -> tuple[list[dict], list[dict]]:
        return [], await self.map_intent(prompt, k)
