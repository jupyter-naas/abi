"""Embedded Oxigraph triple store for ABI Desktop.

Uses ``pyoxigraph.Store`` with on-disk persistence (RocksDB) — no server
process. The desktop app records a lightweight activity graph (chats and
messages as triples) and exposes a raw SPARQL endpoint for exploration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any, Callable

import pyoxigraph
from pyoxigraph import Literal, NamedNode, Quad, RdfFormat

from ..config.desktop_config import resolve_system_ontology_paths

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
RDFS_COMMENT = NamedNode("http://www.w3.org/2000/01/rdf-schema#comment")
RDFS_SUBCLASSOF = NamedNode("http://www.w3.org/2000/01/rdf-schema#subClassOf")
SKOS_DEFINITION = NamedNode("http://www.w3.org/2004/02/skos/core#definition")
OWL_CLASS = NamedNode("http://www.w3.org/2002/07/owl#Class")

BFO_IRI_PROCESS = "http://purl.obolibrary.org/obo/BFO_0000015"
BFO_IRI_TEMPORAL = "http://purl.obolibrary.org/obo/BFO_0000008"
BFO_IRI_MATERIAL = "http://purl.obolibrary.org/obo/BFO_0000040"
BFO_IRI_SITE = "http://purl.obolibrary.org/obo/BFO_0000029"
BFO_IRI_QUALITY = "http://purl.obolibrary.org/obo/BFO_0000019"
BFO_IRI_INFORMATION = "http://purl.obolibrary.org/obo/BFO_0000031"
BFO_IRI_ROLE = "http://purl.obolibrary.org/obo/BFO_0000023"
BFO_IRI_DISPOSITION = "http://purl.obolibrary.org/obo/BFO_0000016"

# BFO object properties used for cross-bucket chat edges (BFO7BucketsProcessOntology.ttl).
BFO_HAS_PARTICIPANT = "http://purl.obolibrary.org/obo/BFO_0000057"
BFO_OCCURS_IN = "http://purl.obolibrary.org/obo/BFO_0000066"
BFO_OCCUPIES_TEMPORAL = "http://purl.obolibrary.org/obo/BFO_0000199"
BFO_CONCRETIZES = "http://purl.obolibrary.org/obo/BFO_0000059"
BFO_REALIZES = "http://purl.obolibrary.org/obo/BFO_0000055"
BFO_INHERES_IN = "http://purl.obolibrary.org/obo/BFO_0000197"

# Desktop routing entity classes (desktop-routing.ttl → BFO7 bucket anchors).
IRI_CHAT_PROCESS = f"{ABID}ChatProcess"
IRI_USER_PARTICIPANT = f"{ABID}UserParticipant"
IRI_MODEL_PARTICIPANT = f"{ABID}ModelParticipant"
IRI_CHAT_STORAGE = f"{ABID}ChatStorageRecord"
IRI_CHAT_TEMPORAL = f"{ABID}ChatTemporalRegion"
IRI_HARNESS_SITE = f"{ABID}HarnessSite"
IRI_HARNESS_AGENT_ROLE = f"{ABID}HarnessAgentRole"
IRI_SECTION_QUALITY = f"{ABID}SectionQuality"

# BFO 7-bucket palette aligned with bob_ontology.html (Forvis Mazars reference).
BFO_BUCKETS: tuple[dict[str, str], ...] = (
    {
        "id": "process",
        "iri": BFO_IRI_PROCESS,
        "label": "Process (WHAT)",
        "subtitle": "Events, activities",
        "color": "#C0392B",
    },
    {
        "id": "temporal",
        "iri": BFO_IRI_TEMPORAL,
        "label": "Temporal (WHEN)",
        "subtitle": "Time periods",
        "color": "#148F77",
    },
    {
        "id": "material",
        "iri": BFO_IRI_MATERIAL,
        "label": "Material (WHO)",
        "subtitle": "People, orgs",
        "color": "#2980B9",
    },
    {
        "id": "site",
        "iri": BFO_IRI_SITE,
        "label": "Site (WHERE)",
        "subtitle": "Locations",
        "color": "#27AE60",
    },
    {
        "id": "quality",
        "iri": BFO_IRI_QUALITY,
        "label": "Quality (HOW IT IS)",
        "subtitle": "Attributes",
        "color": "#717D7E",
    },
    {
        "id": "information",
        "iri": BFO_IRI_INFORMATION,
        "label": "Information (HOW WE KNOW)",
        "subtitle": "Data, documents",
        "color": "#D68910",
    },
    {
        "id": "role",
        "iri": BFO_IRI_ROLE,
        "label": "Role (WHY)",
        "subtitle": "Roles, capabilities",
        "color": "#7D3C98",
    },
)

_BFO_ANCHOR_IRIS: frozenset[str] = frozenset(bucket["iri"] for bucket in BFO_BUCKETS)
_BFO_IRI_TO_BUCKET: dict[str, str] = {bucket["iri"]: bucket["id"] for bucket in BFO_BUCKETS}
_BFO_IRI_TO_BUCKET[BFO_IRI_DISPOSITION] = "role"

# Light fill tints for application/subclass nodes (bob_ontology.html pattern).
_BFO_BUCKET_TINTS: dict[str, str] = {
    "process": "#FADBD8",
    "temporal": "#D5F5E3",
    "material": "#D6EAF8",
    "site": "#D5F5E3",
    "quality": "#EAECEE",
    "information": "#FDEBD0",
    "role": "#E8DAEF",
}

# Graph node group → BFO7 bucket mapping. Toolbar toggles filter by bucket_id only.
#
# | Node group          | Bucket      | Ontology IRI (desktop-routing.ttl) |
# |---------------------|-------------|-------------------------------------|
# | bfo_anchor          | (per anchor)| bfo:BFO_0000015 … BFO_0000023       |
# | ontology_class      | (SPARQL)    | rdfs:subClassOf → BFO anchor        |
# | context             | information | abid:ModelContext                   |
# | route               | (per route) | abid:SectionRoute → mapsToBfoProcess|
# | language_model      | material    | abi:LanguageModel                   |
# | settings            | information | SQLite configuration                |
# | chat_process        | process     | abid:ChatProcess → bfo:BFO_0000015  |
# | chat_temporal       | temporal    | abid:ChatTemporalRegion             |
# | chat_participant    | material    | abid:UserParticipant / ModelParticipant |
# | chat_site           | site        | abid:HarnessSite / abi:SiteLocal|Cloud |
# | chat_storage        | information | abid:ChatStorageRecord              |
# | chat_role           | role        | abid:HarnessAgentRole               |
# | chat_quality        | quality     | abid:SectionQuality                 |
# | graph_chat          | information | abid:Chat (Oxigraph individual)     |
# | sqlite_message      | information | abid:Message                        |
# | graph_message       | information | abid:Message                        |
#
# Chat subgraph edges use BFO properties: hasParticipant, occursIn,
# occupiesTemporalRegion, concretizes, realizes, inheresIn.
_APP_NODE_DEFAULT_BUCKETS: dict[str, str] = {
    "context": "information",
    "language_model": "material",
    "settings": "information",
    "chat_process": "process",
    "chat_temporal": "temporal",
    "chat_participant": "material",
    "chat_site": "site",
    "chat_storage": "information",
    "chat_role": "role",
    "chat_quality": "quality",
    "graph_chat": "information",
    "sqlite_message": "information",
    "graph_message": "information",
    "route": "process",
    "bfo_bucket": "process",
}
LANGUAGE_MODEL = NamedNode(f"{ABI}LanguageModel")
HOSTED_AT = NamedNode(f"{ABI}hostedAt")
SUPPORTS_TOOLS = NamedNode(f"{ABI}supportsTools")
CAN_REALIZE = NamedNode(f"{ABI}canRealize")
MODEL_REF = NamedNode(f"{ABI}modelRef")
SITE_LOCAL = f"{ABI}SiteLocal"
SITE_CLOUD = f"{ABI}SiteCloud"
MODEL_CONTEXT = NamedNode(f"{ABID}ModelContext")
ORGANIZATION = NamedNode(f"{ABID}Organization")
SECTION_ROUTE = NamedNode(f"{ABID}SectionRoute")
CHAT_TYPE = NamedNode(f"{ABID}Chat")
MESSAGE_TYPE = NamedNode(f"{ABID}Message")
CHAT_TITLE = NamedNode(f"{ABID}title")
CHAT_SECTION = NamedNode(f"{ABID}section")
IN_CHAT = NamedNode(f"{ABID}inChat")
MESSAGE_ROLE = NamedNode(f"{ABID}role")
MODEL_NAME = NamedNode(f"{ABID}modelName")
MODEL_URI = NamedNode(f"{ABID}modelUri")
BELONGS_TO_ORG = NamedNode(f"{ABID}belongsToOrg")
ORG_NAME = NamedNode(f"{ABID}orgName")

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
            "language_models": self.query_language_models(org, model),
        }

    def _query_ontology_properties(self, iri: str) -> dict[str, str]:
        """Fetch TTL annotation properties for a system-graph entity."""
        if not iri.strip():
            return {}
        sparql = f"""
