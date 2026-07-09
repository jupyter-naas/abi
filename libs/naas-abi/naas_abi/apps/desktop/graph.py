"""Embedded Oxigraph triple store for ABI Desktop.

Uses ``pyoxigraph.Store`` with on-disk persistence (RocksDB) — no server
process. The desktop app records a lightweight activity graph (chats and
messages as triples) and exposes a raw SPARQL endpoint for exploration.
"""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any

import pyoxigraph
from pyoxigraph import Literal, NamedNode, Quad, RdfFormat

ABID = "http://ontology.naas.ai/abi/desktop#"
RDF_TYPE = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")


class DesktopGraph:
    def __init__(self, graph_dir: Path):
        graph_dir.mkdir(parents=True, exist_ok=True)
        self._store = pyoxigraph.Store(str(graph_dir))
        self._lock = Lock()
        self._active_context: tuple[str, str] | None = None

    def close(self) -> None:
        # pyoxigraph flushes on drop; nothing explicit needed.
        pass

    def record_chat(self, chat: dict[str, Any]) -> None:
        subject = NamedNode(f"{ABID}chat/{chat['id']}")
        quads = [
            Quad(subject, RDF_TYPE, NamedNode(f"{ABID}Chat")),
            Quad(subject, NamedNode(f"{ABID}title"), Literal(str(chat["title"]))),
            Quad(subject, NamedNode(f"{ABID}section"), Literal(str(chat["section"]))),
            Quad(
                subject,
                NamedNode(f"{ABID}createdAt"),
                Literal(str(chat["created_at"])),
            ),
        ]
        with self._lock:
            self._store.extend(quads)

    def record_message(self, message: dict[str, Any]) -> None:
        subject = NamedNode(f"{ABID}message/{message['id']}")
        chat_node = NamedNode(f"{ABID}chat/{message['chat_id']}")
        content = str(message.get("content") or "")[:2000]
        quads = [
            Quad(subject, RDF_TYPE, NamedNode(f"{ABID}Message")),
            Quad(subject, NamedNode(f"{ABID}inChat"), chat_node),
            Quad(subject, NamedNode(f"{ABID}role"), Literal(str(message["role"]))),
            Quad(subject, NamedNode(f"{ABID}content"), Literal(content)),
            Quad(
                subject,
                NamedNode(f"{ABID}createdAt"),
                Literal(str(message["created_at"])),
            ),
        ]
        with self._lock:
            self._store.extend(quads)

    def delete_chat(self, chat_id: str) -> None:
        chat_node = NamedNode(f"{ABID}chat/{chat_id}")
        with self._lock:
            for quad in list(self._store.quads_for_pattern(chat_node, None, None)):
                self._store.remove(quad)
            for quad in list(
                self._store.quads_for_pattern(
                    None, NamedNode(f"{ABID}inChat"), chat_node
                )
            ):
                message_node = quad.subject
                for message_quad in list(
                    self._store.quads_for_pattern(message_node, None, None)
                ):
                    self._store.remove(message_quad)

    def query(self, sparql: str) -> dict[str, Any]:
        """Run a SPARQL query and return a JSON-friendly result."""
        with self._lock:
            results = self._store.query(sparql)

        # ASK queries: plain bool in older pyoxigraph, QueryBoolean in >=0.4.
        if isinstance(results, bool) or isinstance(
            results, getattr(pyoxigraph, "QueryBoolean", ())
        ):
            return {"type": "boolean", "value": bool(results)}

        if isinstance(results, pyoxigraph.QuerySolutions):
            variables = [str(v)[1:] for v in results.variables]
            rows: list[dict[str, str]] = []
            for solution in results:
                row: dict[str, str] = {}
                for variable in variables:
                    try:
                        term = solution[variable]
                    except Exception:
                        term = None
                    if term is not None:
                        row[variable] = _term_to_string(term)
                rows.append(row)
            return {"type": "solutions", "variables": variables, "rows": rows}

        # CONSTRUCT / DESCRIBE — a stream of triples.
        triples = []
        for triple in results:  # type: ignore[union-attr]
            triples.append(
                {
                    "subject": _term_to_string(triple.subject),
                    "predicate": _term_to_string(triple.predicate),
                    "object": _term_to_string(triple.object),
                }
            )
        return {"type": "triples", "triples": triples}

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._store)
        payload: dict[str, Any] = {"triples": total}
        if self._active_context is not None:
            org, model = self._active_context
            payload["active_context"] = {"org": org, "model": model}
        return payload

    def _context_graph(self, org: str, model: str) -> NamedNode:
        return NamedNode(f"{ABID}context/{org}/{model}")

    def _clear_context_graph(self, graph_name: NamedNode) -> None:
        with self._lock:
            for quad in list(
                self._store.quads_for_pattern(None, None, None, graph_name)
            ):
                self._store.remove(quad)

    def load_org_model_context(
        self, org: str, model: str, context_dir: Path
    ) -> dict[str, Any]:
        """Load ontology.ttl and instances.ttl from an org/model folder."""
        graph_name = self._context_graph(org, model)
        if self._active_context is not None:
            prev_org, prev_model = self._active_context
            if (prev_org, prev_model) != (org, model):
                self._clear_context_graph(self._context_graph(prev_org, prev_model))
        self._clear_context_graph(graph_name)

        loaded: list[str] = []
        for filename in ("ontology.ttl", "instances.ttl"):
            path = context_dir / filename
            if not path.is_file():
                continue
            with self._lock:
                self._store.load(
                    path=str(path),
                    format=RdfFormat.TURTLE,
                    to_graph=graph_name,
                )
            loaded.append(filename)

        self._active_context = (org, model)
        with self._lock:
            context_triples = len(
                list(self._store.quads_for_pattern(None, None, None, graph_name))
            )
        return {
            "org": org,
            "model": model,
            "graph": str(graph_name.value),
            "loaded_files": loaded,
            "context_triples": context_triples,
        }


def _term_to_string(term: Any) -> str:
    if isinstance(term, NamedNode):
        return str(term.value)
    if isinstance(term, Literal):
        return str(term.value)
    return str(term)
