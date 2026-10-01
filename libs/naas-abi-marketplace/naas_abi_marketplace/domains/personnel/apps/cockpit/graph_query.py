"""Run the personnel competency queries on a graph and shape them for the cockpit.

Shared by the demo exporter, which writes the results to storage, and by any
app that wants the same payloads live from a graph it already holds - the
People Search profile's graph view reads ``graph_page_payload`` on request.
"""

from __future__ import annotations

import re

from naas_abi_marketplace.domains.personnel.apps.cockpit.graph_payload import (
    build_graph_page_payload,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.scripts.roster_builder import (
    build_roster_rows,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.scripts.workforce_metrics import (
    build_workforce_metrics,
)
from naas_abi_marketplace.domains.personnel.paths import PERSONNEL_ROOT
from rdflib import Graph, Literal, URIRef

QUERIES_TTL = PERSONNEL_ROOT / "ontologies" / "queries" / "PersonnelSparqlQueries.ttl"
GRAPH_IRI = "http://ontology.naas.ai/graph/personnel"
# The queries the graph page is built from. The rest feed other cockpit pages.
GRAPH_PAGE_QUERIES = (
    "find_employee_roster",
    "find_positions_by_title",
    "find_working_experiences",
    "find_skills_developed",
    "find_educations",
)


def _strip_graph(sparql: str) -> str:
    """Remove GRAPH <iri> { ... } wrappers so queries run on the default graph."""
    return re.sub(rf"GRAPH\s*<{re.escape(GRAPH_IRI)}>\s*\{{", "{", sparql)


def _fill_args(template: str, **kwargs: str) -> str:
    out = template
    for key, value in kwargs.items():
        out = out.replace("{{ " + key + " }}", value)
        out = out.replace("{{" + key + "}}", value)
    # Defaults for optional args left in templates.
    out = out.replace("{{ limit }}", "100")
    out = out.replace("{{limit}}", "100")
    out = out.replace("{{ job_title }}", "")
    out = out.replace("{{job_title}}", "")
    out = out.replace("{{ person_name }}", "")
    out = out.replace("{{person_name}}", "")
    out = out.replace("{{ organization_name }}", "")
    out = out.replace("{{organization_name}}", "")
    out = out.replace("{{ status_value }}", "active")
    out = out.replace("{{status_value}}", "active")
    out = out.replace("{{ employee_id }}", "E-10428")
    out = out.replace("{{employee_id}}", "E-10428")
    return out


def _parse_query_templates(ttl_text: str) -> dict[str, str]:
    """Extract rdfs:label → sparqlTemplate pairs from the queries TTL."""
    # Match each TemplatableSparqlQuery block loosely.
    queries: dict[str, str] = {}
    blocks = re.split(
        r"\nintentMapping:\w+Query\s+a\s+intentMapping:TemplatableSparqlQuery\s*;",
        ttl_text,
    )
    for block in blocks[1:]:
        label_m = re.search(r'rdfs:label\s+"([^"]+)"', block)
        tmpl_m = re.search(
            r'intentMapping:sparqlTemplate\s+"""(.*?)"""\s*;',
            block,
            flags=re.DOTALL,
        )
        if label_m and tmpl_m:
            queries[label_m.group(1)] = tmpl_m.group(1).strip()
    return queries


def _row_to_dict(row, keys: list[str]) -> dict:
    out: dict = {}
    for key in keys:
        try:
            val = row[key]
        except (KeyError, TypeError):
            val = getattr(row, key, None)
        if val is None:
            out[key] = None
        elif isinstance(val, Literal):
            out[key] = val.toPython()
            if hasattr(out[key], "isoformat"):
                out[key] = out[key].isoformat()
        else:
            out[key] = str(val)
    return out


def _run_select(
    graph: Graph, sparql: str, bindings: dict[str, URIRef] | None = None
) -> list[dict]:
    result = graph.query(sparql, initBindings=bindings or {})
    keys = [str(v) for v in result.vars] if result.vars else []
    return [_row_to_dict(row, keys) for row in result]


def load_query_templates() -> dict[str, str]:
    return _parse_query_templates(QUERIES_TTL.read_text(encoding="utf-8"))


def query_source_rows(
    graph: Graph,
    templates: dict[str, str] | None = None,
    *,
    labels: tuple[str, ...] | None = None,
    person: URIRef | None = None,
) -> dict[str, list[dict]]:
    """Competency query rows, keyed by query label, in cockpit field names.

    ``labels`` runs only those queries. ``person`` binds ``?person`` in each, so
    the rows are that one person's - complete, where the whole-graph run is
    capped at 500 rows per query, and fast on a large graph.
    """
    templates = templates if templates is not None else load_query_templates()
    if labels is not None:
        templates = {label: templates[label] for label in labels}
    bindings = {"person": person} if person is not None else None
    source_rows: dict[str, list[dict]] = {}
    arg_overrides = {
        "find_employees_by_status": {"status_value": "active"},
        "find_employees_by_organization": {"organization_name": ""},
        "find_positions_by_title": {"job_title": ""},
        "find_employee_by_id": {"employee_id": "E-10428"},
        "find_employee_roster": {"limit": "500"},
        "find_working_experiences": {"limit": "500"},
        "find_skills_developed": {"limit": "500"},
        "find_educations": {"limit": "500"},
    }
    for label, template in templates.items():
        sparql = _strip_graph(_fill_args(template, **arg_overrides.get(label, {})))
        rows = _run_select(graph, sparql, bindings)
        # Normalize keys toward cockpit field names.
        normalized = []
        for row in rows:
            item = {}
            for k, v in row.items():
                # camelCase / SPARQL var → friendly
                mapping = {
                    "personLabel": "personLabel",
                    "employeeId": "employee_id",
                    "jobTitle": "job_title",
                    "jobFamily": "jobFamily",
                    "hireDate": "hire_date",
                    "statusValue": "status_value",
                    "organizationLabel": "organizationLabel",
                    "descriptionLabel": "descriptionLabel",
                    "site": "site",
                    "siteLabel": "siteLabel",
                    "temporal": "temporal",
                    "temporalLabel": "temporalLabel",
                    "temporalStart": "temporalStart",
                    "temporalEnd": "temporalEnd",
                    "givenName": "givenName",
                    "familyName": "familyName",
                    "headcount": "headcount",
                    "working": "working",
                    "org": "org",
                    "orgLabel": "orgLabel",
                    "contract": "contract",
                    "contractLabel": "contractLabel",
                    "position": "position",
                    "positionLabel": "positionLabel",
                    "role": "role",
                    "roleLabel": "roleLabel",
                    "remuneration": "remuneration",
                    "remunerationLabel": "remunerationLabel",
                    "remunerationAmount": "remunerationAmount",
                    "remunerationCurrency": "remunerationCurrency",
                    "jobDescription": "jobDescription",
                    "jobDescriptionLabel": "jobDescriptionLabel",
                }
                item[mapping.get(k, k)] = v
            # Vacant flag for positions-by-title
            if label == "find_positions_by_title":
                item["vacant"] = item.get("personLabel") is None
            normalized.append(item)
        source_rows[label] = normalized
    return source_rows


def roster_and_kpis(
    source_rows: dict[str, list[dict]], *, org_label: str
) -> tuple[list[dict], str, dict]:
    """``(roster_rows, roster_source, kpis)`` for the organization named *org_label*."""
    employment_rows = [
        {
            "personLabel": row.get("personLabel"),
            "employee_id": row.get("employee_id"),
            "job_title": row.get("job_title"),
            "job_family": row.get("jobFamily") or row.get("job_family"),
            "role": row.get("role"),
            "hire_date": row.get("hire_date"),
            "status_value": row.get("status_value"),
            "organizationLabel": row.get("organizationLabel"),
        }
        for row in source_rows.get("find_employee_roster", [])
    ]
    roster_rows, roster_source = build_roster_rows(
        employment_rows,
        source_rows.get("find_working_experiences", []),
        org_label=org_label,
    )

    family_by_person = {
        (r.get("personLabel") or ""): r.get("jobFamily") or r.get("job_family")
        for r in source_rows.get("find_positions_by_title", [])
        if r.get("personLabel") and not r.get("vacant")
    }
    for row in roster_rows:
        if not row.get("job_family"):
            row["job_family"] = family_by_person.get(row.get("personLabel") or "")

    kpis, roster_rows = build_workforce_metrics(
        roster_rows,
        source_rows.get("find_working_experiences", []),
        source_rows.get("find_educations", []),
        org_label=org_label,
    )
    return roster_rows, roster_source, kpis


def graph_page_payload(
    graph: Graph, *, org_label: str, person: URIRef | None = None
) -> dict:
    """What the cockpit graph page renders: people, entities and their relations.

    With ``person``, only that person and what their acts reach.
    """
    source_rows = query_source_rows(graph, labels=GRAPH_PAGE_QUERIES, person=person)
    roster_rows, _, _ = roster_and_kpis(source_rows, org_label=org_label)
    return build_graph_page_payload(
        roster_rows,
        source_rows.get("find_working_experiences", []),
        source_rows.get("find_skills_developed", []),
        source_rows.get("find_educations", []),
    )
