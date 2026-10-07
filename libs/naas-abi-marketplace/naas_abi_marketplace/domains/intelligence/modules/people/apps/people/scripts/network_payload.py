"""The Network view of a search: the search at the centre, what it matched, and the people.

The search is drawn with the person graph page (``graph_page/GraphPage.js``),
focused on an act of searching instead of a person, one hop per ring
(ontologies/modules/SearchOntology.ttl):

    act of searching  --has search match-->  search match  --matches in-->  act  <--  person  --works for-->  organization
    (process)                                (GDC)                          (process)

A match records where the query's words were found. Found in an act of working
(its organization, client, job title or mission, or a skill developed in it) or
an act of studying (school, program, degree), it leads to that act and on to
the person performing it; found in the person themselves (name, headline,
summary, a skill no act records), it leads straight to the person. So "EDF"
reaches Alexis Tourneux through the acts whose client is EDF R&D, Bernard
Fontana through the act he performs for EDF, and Claire Dusser through her
summary. Each person then leads to their current organization (the one the
People list shows), one node per organization, so who the search found at
each organization is drawn together.

The people are the search's own top results (same ranking, same facet), read
from this instance's graph with the people competency queries bound to each.
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Any

from naas_abi_core.services.dataset.DatasetService import DatasetService
from rdflib import Graph, Namespace, URIRef

from .graph_payload import _entity_node, build_graph_page_payload, compact_graph_id
from .graph_view import (
    SKILLS_QUERY,
    STUDYING_QUERY,
    WORKING_QUERY,
    graph_for,
    graph_view_config,
    person_by_slug,
    person_rows,
)
from .search_payload import _sentences, search
from .text import query_tokens, truncate, words

ABI = Namespace("http://ontology.naas.ai/abi/")
# How many of the top results the network draws: past a few dozen people the
# canvas is a hairball, and each person costs three bound queries.
NETWORK_SIZE = 30
# A match is labelled "Client: EDF R&D" when its value is this short, else by
# its field alone; the value is always in its properties.
SHORT_VALUE = 28
MATCHED_TEXT_LENGTH = 220
# Search, match, act, person, organization: the hops the view opens on.
NETWORK_DISTANCE = 4


def _hit(text: object, tokens: list[str]) -> bool:
    text_words = words(text)
    return any(word.startswith(token) for token in tokens for word in text_words)


def _matched_text(text: str, tokens: list[str]) -> str:
    """The sentence of ``text`` that holds the query's words, or all of it."""
    sentence = next(
        (sentence for sentence in _sentences(text) if _hit(sentence, tokens)), text
    )
    return truncate(sentence, MATCHED_TEXT_LENGTH)


def organization_id(name: str) -> str:
    return f"organization:{name.strip().casefold()}"


def search_root_id(query: str) -> str:
    return f"search:{query.strip() or '*'}"


def _summaries(graph: Graph, person: URIRef) -> list[dict[str, str]]:
    return [
        {
            "headline": str(graph.value(summary, ABI.headline_text) or ""),
            "content": str(graph.value(summary, ABI.summary_content) or ""),
        }
        for summary in graph.objects(person, ABI.hasProfileSummary)
    ]


