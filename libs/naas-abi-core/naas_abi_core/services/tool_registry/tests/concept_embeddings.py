"""Deterministic embedding fixtures for semantic tool search tests.

``ConceptEmbeddings`` maps words onto a small, hand-written set of concepts
(synonym groups), so "report a defect in our codebase" and "Create a new issue
in a GitHub repository" land close together without sharing a single word.
That makes paraphrase retrieval testable without a network call or a model
download. It is a LangChain ``Embeddings``, so it can be registered in the
model registry exactly like a real provider.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence

from langchain_core.embeddings import Embeddings

from naas_abi_core.models.Model import EmbeddingModel
from naas_abi_core.services.tool_registry.ToolRegistryPort import IToolEmbedderPort

CONCEPTS: dict[str, tuple[str, ...]] = {
    "issue": (
        "issue",
        "issues",
        "ticket",
        "tickets",
        "bug",
        "bugs",
        "defect",
        "defects",
    ),
    "create": ("create", "open", "new", "raise", "add", "submit", "report", "file"),
    "repository": ("repository", "repositories", "repo", "repos", "codebase", "github"),
    "pull_request": ("pull", "merge", "review", "reviews", "changes"),
    "list": ("list", "show", "browse", "enumerate", "all"),
    "email": ("email", "emails", "mail", "message", "messages", "inbox", "recipient"),
    "send": ("send", "deliver", "dispatch", "write"),
    "calendar": (
        "calendar",
        "event",
        "events",
        "meeting",
        "meetings",
        "appointment",
        "schedule",
    ),
    "weather": ("weather", "forecast", "temperature", "rain", "sunny", "outside"),
    "place": ("city", "town", "location", "place"),
}

_WORD = re.compile(r"[a-z0-9]+")


def concept_vector(text: str) -> list[float]:
    words = _WORD.findall(text.lower())
    vector = [
        float(sum(words.count(w) for w in synonyms)) for synonyms in CONCEPTS.values()
    ]
    norm = math.sqrt(sum(v * v for v in vector))
    return [v / norm for v in vector] if norm else vector


class ConceptEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [concept_vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return concept_vector(text)


def concept_embedding_model(model_id: str = "concepts-v1") -> EmbeddingModel:
    return EmbeddingModel(
        model_id=model_id,
        provider="fixture",
        model=ConceptEmbeddings(),
        dimensions=len(CONCEPTS),
    )


class CountingConceptEmbedder(IToolEmbedderPort):
    """Port-level embedder that records how many texts it embedded."""

    def __init__(self, model_key: str = "fixture/concepts-v1") -> None:
        self.key = model_key
        self.embedded: list[str] = []
        self.queries: list[str] = []

    @property
    def model_key(self) -> str:
        return self.key

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        self.embedded.extend(texts)
        return [concept_vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return concept_vector(text)