SELECT ?label ?comment ?definition WHERE {{
  GRAPH <{SYSTEM_GRAPH.value}> {{
    <{iri}> a ?type .
    OPTIONAL {{ <{iri}> <{RDFS_LABEL.value}> ?label . }}
    OPTIONAL {{ <{iri}> <{RDFS_COMMENT.value}> ?comment . }}
    OPTIONAL {{ <{iri}> <{SKOS_DEFINITION.value}> ?definition . }}
  }}
}}
LIMIT 1
"""
        result = self.query(sparql)
        if result["type"] != "solutions" or not result["rows"]:
            return {}
        row = result["rows"][0]
        props: dict[str, str] = {}
        if row.get("label"):
            props["rdfs_label"] = str(row["label"])
        if row.get("comment"):
            props["rdfs_comment"] = str(row["comment"])
        if row.get("definition"):
            props["skos_definition"] = str(row["definition"])
        return props

    def _query_language_model_realizabilities(
        self, org: str, model: str
    ) -> dict[str, list[str]]:
        """Map modelRef → BFO7 process labels from canRealize assertions."""
        graph_iri = self._context_graph(org, model).value
        sparql = f"""
SELECT ?modelRef ?process ?processLabel WHERE {{
  GRAPH <{graph_iri}> {{
    ?m a <{LANGUAGE_MODEL.value}> ;
       <{MODEL_REF.value}> ?modelRef ;
       <{CAN_REALIZE.value}> ?process .
  }}
  OPTIONAL {{
    GRAPH <{SYSTEM_GRAPH.value}> {{
      ?process <{RDFS_LABEL.value}> ?processLabel .
    }}
  }}
}}
ORDER BY ?modelRef ?processLabel
"""
        result = self.query(sparql)
        if result["type"] != "solutions":
            return {}

        by_ref: dict[str, list[str]] = {}
        for row in result["rows"]:
            model_ref = row.get("modelRef", "").strip()
            if not model_ref:
                continue
            process = row.get("process", "").strip()
            label = row.get("processLabel", "").strip() or (
                process.rsplit("/", 1)[-1] if process else ""
            )
            entry = label or process
            if not entry:
                continue
            bucket = by_ref.setdefault(model_ref, [])
            if entry not in bucket:
                bucket.append(entry)
        return by_ref

    def query_language_models(self, org: str, model: str) -> list[dict[str, str]]:
        """List LanguageModel individuals in the active org/model context."""
        graph_iri = self._context_graph(org, model).value
        sparql = f"""
