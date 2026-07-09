"""Embedded Oxigraph triple store for ABI Desktop.

Uses ``pyoxigraph.Store`` with on-disk persistence (RocksDB) — no server
process. The desktop app records a lightweight activity graph (chats and
messages as triples) and exposes a raw SPARQL endpoint for exploration.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

import pyoxigraph
from pyoxigraph import Literal, NamedNode, Quad, RdfFormat

from .desktop_config import resolve_system_ontology_paths

ABID = "http://ontology.naas.ai/abi/desktop#"
ABI = "http://ontology.naas.ai/abi/"
BFO_PROCESS = "http://purl.obolibrary.org/obo/BFO_0000015"
BFO_ROLE = "http://purl.obolibrary.org/obo/BFO_0000023"
RDF_TYPE = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
SYSTEM_GRAPH = NamedNode(f"{ABID}system")
FOR_SECTION = NamedNode(f"{ABID}forSection")
HARNESS_AGENT = NamedNode(f"{ABID}harnessAgent")
HARNESS_MODEL = NamedNode(f"{ABID}harnessModel")
USES_HARNESS = NamedNode(f"{ABID}usesHarness")
MAPS_TO_BFO_PROCESS = NamedNode(f"{ABID}mapsToBfoProcess")
RDFS_LABEL = NamedNode("http://www.w3.org/2000/01/rdf-schema#label")
LANGUAGE_MODEL = NamedNode(f"{ABI}LanguageModel")
HOSTED_AT = NamedNode(f"{ABI}hostedAt")
SUPPORTS_TOOLS = NamedNode(f"{ABI}supportsTools")
CAN_REALIZE = NamedNode(f"{ABI}canRealize")
MODEL_REF = NamedNode(f"{ABI}modelRef")
SITE_LOCAL = f"{ABI}SiteLocal"
SITE_CLOUD = f"{ABI}SiteCloud"

_INTENT_SECTIONS = {"chat": "chat", "code": "code", "plan": "chat", "build": "code"}

# MVP rule-based intent keywords → BFO7 process IRIs (V2: LLM intent tagger).
INTENT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "code",
        ("code", "refactor", "python", "typescript", "debug", "implement", "fix bug"),
    ),
    ("plan", ("plan", "design", "architect", "strategy", "roadmap")),
    ("summarize", ("summarize", "summary", "tldr", "explain")),
)
INTENT_TO_BFO_PROCESS: dict[str, str] = {
    "code": BFO_PROCESS,
    "plan": BFO_ROLE,
    "summarize": BFO_PROCESS,
    "general": BFO_PROCESS,
}


@dataclass(frozen=True)
class ModelSuggestion:
    """Ranked model recommendation from the SPARQL router."""

    model_ref: str
    label: str
    hosted_at: str
    score: int
    reason: str
    matched_processes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_ref": self.model_ref,
            "label": self.label,
            "hosted_at": self.hosted_at,
            "score": self.score,
            "reason": self.reason,
            "matched_processes": list(self.matched_processes),
        }


class DesktopGraph:
    def __init__(self, graph_dir: Path):
        graph_dir.mkdir(parents=True, exist_ok=True)
        self._store = pyoxigraph.Store(str(graph_dir))
        self._lock = Lock()
        self._active_context: tuple[str, str] | None = None
        self._system_loaded = False

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
        payload: dict[str, Any] = {
            "triples": total,
            "system_loaded": self._system_loaded,
        }
        if self._active_context is not None:
            org, model = self._active_context
            payload["active_context"] = {"org": org, "model": model}
        return payload

    def _context_graph(self, org: str, model: str) -> NamedNode:
        return NamedNode(f"{ABID}context/{org}/{model}")

    def _clear_named_graph(self, graph_name: NamedNode) -> None:
        with self._lock:
            for quad in list(
                self._store.quads_for_pattern(None, None, None, graph_name)
            ):
                self._store.remove(quad)

    def load_system_ontology(self, paths: list[Path] | None = None) -> dict[str, Any]:
        """Load BFO7 bucket TTL files into the system named graph."""
        if self._system_loaded:
            return {
                "graph": str(SYSTEM_GRAPH.value),
                "loaded_files": [],
                "reused": True,
            }

        ttl_paths = paths if paths is not None else resolve_system_ontology_paths()
        loaded: list[str] = []
        for path in ttl_paths:
            if not path.is_file():
                continue
            with self._lock:
                self._store.load(
                    path=str(path),
                    format=RdfFormat.TURTLE,
                    to_graph=SYSTEM_GRAPH,
                )
            loaded.append(path.name)

        self._system_loaded = bool(loaded)
        with self._lock:
            system_triples = len(
                list(self._store.quads_for_pattern(None, None, None, SYSTEM_GRAPH))
            )
        return {
            "graph": str(SYSTEM_GRAPH.value),
            "loaded_files": loaded,
            "system_triples": system_triples,
            "reused": False,
        }

    def load_org_model_context(
        self, org: str, model: str, context_dir: Path
    ) -> dict[str, Any]:
        """Load system BFO7 TTL plus org/model ontology and instances."""
        system = self.load_system_ontology()
        graph_name = self._context_graph(org, model)
        if self._active_context is not None:
            prev_org, prev_model = self._active_context
            if (prev_org, prev_model) != (org, model):
                self._clear_named_graph(self._context_graph(prev_org, prev_model))
        self._clear_named_graph(graph_name)

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
            "system": system,
        }

    def query_section_route(
        self, org: str, model: str, section: str
    ) -> dict[str, str] | None:
        """Return harness agent, model hint, harness, and BFO7 bucket for a section."""
        graph_iri = self._context_graph(org, model).value
        section_literal = _sparql_literal(section)
        sparql = f"""
