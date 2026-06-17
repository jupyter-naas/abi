"""Secondary port for executing compiled SPARQL (AUDIT §7b.5, §7b.10).

This is the seam that isolates **backend differences** from the rest of the query stack.
The compiler is pure and backend-agnostic; the only place a backend matters is here:
  * how a SPARQL string is executed + results shaped (transport — already abstracted by the
    triple-store secondary adapters);
  * whether a Lucene full-text index is available (``supports_fulltext`` → the compiler's
    ``CompileContext.fts_backend``);
  * (future) a per-query timeout, which the existing ``ITripleStorePort.query(str)`` lacks.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Binding:
    """One SPARQL result cell: the lexical value + whether it was an IRI (for click-through)."""

    value: str
    is_uri: bool


# A result row maps a SPARQL variable name (without "?") to its Binding.
ResultRow = dict[str, Binding]


class IGraphQueryStore(ABC):
    @abstractmethod
    def select(self, sparql: str) -> list[ResultRow]:
        """Run a SELECT and return its rows."""

    @abstractmethod
    def count(self, sparql: str) -> int:
        """Run a single-row ``COUNT`` query and return the integer total."""

    @abstractmethod
    def supports_fulltext(self) -> bool:
        """True when the backend has a queryable full-text index (Jena + jena-text)."""