SELECT ?modelRef ?label ?site WHERE {{
  GRAPH <{graph_iri}> {{
    ?m a <{LANGUAGE_MODEL.value}> ;
       <{MODEL_REF.value}> ?modelRef ;
       <{HOSTED_AT.value}> ?site .
    OPTIONAL {{ ?m <{RDFS_LABEL.value}> ?label . }}
  }}
}}
ORDER BY ?modelRef
"""
        result = self.query(sparql)
        if result["type"] != "solutions":
            return []

        models: list[dict[str, str]] = []
        for row in result["rows"]:
            model_ref = row.get("modelRef", "").strip()
            if not model_ref:
                continue
            models.append(
                {
                    "model_ref": model_ref,
                    "label": row.get("label", "").strip()
                    or _short_model_label(model_ref),
                    "hosted_at": _hosted_at_label(row.get("site", "")),
                }
            )
        return models

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

    def list_bfo_buckets(self) -> list[dict[str, str]]:
        """Return the seven BFO bucket definitions for the Graph UI legend."""
        return [dict(bucket) for bucket in BFO_BUCKETS]

    def assign_node_bucket(
        self, group: str, detail: dict[str, Any] | None = None
    ) -> str | None:
        """Resolve the BFO7 bucket id for a graph overview node."""
        payload = detail or {}
        explicit = str(payload.get("bucket_id") or "").strip()
        if explicit:
            return explicit

        iri = str(payload.get("iri") or "").strip()
        if iri:
            direct = _BFO_IRI_TO_BUCKET.get(iri)
            if direct:
                return direct
            mapped = self.resolve_bucket_id(iri)
            if mapped:
                return mapped

        bucket_iri = str(payload.get("bucket_iri") or "").strip()
        if bucket_iri:
            mapped = _BFO_IRI_TO_BUCKET.get(bucket_iri)
            if mapped:
                return mapped

        parent = str(payload.get("parent") or "").strip()
        if parent:
            mapped = _BFO_IRI_TO_BUCKET.get(parent)
            if mapped:
                return mapped
            mapped = self.resolve_bucket_id(parent)
            if mapped:
                return mapped

        label = str(payload.get("label") or "").lower()
        iri_lower = iri.lower()
        if "chatplanning" in iri_lower or "chat section route" in label:
            return "role"
        if "codebuilding" in iri_lower or "code section route" in label:
            return "process"
        if parent.endswith("SectionRoute"):
            return "process"

        if group == "route":
            section = str(payload.get("section") or "").strip().lower()
            if section == "chat":
                return "role"
            if section == "code":
                return "process"

        if group in ("ontology_class", "bfo_bucket"):
            if "sectionroute" in iri_lower:
                return "process"
            if "modelcontext" in iri_lower or "contextdocument" in iri_lower:
                return "information"
            if "organization" in iri_lower:
                return "material"
            if "languagemodel" in iri_lower:
                return "material"
            if group == "ontology_class":
                return "information"

        return _APP_NODE_DEFAULT_BUCKETS.get(group)

    def resolve_bucket_id(self, class_iri: str) -> str | None:
        """Map an ontology class IRI to a BFO bucket id."""
        iri = class_iri.strip()
        if not iri:
            return None
        direct = _BFO_IRI_TO_BUCKET.get(iri)
        if direct:
            return direct

        visited: set[str] = set()
        current = iri
        for _ in range(12):
            if current in visited:
                break
            visited.add(current)
            sparql = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?parent WHERE {{
  GRAPH ?g {{
    <{current}> rdfs:subClassOf ?parent .
  }}
}}
LIMIT 1
"""
            result = self.query(sparql)
            if result["type"] != "solutions" or not result["rows"]:
                break
            parent = result["rows"][0].get("parent", "").strip()
            if not parent:
                break
            mapped = _BFO_IRI_TO_BUCKET.get(parent)
            if mapped:
                return mapped
            current = parent
        return None

    def query_subclasses(
        self,
        class_iri: str,
        *,
        org: str | None = None,
        model: str | None = None,
    ) -> list[dict[str, str]]:
        """Return direct rdfs:subClassOf children for an ontology class."""
        parent = class_iri.strip()
        if not parent:
            return []

        graphs = [SYSTEM_GRAPH.value]
        context = self._resolve_context(org, model)
        if context is not None:
            graphs.append(self._context_graph(*context).value)

        union_blocks = "\n  UNION\n  ".join(
            f"""{{
    GRAPH <{graph_iri}> {{
      ?sub <{RDFS_SUBCLASSOF.value}> <{parent}> .
      OPTIONAL {{ ?sub <{RDFS_LABEL.value}> ?label . }}
    }}
  }}"""
            for graph_iri in graphs
        )
        sparql = f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?sub ?label WHERE {{
  {union_blocks}
}}
ORDER BY ?label ?sub
"""
        result = self.query(sparql)
        if result["type"] != "solutions":
            return []

        subclasses: list[dict[str, str]] = []
        seen: set[str] = set()
        for row in result["rows"]:
            sub_iri = row.get("sub", "").strip()
            if not sub_iri or sub_iri in seen:
                continue
            seen.add(sub_iri)
            label = row.get("label", "").strip() or sub_iri.rsplit("/", 1)[-1]
            bucket_id = self.resolve_bucket_id(sub_iri)
            if not bucket_id:
                bucket_id = self.resolve_bucket_id(parent)
            entry: dict[str, str] = {"iri": sub_iri, "label": label}
            if bucket_id:
                entry["bucket_id"] = bucket_id
            subclasses.append(entry)
        return subclasses

    def _bucket_color(self, bucket_id: str | None) -> str:
        if not bucket_id:
            return ""
        for bucket in BFO_BUCKETS:
            if bucket["id"] == bucket_id:
                return bucket["color"]
        return ""

    def _resolve_chat_site(
        self,
        chat: dict[str, Any],
        lm_by_ref: dict[str, dict[str, str]],
    ) -> tuple[str, str]:
        """Return (site_label, site_iri) for a chat's model hosting."""
        model_ref = str(chat.get("model") or "").strip()
        if model_ref and model_ref in lm_by_ref:
            hosted = lm_by_ref[model_ref].get("hosted_at", "")
            if hosted == "cloud":
                return "cloud", SITE_CLOUD
            if hosted == "local":
                return "local", SITE_LOCAL
        if model_ref.startswith("ollama/") or not model_ref:
            return "local", SITE_LOCAL
        return "cloud", SITE_CLOUD

    def _emit_chat_bfo_subgraph(
        self,
        chat: dict[str, Any],
        messages_for_chat: list[dict[str, Any]],
        *,
        context_id: str,
        lm_by_ref: dict[str, dict[str, str]],
        settings: dict[str, str],
        route_by_section: dict[str, dict[str, str]],
        graph_chats_by_id: dict[str, str],
        add_node: Callable[..., None],
        add_edge: Callable[..., None],
    ) -> str:
        """Emit BFO7 cross-bucket nodes/edges for one chat session.

        Returns the process node id (``chat:{id}:process``).
        """
        chat_id = chat["id"]
        prefix = f"chat:{chat_id}"
        process_id = f"{prefix}:process"
        title = str(chat.get("title") or "Chat")[:40]
        section = str(chat.get("section") or "chat")

        add_node(
            process_id,
            title,
            "chat_process",
            f"Chat process: {title}",
            {
                "chat_id": chat_id,
                "iri": IRI_CHAT_PROCESS,
                "section": section,
                "source": "sqlite",
            },
        )
        add_edge(context_id, process_id, "hasChatProcess")
        add_edge(process_id, "bfo:anchor:process", "subClassOf")

        temporal_id = f"{prefix}:temporal"
        created = chat.get("created_at") or chat.get("updated_at")
        temporal_label = _format_timestamp(created)
        add_node(
            temporal_id,
            temporal_label,
            "chat_temporal",
            f"Chat temporal region: {temporal_label}",
            {
                "chat_id": chat_id,
                "iri": IRI_CHAT_TEMPORAL,
                "timestamp": created,
                "bfo_property": BFO_OCCUPIES_TEMPORAL,
                "source": "sqlite",
            },
        )
        add_edge(process_id, temporal_id, "occupiesTemporalRegion")
        add_edge(temporal_id, "bfo:anchor:temporal", "subClassOf")

        user_messages = [m for m in messages_for_chat if m.get("role") == "user"]
        user_id = f"{prefix}:user"
        add_node(
            user_id,
            "user",
            "chat_participant",
            "User participant in chat process",
            {
                "chat_id": chat_id,
                "iri": IRI_USER_PARTICIPANT,
                "role": "user",
                "message_count": len(user_messages),
                "bfo_property": BFO_HAS_PARTICIPANT,
                "source": "sqlite",
            },
        )
        add_edge(process_id, user_id, "hasParticipant")

        model_ref = str(
            chat.get("model") or settings.get("default_model") or ""
        ).strip()
        if model_ref:
            model_participant_id = f"{prefix}:model"
            add_node(
                model_participant_id,
                _short_model_label(model_ref),
                "chat_participant",
                f"Model participant: {model_ref}",
                {
                    "chat_id": chat_id,
                    "iri": IRI_MODEL_PARTICIPANT,
                    "model_ref": model_ref,
                    "bfo_property": BFO_HAS_PARTICIPANT,
                    "source": "sqlite",
                },
            )
            add_edge(process_id, model_participant_id, "hasParticipant")
            add_edge(model_participant_id, f"lm:{model_ref}", "sameAs")

        site_label, site_iri = self._resolve_chat_site(chat, lm_by_ref)
        site_id = f"{prefix}:site"
        add_node(
            site_id,
            site_label,
            "chat_site",
            f"Harness site: {site_label}",
            {
                "chat_id": chat_id,
                "iri": IRI_HARNESS_SITE,
                "site_iri": site_iri,
                "bfo_property": BFO_OCCURS_IN,
                "source": "routing",
            },
        )
        add_edge(process_id, site_id, "occursIn")
        add_edge(site_id, "bfo:anchor:site", "subClassOf")

        storage_id = f"{prefix}:storage"
        add_node(
            storage_id,
            "chats row",
            "chat_storage",
            f"SQLite chats row for {title}",
            {
                "chat_id": chat_id,
                "iri": IRI_CHAT_STORAGE,
                "table": "chats",
                "bfo_property": BFO_CONCRETIZES,
                "source": "sqlite",
            },
        )
        add_edge(process_id, storage_id, "concretizes")
        add_edge(storage_id, "bfo:anchor:information", "subClassOf")
        graph_chat_id = graph_chats_by_id.get(chat_id)
        if graph_chat_id:
            add_edge(storage_id, graph_chat_id, "synced")

        route = route_by_section.get(section, {})
        agent = route.get("agent") or settings.get(f"{section}_agent", "")
        role_id = f"{prefix}:role"
        role_label = agent or section
        add_node(
            role_id,
            role_label,
            "chat_role",
            f"Harness agent role: {role_label}",
            {
                "chat_id": chat_id,
                "iri": IRI_HARNESS_AGENT_ROLE,
                "agent": agent,
                "section": section,
                "bfo_property": BFO_REALIZES,
                "source": "oxigraph",
            },
        )
        add_edge(process_id, role_id, "realizes")
        add_edge(role_id, "bfo:anchor:role", "subClassOf")

        quality_id = f"{prefix}:quality"
        add_node(
            quality_id,
            section,
            "chat_quality",
            f"Section quality: {section}",
            {
                "chat_id": chat_id,
                "iri": IRI_SECTION_QUALITY,
                "section": section,
                "bfo_property": BFO_INHERES_IN,
                "source": "sqlite",
            },
        )
        add_edge(quality_id, user_id, "inheresIn")
        add_edge(quality_id, "bfo:anchor:quality", "subClassOf")

        return process_id

    def _query_context_ontology_classes(
        self, org: str, model: str
    ) -> tuple[list[dict[str, Any]], list[tuple[str, str, str]]]:
        """Load owl:Class nodes and subClassOf edges from the active context graph."""
        graph_iri = self._context_graph(org, model).value
        sparql = f"""
SELECT ?class ?label ?parent WHERE {{
  GRAPH <{graph_iri}> {{
    ?class a <{OWL_CLASS.value}> .
    OPTIONAL {{ ?class <{RDFS_LABEL.value}> ?label . }}
    OPTIONAL {{ ?class <{RDFS_SUBCLASSOF.value}> ?parent . }}
  }}
}}
"""
        result = self.query(sparql)
        if result["type"] != "solutions":
            return [], []

        classes: list[dict[str, Any]] = []
        edges: list[tuple[str, str, str]] = []
        seen_class: set[str] = set()
        for row in result["rows"]:
            class_iri = row.get("class", "").strip()
            if not class_iri or class_iri in seen_class:
                continue
            seen_class.add(class_iri)
            label = row.get("label", "").strip() or class_iri.rsplit("/", 1)[-1]
            parent = row.get("parent", "").strip()
            bucket_id = self.resolve_bucket_id(class_iri)
            if not bucket_id and parent:
                bucket_id = self.resolve_bucket_id(parent)
            classes.append(
                {
                    "iri": class_iri,
                    "label": label,
                    "parent": parent,
                    "bucket_id": bucket_id,
                }
            )
            if parent:
                edges.append((class_iri, parent, "subClassOf"))
        return classes, edges

    def build_graph_overview(
        self,
        *,
        settings: dict[str, str],
        chats: list[dict[str, Any]],
        messages: list[dict[str, Any]],
        org: str | None = None,
        model: str | None = None,
        chat_limit: int = 20,
        message_limit: int = 50,
    ) -> dict[str, Any]:
        """Build vis.js nodes/edges plus SQLite table snapshots for the Graph UI."""
        context = self._resolve_context(org, model)
        org_name = context[0] if context else (settings.get("active_org") or "default")
        model_name = (
            context[1] if context else (settings.get("active_model") or "default")
        )

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        seen_nodes: set[str] = set()
        edge_seq = 0

        def add_node(
            node_id: str,
            label: str,
            group: str,
            title: str,
            detail: dict[str, Any] | None = None,
        ) -> None:
            if node_id in seen_nodes:
                return
            seen_nodes.add(node_id)
            node_detail = dict(detail or {})
            bucket_id = self.assign_node_bucket(group, node_detail)
            if bucket_id:
                node_detail["bucket_id"] = bucket_id
                node_detail["bucket_color"] = self._bucket_color(bucket_id)
            nodes.append(
                {
                    "id": node_id,
                    "label": label,
                    "group": group,
                    "title": title,
                    "bucket_id": bucket_id or "",
                    "bucket_color": self._bucket_color(bucket_id) if bucket_id else "",
                    "detail": node_detail,
                }
            )

        def add_edge(
            source: str,
            target: str,
            label: str = "",
            edge_id: str | None = None,
        ) -> None:
            if source not in seen_nodes or target not in seen_nodes:
                return
            nonlocal edge_seq
            edge_seq += 1
            edges.append(
                {
                    "id": edge_id or f"e{edge_seq}",
                    "from": source,
                    "to": target,
                    "label": label,
                }
            )

        for bucket in BFO_BUCKETS:
            bucket_id = bucket["id"]
            node_id = f"bfo:anchor:{bucket_id}"
            props = self._query_ontology_properties(bucket["iri"])
            detail: dict[str, Any] = {
                "iri": bucket["iri"],
                "bucket_id": bucket_id,
                "bucket_label": bucket["label"],
                "bucket_color": bucket["color"],
                "source": "oxigraph",
            }
            detail.update(props)
            add_node(
                node_id,
                bucket["label"],
                "bfo_anchor",
                f"BFO7 anchor: {bucket['label']}",
                detail,
            )

        context_classes, context_class_edges = self._query_context_ontology_classes(
            org_name, model_name
        )
        for class_row in context_classes:
            class_iri = class_row["iri"]
            short = class_iri.rsplit("/", 1)[-1]
            node_id = f"onto:{short}"
            detail = {
                "iri": class_iri,
                "label": class_row["label"],
                "source": "oxigraph",
                "parent": class_row.get("parent", ""),
            }
            if class_row.get("bucket_id"):
                detail["bucket_id"] = class_row["bucket_id"]
            detail.update(self._query_ontology_properties(class_iri))
            add_node(
                node_id,
                class_row["label"],
                "ontology_class",
                f"Ontology class: {class_row['label']}",
                detail,
            )
        for child_iri, parent_iri, edge_label in context_class_edges:
            child_id = f"onto:{child_iri.rsplit('/', 1)[-1]}"
            if parent_iri in _BFO_ANCHOR_IRIS:
                parent_bucket = _BFO_IRI_TO_BUCKET.get(parent_iri)
                parent_id = f"bfo:anchor:{parent_bucket}" if parent_bucket else None
            else:
                parent_short = parent_iri.rsplit("/", 1)[-1]
                parent_id = f"onto:{parent_short}"
                if parent_id not in seen_nodes:
                    parent_label = parent_short
                    parent_props = self._query_ontology_properties(parent_iri)
                    if parent_props.get("rdfs_label"):
                        parent_label = parent_props["rdfs_label"]
                    parent_bucket = self.resolve_bucket_id(parent_iri)
                    parent_detail: dict[str, Any] = {
                        "iri": parent_iri,
                        "label": parent_label,
                        "source": "oxigraph",
                        "parent": "",
                    }
                    if parent_bucket:
                        parent_detail["bucket_id"] = parent_bucket
                    parent_detail.update(parent_props)
                    add_node(
                        parent_id,
                        parent_label,
                        "ontology_class",
                        f"Ontology class: {parent_label}",
                        parent_detail,
                    )
            if parent_id:
                add_edge(child_id, parent_id, edge_label)

        context_id = f"context:{org_name}/{model_name}"
        add_node(
            context_id,
            f"{org_name}/{model_name}",
            "context",
            f"Active org/model context: {org_name}/{model_name}",
            {
                "org": org_name,
                "model": model_name,
                "source": "routing",
                "iri": f"{ABID}ModelContext",
            },
        )

        setting_keys = (
            "workspace_root",
            "harness",
            "active_org",
            "active_model",
            "default_model",
            "opencode_bin",
            "pi_bin",
        )
        for key in setting_keys:
            value = settings.get(key, "").strip()
            if not value:
                continue
            node_id = f"setting:{key}"
            short = value if len(value) <= 28 else f"{value[:25]}..."
            add_node(
                node_id,
                short,
                "settings",
                f"{key}: {value}",
                {"key": key, "value": value, "source": "sqlite"},
            )
            if key in ("active_org", "active_model"):
                add_edge(node_id, context_id, "active")

        graph_iri = self._context_graph(org_name, model_name).value
        mc_result = self.query(
            f"""
SELECT ?orgName ?modelName ?modelUri WHERE {{
  GRAPH <{graph_iri}> {{
    ?mc a <{MODEL_CONTEXT.value}> ;
        <{MODEL_NAME.value}> ?modelName ;
        <{MODEL_URI.value}> ?modelUri .
    OPTIONAL {{
      ?mc <{BELONGS_TO_ORG.value}> ?org .
      ?org <{ORG_NAME.value}> ?orgName .
    }}
  }}
}}
LIMIT 1
"""
        )
        if mc_result["type"] == "solutions" and mc_result["rows"]:
            row = mc_result["rows"][0]
            add_node(
                context_id,
                f"{org_name}/{model_name}",
                "context",
                f"ModelContext: {row.get('modelUri', context_id)}",
                {
                    "org": row.get("orgName") or org_name,
                    "model": row.get("modelName") or model_name,
                    "model_uri": row.get("modelUri", ""),
                    "source": "oxigraph",
                },
            )

        route_result = self.query(
            f"""
SELECT ?route ?section ?agent ?harness ?modelHint ?bucket ?bucketLabel WHERE {{
  GRAPH <{graph_iri}> {{
    ?route <{FOR_SECTION.value}> ?section ;
           <{HARNESS_AGENT.value}> ?agent .
    OPTIONAL {{ ?route <{USES_HARNESS.value}> ?harness . }}
    OPTIONAL {{ ?route <{HARNESS_MODEL.value}> ?modelHint . }}
    OPTIONAL {{ ?route <{MAPS_TO_BFO_PROCESS.value}> ?bucket . }}
  }}
  OPTIONAL {{
    GRAPH <{SYSTEM_GRAPH.value}> {{
      ?bucket <{RDFS_LABEL.value}> ?bucketLabel .
    }}
  }}
}}
ORDER BY ?section
"""
        )
        lm_by_ref: dict[str, str] = {}
        lm_meta_by_ref: dict[str, dict[str, str]] = {}
        lm_realizabilities = self._query_language_model_realizabilities(
            org_name, model_name
        )
        route_by_section: dict[str, dict[str, str]] = {}
        for lm in self.query_language_models(org_name, model_name):
            ref = lm.get("model_ref", "")
            if ref:
                lm_by_ref[ref] = f"lm:{ref}"
                lm_meta_by_ref[ref] = lm

        if route_result["type"] == "solutions":
            for row in route_result["rows"]:
                section = row.get("section", "").strip() or "route"
                route_uri = row.get("route", "").strip()
                route_id = f"route:{section}"
                agent = row.get("agent", "")
                harness = row.get("harness", "")
                model_hint = row.get("modelHint", "")
                bucket = row.get("bucket", "")
                bucket_label = row.get("bucketLabel", "")
                route_by_section[section] = {
                    "agent": agent,
                    "harness": harness,
                    "model_hint": model_hint,
                    "bucket": bucket,
                    "bucket_label": bucket_label,
                }
                route_detail: dict[str, Any] = {
                    "section": section,
                    "agent": agent,
                    "harness": harness,
                    "model_hint": model_hint,
                    "route_uri": route_uri,
                    "source": "oxigraph",
                    "iri": f"{ABID}SectionRoute",
                }
                if bucket:
                    route_detail["bucket_iri"] = bucket
                add_node(
                    route_id,
                    f"{section} → {agent}",
                    "route",
                    f"SectionRoute {section}: agent={agent}, harness={harness}",
                    route_detail,
                )
                add_edge(context_id, route_id, "hasRoute")
                if bucket:
                    bucket_short = bucket.rsplit("/", 1)[-1]
                    bucket_id = _BFO_IRI_TO_BUCKET.get(bucket)
                    route_bucket_node = (
                        f"bfo:anchor:{bucket_id}"
                        if bucket_id and f"bfo:anchor:{bucket_id}" in seen_nodes
                        else f"bfo:{bucket_short}"
                    )
                    bucket_detail: dict[str, Any] = {
                        "iri": bucket,
                        "label": bucket_label,
                        "source": "oxigraph",
                    }
                    if bucket_id:
                        bucket_detail["bucket_id"] = bucket_id
                    bucket_detail.update(self._query_ontology_properties(bucket))
                    if route_bucket_node not in seen_nodes:
                        add_node(
                            route_bucket_node,
                            bucket_label or bucket_short,
                            "bfo_bucket",
                            f"BFO7 bucket: {bucket}",
                            bucket_detail,
                        )
                    add_edge(route_id, route_bucket_node, "mapsToBfoProcess")
                if model_hint and model_hint in lm_by_ref:
                    add_edge(route_id, lm_by_ref[model_hint], "harnessModel")

        for lm in self.query_language_models(org_name, model_name):
            ref = lm.get("model_ref", "")
            if not ref:
                continue
            lm_id = f"lm:{ref}"
            add_node(
                lm_id,
                lm.get("label") or _short_model_label(ref),
                "language_model",
                f"LanguageModel: {ref} ({lm.get('hosted_at', '')})",
                {
                    "model_ref": ref,
                    "label": lm.get("label", ""),
                    "hosted_at": lm.get("hosted_at", ""),
                    "can_realize": lm_realizabilities.get(ref, []),
                    "source": "oxigraph",
                    "iri": f"{ABI}LanguageModel",
                },
            )
            add_edge(context_id, lm_id, "LanguageModel")

        limited_chats = chats[:chat_limit]
        chat_ids = {chat["id"] for chat in limited_chats}
        limited_messages = [
            message for message in messages if message.get("chat_id") in chat_ids
        ][:message_limit]
        messages_by_chat: dict[str, list[dict[str, Any]]] = {}
        for message in limited_messages:
            messages_by_chat.setdefault(message["chat_id"], []).append(message)

        graph_chat_result = self.query(
            f"""
SELECT ?chat ?title ?section WHERE {{
  ?chat a <{CHAT_TYPE.value}> ;
        <{CHAT_TITLE.value}> ?title ;
        <{CHAT_SECTION.value}> ?section .
}}
"""
        )
        graph_chats_by_id: dict[str, str] = {}
        if graph_chat_result["type"] == "solutions":
            for row in graph_chat_result["rows"]:
                chat_uri = row.get("chat", "")
                if not chat_uri:
                    continue
                chat_id = chat_uri.rsplit("/", 1)[-1]
                if chat_id not in chat_ids:
                    continue
                graph_chat_id = f"graph:chat:{chat_id}"
                graph_chats_by_id[chat_id] = graph_chat_id
                title = row.get("title", chat_id)[:40]
                add_node(
                    graph_chat_id,
                    title,
                    "graph_chat",
                    f"Oxigraph chat: {title}",
                    {
                        "id": chat_id,
                        "title": row.get("title"),
                        "section": row.get("section"),
                        "uri": chat_uri,
                        "source": "oxigraph",
                        "iri": f"{ABID}Chat",
                    },
                )

        chat_process_by_id: dict[str, str] = {}
        for chat in limited_chats:
            chat_id = chat["id"]
            process_id = self._emit_chat_bfo_subgraph(
                chat,
                messages_by_chat.get(chat_id, []),
                context_id=context_id,
                lm_by_ref=lm_meta_by_ref,
                settings=settings,
                route_by_section=route_by_section,
                graph_chats_by_id=graph_chats_by_id,
                add_node=add_node,
                add_edge=add_edge,
            )
            chat_process_by_id[chat_id] = process_id

        graph_msg_result = self.query(
            f"""
SELECT ?msg ?chat ?role WHERE {{
  ?msg a <{MESSAGE_TYPE.value}> ;
       <{IN_CHAT.value}> ?chat ;
       <{MESSAGE_ROLE.value}> ?role .
}}
LIMIT {message_limit}
"""
        )
        if graph_msg_result["type"] == "solutions":
            for row in graph_msg_result["rows"]:
                msg_uri = row.get("msg", "")
                chat_uri = row.get("chat", "")
                if not msg_uri or not chat_uri:
                    continue
                msg_id = msg_uri.rsplit("/", 1)[-1]
                chat_id = chat_uri.rsplit("/", 1)[-1]
                if chat_id not in chat_ids:
                    continue
                graph_msg_id = f"graph:msg:{msg_id}"
                role = row.get("role", "")
                add_node(
                    graph_msg_id,
                    role or "message",
                    "graph_message",
                    f"Oxigraph message ({role})",
                    {
                        "id": msg_id,
                        "chat_id": chat_id,
                        "role": role,
                        "uri": msg_uri,
                        "source": "oxigraph",
                        "iri": f"{ABID}Message",
                    },
                )
                graph_chat_id = graph_chats_by_id.get(chat_id)
                process_id = chat_process_by_id.get(chat_id)
                if graph_chat_id:
                    add_edge(graph_chat_id, graph_msg_id, "inChat")
                if process_id:
                    add_edge(process_id, graph_msg_id, "hasMessage")

        for message in limited_messages:
            msg_id = message["id"]
            chat_id = message["chat_id"]
            sqlite_msg_id = f"sqlite:msg:{msg_id}"
            role = message.get("role", "")
            preview = str(message.get("content") or "")[:32]
            add_node(
                sqlite_msg_id,
                f"{role}: {preview}" if preview else role,
                "sqlite_message",
                f"SQLite message ({role})",
                {
                    "id": msg_id,
                    "chat_id": chat_id,
                    "role": role,
                    "content": message.get("content", ""),
                    "parts_count": len(message.get("parts") or []),
                    "sources_count": len(message.get("sources") or []),
                    "source": "sqlite",
                    "iri": f"{ABID}Message",
                },
            )
            process_id = chat_process_by_id.get(chat_id)
            storage_id = f"chat:{chat_id}:storage"
            if process_id:
                add_edge(process_id, sqlite_msg_id, "hasMessage")
            elif storage_id in seen_nodes:
                add_edge(storage_id, sqlite_msg_id, "message")
            graph_msg_id = f"graph:msg:{msg_id}"
            if graph_msg_id in seen_nodes:
                add_edge(sqlite_msg_id, graph_msg_id, "synced")

        settings_rows = [
            {"key": key, "value": settings.get(key, "")}
            for key in setting_keys
            if settings.get(key, "").strip()
        ]
        chat_rows = [
            {
                "id": chat["id"],
                "title": chat.get("title"),
                "section": chat.get("section"),
                "model": chat.get("model"),
                "updated_at": chat.get("updated_at"),
            }
            for chat in limited_chats
        ]
        message_rows = [
            {
                "id": message["id"],
                "chat_id": message["chat_id"],
                "role": message.get("role"),
                "content": (message.get("content") or "")[:120],
                "parts": len(message.get("parts") or []),
                "sources": len(message.get("sources") or []),
            }
            for message in limited_messages
        ]

        return {
            "nodes": nodes,
            "edges": edges,
            "buckets": self.list_bfo_buckets(),
            "tables": [
                {"name": "settings", "rows": settings_rows},
                {"name": "chats", "rows": chat_rows},
                {"name": "messages", "rows": message_rows},
            ],
            "meta": {
                "org": org_name,
                "model": model_name,
                "triple_count": self.stats()["triples"],
                "node_count": len(nodes),
                "edge_count": len(edges),
            },
        }


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


def _format_timestamp(value: Any) -> str:
    try:
        ts = float(value)
        return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return str(value) if value else "unknown"


def _sparql_literal(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _term_to_string(term: Any) -> str:
    if isinstance(term, NamedNode):
        return str(term.value)
    if isinstance(term, Literal):
        return str(term.value)
    return str(term)