SELECT ?agent ?modelHint ?harness ?bucketLabel ?bucket WHERE {{
  GRAPH <{graph_iri}> {{
    ?route <{FOR_SECTION.value}> ?section ;
           <{HARNESS_AGENT.value}> ?agent .
    FILTER(?section = {section_literal})
    OPTIONAL {{ ?route <{HARNESS_MODEL.value}> ?modelHint . }}
    OPTIONAL {{ ?route <{USES_HARNESS.value}> ?harness . }}
    OPTIONAL {{ ?route <{MAPS_TO_BFO_PROCESS.value}> ?bucket . }}
  }}
  OPTIONAL {{
    GRAPH <{SYSTEM_GRAPH.value}> {{
      ?bucket <{RDFS_LABEL.value}> ?bucketLabel .
    }}
  }}
}}
LIMIT 1
"""
        result = self.query(sparql)
        if result["type"] != "solutions" or not result["rows"]:
            return None
        row = result["rows"][0]
        payload = {key: value for key, value in row.items() if value}
        return payload or None

    def resolve_route(
        self, org: str, model: str, intent: str = "chat"
    ) -> dict[str, str] | None:
        """Resolve routing for chat or code intent.

        Returns ``agent``, optional ``model_hint``, ``harness``, and
        ``bucket_label`` when defined in org/model ``instances.ttl``.
        """
        section = _INTENT_SECTIONS.get(intent, intent)
        route = self.query_section_route(org, model, section)
        if route is None:
            return None
        payload: dict[str, str] = {}
        agent = route.get("agent", "").strip()
        if agent:
            payload["agent"] = agent
        model_hint = route.get("modelHint", "").strip()
        if model_hint:
            payload["model_hint"] = model_hint
        harness = route.get("harness", "").strip()
        if harness:
            payload["harness"] = harness
        bucket_label = route.get("bucketLabel", "").strip()
        if bucket_label:
            payload["bucket_label"] = bucket_label
        bucket = route.get("bucket", "").strip()
        if bucket:
            payload["bucket"] = bucket
        return payload or None

    def resolve_route_agent(self, org: str, model: str, section: str) -> str | None:
        """Resolve harness agent name from org/model routing instances."""
        route = self.resolve_route(org, model, section)
        if route is None:
            return None
        return route.get("agent")

    def build_routing_prompt_hint(self, org: str, model: str, section: str) -> str:
        """Compose a short routing hint block for harness prompt injection."""
        route = self.resolve_route(org, model, section)
        if route is None:
            return ""
        lines = ["## Routing (knowledge graph)"]
        agent = route.get("agent")
        if agent:
            lines.append(f"- Harness agent: `{agent}`")
        model_hint = route.get("model_hint")
        if model_hint:
            lines.append(f"- Model hint: `{model_hint}`")
        harness = route.get("harness")
        if harness:
            lines.append(f"- Harness: `{harness}`")
        bucket = route.get("bucket_label")
        if bucket:
            lines.append(f"- BFO7 bucket: {bucket}")
        return "\n".join(lines) + "\n\n"

    def active_routing_summary(self, org: str, model: str) -> dict[str, Any]:
        """Return resolved chat/code routes for the active org/model context."""
        return {
            "org": org,
            "model": model,
            "chat": self.resolve_route(org, model, "chat"),
            "code": self.resolve_route(org, model, "code"),
        }

    def suggest_models(
        self,
        intent_tags: list[str],
        prefer_local: bool,
        *,
        org: str | None = None,
        model: str | None = None,
    ) -> list[ModelSuggestion]:
        """Rank language models by BFO7 realizability and hosting site."""
        context = self._resolve_context(org, model)
        if context is None:
            return []

        org_name, model_name = context
        required_processes = _processes_for_intent_tags(intent_tags)
        if not required_processes:
            return []

        graph_iri = self._context_graph(org_name, model_name).value
        process_filter = " ".join(f"<{iri}>" for iri in sorted(required_processes))
        sparql = f"""
