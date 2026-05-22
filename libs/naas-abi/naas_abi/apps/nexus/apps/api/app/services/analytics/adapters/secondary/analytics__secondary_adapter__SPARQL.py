"""SPARQL secondary adapter for the analytics service.

Loads one or more Turtle files into an in-memory :class:`rdflib.Graph`
and answers :meth:`AnalyticsPort.query_flat_events` with a single
SPARQL SELECT that materialises every ``nexus:Log`` together with its
session, user, workspace and (optional) page context.

The graph is re-parsed whenever any source TTL's ``mtime`` changes, so
hand-editing the fake-data TTL is enough to refresh the dashboard on
the next request — no API restart needed.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Iterable

from rdflib import Graph

from naas_abi.apps.nexus.apps.api.app.services.analytics.port import (
    AnalyticsPort,
    LogRecord,
)


# Single source-of-truth SPARQL query. Every analytics KPI is derived
# from this flat row set in :class:`AnalyticsService`.
FLAT_EVENTS_QUERY = """
PREFIX nexus: <http://ontology.naas.ai/nexus/>
PREFIX bfo:   <http://purl.obolibrary.org/obo/>

SELECT ?event_id ?event_name ?timestamp ?page_path ?page_title
       ?event_payload ?referrer ?session_id ?device ?browser ?country
       ?user_id ?user_email ?workspace_id ?workspace_name
WHERE {
  ?log a nexus:Log ;
       nexus:event_id ?event_id ;
       nexus:event_name ?event_name ;
       nexus:timestamp ?timestamp ;
       nexus:isLogOf ?session .
  OPTIONAL { ?log nexus:page_path     ?page_path }
  OPTIONAL { ?log nexus:page_title    ?page_title }
  OPTIONAL { ?log nexus:event_payload ?event_payload }
  OPTIONAL { ?log nexus:referrer      ?referrer }
  ?session nexus:session_id ?session_id .
  OPTIONAL { ?session nexus:device  ?device }
  OPTIONAL { ?session nexus:browser ?browser }
  OPTIONAL { ?session nexus:country ?country }
  OPTIONAL {
    ?session nexus:isSessionOf ?ws .
    ?ws nexus:workspace_id   ?workspace_id ;
        nexus:workspace_name ?workspace_name .
  }
  OPTIONAL {
    ?visit a nexus:VisitSession ;
           bfo:BFO_0000059 ?session ;
           bfo:BFO_0000057 ?user .
    ?user a nexus:User .
    OPTIONAL { ?user nexus:user_id ?user_id }
    OPTIONAL { ?user nexus:email   ?user_email }
  }
}
"""


class SPARQLAnalyticsAdapter(AnalyticsPort):
    def __init__(self, ttl_paths: Iterable[Path | str]):
        self._ttl_paths: list[Path] = [Path(p) for p in ttl_paths]
        if not self._ttl_paths:
            raise ValueError("SPARQLAnalyticsAdapter needs at least one TTL path")
        self._graph: Graph | None = None
        self._mtimes: dict[Path, float] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # AnalyticsPort                                                       #
    # ------------------------------------------------------------------ #

    def query_flat_events(self) -> list[LogRecord]:
        rows = self._ensure_graph().query(FLAT_EVENTS_QUERY)
        return [
            LogRecord(
                event_id=str(r.event_id),
                event_name=str(r.event_name),
                timestamp=str(r.timestamp),
                page_path=_str_or_none(r.page_path),
                page_title=_str_or_none(r.page_title),
                properties=_payload_to_dict(r.event_payload),
                referrer=_str_or_none(r.referrer),
                session_id=str(r.session_id),
                device=_str_or_none(r.device),
                browser=_str_or_none(r.browser),
                country=_str_or_none(r.country),
                user_id=_str_or_none(r.user_id),
                user_email=_str_or_none(r.user_email),
                workspace_id=_str_or_none(r.workspace_id),
                workspace_name=_str_or_none(r.workspace_name),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    # internals                                                           #
    # ------------------------------------------------------------------ #

    @property
    def ttl_paths(self) -> list[Path]:
        return list(self._ttl_paths)

    def _current_mtimes(self) -> dict[Path, float]:
        return {p: p.stat().st_mtime for p in self._ttl_paths}

    def _ensure_graph(self) -> Graph:
        with self._lock:
            now_mtimes = self._current_mtimes()
            if self._graph is None or now_mtimes != self._mtimes:
                g = Graph()
                for p in self._ttl_paths:
                    g.parse(p, format="turtle")
                self._graph = g
                self._mtimes = now_mtimes
            return self._graph


def _str_or_none(value) -> str | None:
    return None if value is None else str(value)


def _payload_to_dict(value) -> dict | None:
    if value is None:
        return None
    try:
        return json.loads(str(value))
    except (ValueError, TypeError):
        return {"raw": str(value)}