def find_matches(
    person_label: str,
    tokens: list[str],
    *,
    working: list[dict[str, Any]],
    studying: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    summaries: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Where one person's records hold the query's words.

    Each match names the field, the text it was found in, and ``evidence``: the
    acts it was found in (compact ids), or the person's label when it was
    found in the person themselves.
    """
    # One match per field and text: three engagements for the same client
    # are one "Client: EDF R&D" match found in three acts.
    found: dict[tuple[str, str], dict[str, Any]] = {}

    def add(field: str, value: object, evidence: str | None) -> None:
        text = str(value or "").strip()
        if not (text and evidence and _hit(text, tokens)):
            return
        matched = _matched_text(text, tokens)
        match = found.setdefault(
            (field, matched), {"field": field, "text": matched, "evidence": []}
        )
        if evidence not in match["evidence"]:
            match["evidence"].append(evidence)

    add("Name", person_label, person_label)
    for summary in summaries:
        add("Headline", summary["headline"], person_label)
        add("Summary", summary["content"], person_label)
    for row in working:
        act = compact_graph_id(row.get("working"))
        add("Organization", row.get("orgLabel"), act)
        add("Client", row.get("clientLabel"), act)
        add("Job title", row.get("jobTitle") or row.get("roleLabel"), act)
        add("Mission", row.get("missionContent"), act)
    for row in studying:
        act = compact_graph_id(row.get("studying"))
        add("School", row.get("orgLabel"), act)
        add("Program", row.get("programName"), act)
        add("Degree", row.get("degreeLabel"), act)
    for row in skills:
        # A skill leads to the act it was developed in, or else to its bearer.
        add(
            "Skill",
            row.get("skillLabel"),
            compact_graph_id(row.get("working")) or person_label,
        )
    return list(found.values())


def _prop(uri: str, label: str, value: object) -> dict[str, str]:
    return {"uri": uri, "label": label, "value": str(value)}


def _props(*items: tuple[str, str, object]) -> list[dict[str, str]]:
    return [_prop(uri, label, value) for uri, label, value in items if value]


def _working_act(row: dict[str, Any]) -> dict[str, Any]:
    title = row.get("roleLabel") or row.get("jobTitle") or "Act of Working"
    org = row.get("orgLabel")
    return _entity_node(
        compact_graph_id(row["working"]),
        label=row.get("workingLabel") or (f"{title} @ {org}" if org else title),
        class_uri="abi:ActOfWorking",
        class_label="Act of Working",
        bfo_bucket="Process",
        is_working_hub=True,
        started_at=row.get("temporalStart"),
        ended_at=row.get("temporalEnd"),
        properties=_props(
            ("abi:isActOfWorkingOf", "worker", row.get("personLabel")),
            ("abi:forOrganization", "organization", org),
            ("abi:forClient", "client", row.get("clientLabel")),
            ("abi:job_title", "job title", row.get("jobTitle")),
            ("abi:hasFirstInstant", "start", row.get("temporalStart")),
            ("abi:hasLastInstant", "end", row.get("temporalEnd")),
        ),
    )


def _studying_act(row: dict[str, Any]) -> dict[str, Any]:
    program = row.get("programName") or row.get("roleLabel") or "Act of Studying"
    school = row.get("orgLabel")
    return _entity_node(
        compact_graph_id(row["studying"]),
        label=row.get("studyingLabel")
        or (f"{program} @ {school}" if school else program),
        class_uri="abi:ActOfStudying",
        class_label="Act of Studying",
        bfo_bucket="Process",
        started_at=row.get("temporalStart"),
        ended_at=row.get("temporalEnd"),
        properties=_props(
            ("abi:isActOfStudyingOf", "student", row.get("personLabel")),
            ("abi:forEducationalOrganization", "organization", school),
            ("abi:program_name", "program", row.get("programName")),
            ("abi:hasFirstInstant", "start", row.get("temporalStart")),
            ("abi:hasLastInstant", "end", row.get("temporalEnd")),
        ),
    )


def _relation(source: str, target: str, uri: str, label: str) -> dict[str, Any]:
    return {
        "from": source,
        "to": target,
        "predicateUri": uri,
        "predicateLabel": label,
        "canvas": True,
    }


def search_graph_payload(
    graph: Graph,
    people: list[dict[str, Any]],
    *,
    query: str,
    total: int,
) -> dict[str, Any]:
    """The graph page payload for a search: the act of searching, its matches,
    the acts they were found in, the people performing them, and each person's
    current organization.

    ``people`` are search results (``slug``, ``full_name``, ``organization``).
    Someone with no match the canvas can draw (not in the graph, or a search
    with no words) is tied to the search directly, so nobody found is left out.
    """
    tokens = query_tokens(query)
    root = search_root_id(query)
    roster = [
        {
            "personLabel": found.get("full_name") or found["slug"],
            "organizationLabel": found.get("organization"),
        }
        for found in people
    ]
    payload = build_graph_page_payload(roster)
    slugs = {found.get("full_name") or found["slug"]: found["slug"] for found in people}
    for person in payload["people"]:
        person["slug"] = slugs.get(person["id"])

    entities: dict[str, dict[str, Any]] = {}
    relations: list[dict[str, Any]] = []

    # Each person's current organization, as the People list shows it: one node
    # per organization, so the people a search found there are drawn together.
    for found in people:
        organization = (found.get("organization") or "").strip()
        if not organization:
            continue
        org_id = organization_id(organization)
        node = entities.setdefault(
            org_id,
            _entity_node(
                org_id,
                label=organization,
                class_uri="abi:Organization",
                class_label="Organization",
                bfo_bucket="Material Entity",
                properties=_props(("rdfs:label", "name", organization)),
            ),
        )
        # Drawn in place of the node's colour (the People list shows the same).
        if found.get("organization_logo") and not node.get("image"):
            node["image"] = found["organization_logo"]
        relations.append(
            _relation(
                found.get("full_name") or found["slug"],
                org_id,
                "abi:worksFor",
                "works for",
            )
        )

    index = 0
    for found in people:
        label = found.get("full_name") or found["slug"]
        person = person_by_slug(graph, found["slug"]) if tokens else None
        matches: list[dict[str, Any]] = []
        acts: dict[str, dict[str, Any]] = {}
        if person is not None:
            rows = {
                name: person_rows(graph, name, person)
                for name in (WORKING_QUERY, STUDYING_QUERY, SKILLS_QUERY)
            }
            for row in rows[WORKING_QUERY]:
                if row.get("working"):
                    acts.setdefault(compact_graph_id(row["working"]), _working_act(row))
            for row in rows[STUDYING_QUERY]:
                if row.get("studying"):
                    acts.setdefault(
                        compact_graph_id(row["studying"]), _studying_act(row)
                    )
            matches = find_matches(
                label,
                tokens,
                working=rows[WORKING_QUERY],
                studying=rows[STUDYING_QUERY],
                skills=rows[SKILLS_QUERY],
                summaries=_summaries(graph, person),
            )

        tied = False
        for match in matches:
            evidence = [
                node for node in match["evidence"] if node in acts or node == label
            ]
            if not evidence:
                continue
            index += 1
            match_id = f"{root}/match/{index}"
            value = match["text"]
            entities[match_id] = _entity_node(
                match_id,
                label=f"{match['field']}: {value}"
                if len(value) <= SHORT_VALUE
                else match["field"],
                class_uri="abi:SearchMatch",
                class_label="Search Match",
                bfo_bucket="GDC",
                properties=_props(
                    ("abi:matched_field", "field", match["field"]),
                    ("abi:matched_text", "matched text", value),
                    ("abi:isSearchResultOf", "person", label),
                ),
            )
            relations.append(
                _relation(root, match_id, "abi:hasSearchMatch", "has search match")
            )
            for node in evidence:
                relations.append(
                    _relation(match_id, node, "abi:matchesIn", "matches in")
                )
                if node in acts and node not in entities:
                    entities[node] = acts[node]
                    act_class = acts[node]["classLabel"]
                    relations.append(
                        _relation(
                            label,
                            node,
                            "abi:hasActOfWorking"
                            if act_class == "Act of Working"
                            else "abi:hasActOfStudying",
                            "has act of working"
                            if act_class == "Act of Working"
                            else "has act of studying",
                        )
                    )
            tied = True
        if not tied:
            relations.append(
                _relation(root, label, "abi:hasSearchResult", "has search result")
            )

    match_count = index
    entities[root] = _entity_node(
        root,
        label=query.strip() or "Everyone",
        class_uri="abi:ActOfSearching",
        class_label="Act of Searching",
        bfo_bucket="Process",
        properties=_props(
            ("abi:query_text", "query", query.strip() or "(everyone)"),
            ("abi:result_count", "people found", str(total)),
            ("abi:result_shown", "people drawn", str(len(people))),
            ("abi:match_count", "matches", str(match_count)),
        ),
    )
    return {
        **payload,
        "entities": sorted(entities.values(), key=lambda entity: entity["label"]),
        "relations": relations,
        "allRelations": relations,
    }


def network_view_config(config: dict[str, Any]) -> dict[str, Any]:
    """The graph page's settings for a search: rings, no time filter, filters
    tucked away in the settings panel, kept apart from the profile's."""
    view_config = deepcopy(graph_view_config(config))
    graph = view_config["graph"]
    graph.update(
        layout="rings",
        # One sector per organization: who the search found there, together.
        ring_cluster_class="Organization",
        temporal_filter=False,
        default_view="2d",
        default_distance=NETWORK_DISTANCE,
        max_distance=NETWORK_DISTANCE,
        params_session_key="people-search-graph-params-v1",
        # Thirty people's rings need to zoom further out than one person.
        scale={**graph.get("scale", {}), "min": 0.08},
    )
    defaults = graph.setdefault("view_defaults", {})
    for view in ("2d", "3d"):
        defaults[view] = {
            **defaults.get(view, {}),
            "filters": False,
            "physics": False,
            "legend": False,
        }
    return view_config


@lru_cache(maxsize=32)
def _cached_payload(
    graph: Graph,
    people: tuple[tuple[str, str, str, str], ...],
    query: str,
    total: int,
) -> dict[str, Any]:
    # The graph is the one graph_for() keeps until its file changes, so a
    # rebuilt graph is a new key.
    return search_graph_payload(
        graph,
        [
            {
                "slug": slug,
                "full_name": name,
                "organization": organization,
                "organization_logo": logo,
            }
            for slug, name, organization, logo in people
        ],
        query=query,
        total=total,
    )


def network(
    service: DatasetService,
    config: dict[str, Any],
    *,
    query: str = "",
    facet: str = "",
) -> dict[str, Any]:
    """The search's top results as a graph page payload, focused on the search."""
    network_config = {
        **config,
        "search": {**config["search"], "page_size": NETWORK_SIZE},
    }
    found = search(service, network_config, query=query, facet=facet, page=1)
    people = tuple(
        (
            hit["slug"],
            hit.get("full_name") or hit["slug"],
            hit.get("organization") or "",
            hit.get("organization_logo") or "",
        )
        for hit in found["results"]
    )
    data = _cached_payload(graph_for(config), people, query.strip(), found["total"])
    return {
        "query": found["query"],
        "facet": found["facet"],
        "total": found["total"],
        "shown": len(people),
        "root": search_root_id(query),
        "data": data,
        "config": network_view_config(config),
    }