SELECT ?model ?modelRef ?label ?site ?processLabel WHERE {{
  GRAPH <{graph_iri}> {{
    ?model a <{LANGUAGE_MODEL.value}> ;
           <{MODEL_REF.value}> ?modelRef ;
           <{SUPPORTS_TOOLS.value}> true ;
           <{HOSTED_AT.value}> ?site ;
           <{CAN_REALIZE.value}> ?process .
    FILTER(?process IN ({process_filter}))
    OPTIONAL {{ ?model <{RDFS_LABEL.value}> ?label . }}
  }}
  OPTIONAL {{
    GRAPH <{SYSTEM_GRAPH.value}> {{
      ?process <{RDFS_LABEL.value}> ?processLabel .
    }}
  }}
}}
"""
        result = self.query(sparql)
        if result["type"] != "solutions":
            return []

        aggregated: dict[str, dict[str, Any]] = {}
        for row in result["rows"]:
            model_ref = row.get("modelRef", "").strip()
            if not model_ref:
                continue
            entry = aggregated.setdefault(
                model_ref,
                {
                    "model_ref": model_ref,
                    "label": row.get("label", "").strip()
                    or _short_model_label(model_ref),
                    "hosted_at": _hosted_at_label(row.get("site", "")),
                    "matched": set(),
                },
            )
            process_label = row.get("processLabel", "").strip()
            if process_label:
                entry["matched"].add(process_label)

        suggestions: list[ModelSuggestion] = []
        for entry in aggregated.values():
            match_count = len(entry["matched"])
            score = match_count
            if prefer_local and entry["hosted_at"] == "local":
                score += 2
            elif not prefer_local and entry["hosted_at"] == "cloud":
                score += 1

            matched = tuple(sorted(entry["matched"]))
            if matched:
                process_phrase = ", ".join(matched)
                reason = (
                    f"Realizes {process_phrase}; "
                    f"{'local' if entry['hosted_at'] == 'local' else 'cloud'} hosting"
                )
            else:
                reason = f"Matches intent; {entry['hosted_at']} hosting"

            suggestions.append(
                ModelSuggestion(
                    model_ref=entry["model_ref"],
                    label=entry["label"],
                    hosted_at=entry["hosted_at"],
                    score=score,
                    reason=reason,
                    matched_processes=matched,
                )
            )

        suggestions.sort(key=lambda s: (-s.score, s.model_ref))
        return suggestions

    def _resolve_context(
        self, org: str | None, model: str | None
    ) -> tuple[str, str] | None:
        if org is not None and model is not None:
            return org, model
        if self._active_context is not None:
            return self._active_context
        return None


def tag_intent_from_text(text: str) -> list[str]:
    """MVP rule-based intent tagger from composer text (V2: LLM)."""
    lower = text.lower().strip()
    if not lower:
        return []
    tags: list[str] = []
    for tag, keywords in INTENT_KEYWORDS:
        if any(keyword in lower for keyword in keywords):
            tags.append(tag)
    if not tags:
        tags.append("general")
    return tags


def _processes_for_intent_tags(intent_tags: list[str]) -> set[str]:
    processes: set[str] = set()
    for tag in intent_tags:
        process = INTENT_TO_BFO_PROCESS.get(tag)
        if process:
            processes.add(process)
    return processes


def _hosted_at_label(site_iri: str) -> str:
    if SITE_LOCAL in site_iri:
        return "local"
    if SITE_CLOUD in site_iri:
        return "cloud"
    return "unknown"


def _short_model_label(model_ref: str) -> str:
    slash = model_ref.find("/")
    return model_ref[slash + 1 :] if slash >= 0 else model_ref


def _sparql_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _term_to_string(term: Any) -> str:
    if isinstance(term, NamedNode):
        return str(term.value)
    if isinstance(term, Literal):
        return str(term.value)
    return str(term)
