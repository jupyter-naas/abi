#!/usr/bin/env python3
"""Run personnel SPARQL queries against the demo TTL and write app JSON.

Reads ``data/graph/personnel_demo.ttl``, executes the competency
queries from ``ontologies/queries/PersonnelSparqlQueries.ttl`` (GRAPH wrappers
stripped for local rdflib), and writes directly to the committed cockpit tree::

    apps/cockpit/web/data/entities/_demo/source/   # one file per query
    apps/cockpit/web/data/entities/_demo/<page>/  # page aggregates

Requires ``generate_demo_graph.py`` to have run first::

    python scripts/generate_demo_graph.py
    python scripts/export_demo_apps_from_graph.py
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from pathlib import Path

from rdflib import Graph, Literal

from naas_abi_marketplace.domains.personnel.apps.cockpit.graph_payload import (
    build_graph_page_payload,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.log_payload import (
    build_ledger_log_entries,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.paths import (
    ENTITY_DEMO,
    GRAPH_FILE,
    WEB_DATA,
)

PERSONNEL_ROOT = Path(__file__).resolve().parents[1]
QUERIES_TTL = (
    PERSONNEL_ROOT / "ontologies" / "queries" / "PersonnelSparqlQueries.ttl"
)
SOURCE = ENTITY_DEMO / "source"

SCHEMA = "1.0"
ENTITY_ID = "_demo"
GRAPH_IRI = "http://ontology.naas.ai/graph/personnel"


def _now_version() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M")


def _envelope(records: list, **extra) -> dict:
    body = {
        "schema_version": SCHEMA,
        "data_version": _now_version(),
        "entity_id": ENTITY_ID,
        "source": str(GRAPH_FILE.relative_to(PERSONNEL_ROOT)),
        "records": records,
    }
    body.update(extra)
    return body


def _dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  wrote {path.relative_to(PERSONNEL_ROOT)}")


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
    blocks = re.split(r"\nintentMapping:\w+Query\s+a\s+intentMapping:TemplatableSparqlQuery\s*;", ttl_text)
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
        except Exception:
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


def _run_select(graph: Graph, sparql: str) -> list[dict]:
    result = graph.query(sparql)
    keys = [str(v) for v in result.vars] if result.vars else []
    return [_row_to_dict(row, keys) for row in result]


def _age_years(iso: str, today: date | None = None) -> int:
    today = today or date.today()
    y, m, d = (int(x) for x in iso.split("-"))
    born = date(y, m, d)
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _age_pyramid_from_births(births: list[dict], sex_by_person: dict[str, str]) -> list[dict]:
    bands = ["<25", "25-34", "35-44", "45-54", "55+"]
    counts = {b: {"Male": 0, "Female": 0, "Other": 0} for b in bands}
    seen: set[str] = set()
    for b in births:
        person = b.get("personLabel")
        temporal = b.get("temporalLabel")
        if not person or not temporal or person in seen:
            continue
        seen.add(person)
        try:
            age = _age_years(str(temporal)[:10])
        except ValueError:
            continue
        if age < 25:
            band = "<25"
        elif age < 35:
            band = "25-34"
        elif age < 45:
            band = "35-44"
        elif age < 55:
            band = "45-54"
        else:
            band = "55+"
        sex = sex_by_person.get(person, "Other")
        if sex not in counts[band]:
            sex = "Other"
        counts[band][sex] += 1
    return [{"band": b, **counts[b]} for b in bands]


def main() -> None:
    if not GRAPH_FILE.exists():
        raise SystemExit(
            f"Missing {GRAPH_FILE}. Run scripts/generate_demo_graph.py first."
        )

    print(f"Loading {GRAPH_FILE.relative_to(PERSONNEL_ROOT)}…")
    graph = Graph()
    graph.parse(GRAPH_FILE, format="turtle")
    print(f"  {len(graph)} triples")

    templates = _parse_query_templates(QUERIES_TTL.read_text(encoding="utf-8"))
    print(f"  {len(templates)} SPARQL templates")

    # --- source: one JSON per query -----------------------------------------
    print("source/")
    source_rows: dict[str, list[dict]] = {}
    arg_overrides = {
        "find_employees_by_status": {"status_value": "active"},
        "find_employees_by_organization": {"organization_name": ""},
        "find_positions_by_title": {"job_title": ""},
        "find_person_birth_lineage": {"person_name": "Ravenel"},
        "find_employee_by_id": {"employee_id": "E-10428"},
    }
    for label, template in templates.items():
        sparql = _strip_graph(_fill_args(template, **arg_overrides.get(label, {})))
        rows = _run_select(graph, sparql)
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
                    "registrationLabel": "registrationLabel",
                    "declaration": "declaration",
                    "birth": "birth",
                    "birthLabel": "birthLabel",
                    "site": "site",
                    "siteLabel": "siteLabel",
                    "temporal": "temporal",
                    "temporalLabel": "temporalLabel",
                    "record": "record",
                    "recordLabel": "recordLabel",
                    "sex": "sex",
                    "sexLabel": "sexLabel",
                    "eyeColor": "eyeColor",
                    "eyeColorLabel": "eyeColorLabel",
                    "motherLabel": "motherLabel",
                    "fatherLabel": "fatherLabel",
                    "declarantLabel": "declarantLabel",
                    "declaredOn": "declaredOn",
                    "declaredContent": "declaredContent",
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
        _dump(SOURCE / f"{label}.json", _envelope(normalized, query=label))

    # Biological sex for pyramid (not in birth registration SELECT).
    sex_q = _strip_graph(
        """
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX bfo:  <http://purl.obolibrary.org/obo/>
        PREFIX personnel: <http://ontology.naas.ai/personnel/>
        SELECT ?personLabel ?sexLabel WHERE {
          ?sex a personnel:BiologicalSex ; rdfs:label ?sexLabel ; bfo:BFO_0000197 ?person .
          ?person rdfs:label ?personLabel .
        }
        """
    )
    sex_by_person = {
        r["personLabel"]: r["sexLabel"]
        for r in _run_select(graph, sex_q)
        if r.get("personLabel") and r.get("sexLabel")
    }

    # --- page datasets ------------------------------------------------------
    print("web/data/entities/_demo/")
    active = source_rows.get("find_active_employees", [])
    by_status_all = source_rows.get("find_employees_by_status", [])
    # Re-query all statuses for mix: run without status filter approximation —
    # use active list + on-leave/notice from a broader query.
    status_all_sparql = _strip_graph(
        """
        PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX abi:  <http://ontology.naas.ai/abi/>
        PREFIX personnel: <http://ontology.naas.ai/personnel/>
        SELECT DISTINCT ?personLabel ?employeeId ?jobTitle ?hireDate ?statusValue ?organizationLabel
        WHERE {
          ?person rdf:type abi:Person ;
                  personnel:hasEmploymentRecord ?record .
          ?record personnel:employee_id ?employeeId .
          OPTIONAL { ?person rdfs:label ?personLabel . }
          OPTIONAL { ?record personnel:hire_date ?hireDate . }
          OPTIONAL {
            ?person personnel:hasEmployeeRole ?role .
            ?role personnel:hasJobPosition ?position .
            ?position personnel:job_title ?jobTitle .
          }
          OPTIONAL {
            ?person personnel:hasEmploymentStatus ?status .
            ?status personnel:status_value ?statusValue .
          }
          OPTIONAL {
            ?person personnel:isEmployedBy ?org .
            ?org rdfs:label ?organizationLabel .
          }
        }
        ORDER BY ?personLabel
        """
    )
    roster_rows = []
    for row in _run_select(graph, status_all_sparql):
        roster_rows.append(
            {
                "personLabel": row.get("personLabel"),
                "employee_id": row.get("employeeId"),
                "job_title": row.get("jobTitle"),
                "hire_date": row.get("hireDate"),
                "status_value": row.get("statusValue"),
                "organizationLabel": row.get("organizationLabel"),
            }
        )

    families = source_rows.get("find_headcount_by_job_family", [])
    # normalize jobFamily key
    family_records = [
        {
            "jobFamily": r.get("jobFamily") or r.get("job_family"),
            "headcount": int(r.get("headcount") or 0),
        }
        for r in families
    ]

    status_mix: dict[str, int] = {}
    for r in roster_rows:
        s = r.get("status_value") or "unknown"
        status_mix[s] = status_mix.get(s, 0) + 1

    births = source_rows.get("find_birth_registrations", [])
    open_positions = [
        {
            "job_title": r.get("job_title") or r.get("jobTitle"),
            "job_family": r.get("jobFamily") or r.get("job_family"),
            "descriptionLabel": r.get("descriptionLabel"),
        }
        for r in source_rows.get("find_open_job_positions", [])
    ]

    _dump(
        ENTITY_DEMO / "workforce" / "kpis.json",
        _envelope(
            [],
            kpis={
                "active_headcount": {
                    "value": len([r for r in roster_rows if r.get("status_value") == "active"])
                },
                "on_leave": {
                    "value": len(
                        [r for r in roster_rows if r.get("status_value") == "on-leave"]
                    )
                },
                "notice_period": {
                    "value": len(
                        [
                            r
                            for r in roster_rows
                            if r.get("status_value") == "notice-period"
                        ]
                    )
                },
                "open_roles": {"value": len(open_positions)},
            },
        ),
    )
    _dump(ENTITY_DEMO / "workforce" / "roster.json", _envelope(roster_rows))
    _dump(ENTITY_DEMO / "workforce" / "by_job_family.json", _envelope(family_records))
    _dump(
        ENTITY_DEMO / "workforce" / "status_mix.json",
        _envelope(
            [{"status_value": k, "count": v} for k, v in sorted(status_mix.items())]
        ),
    )
    _dump(
        ENTITY_DEMO / "workforce" / "age_pyramid.json",
        _envelope(_age_pyramid_from_births(births, sex_by_person)),
    )


    _dump(ENTITY_DEMO / "logs" / "births.json", _envelope(births))
    # Kinship from lineage query (Jeremy family).
    kinship = []
    for r in source_rows.get("find_person_birth_lineage", []):
        if r.get("motherLabel") or r.get("fatherLabel"):
            kinship.append(
                {
                    "personLabel": r.get("personLabel"),
                    "motherLabel": r.get("motherLabel"),
                    "fatherLabel": r.get("fatherLabel"),
                    "declarantLabel": r.get("declarantLabel"),
                    "priorRegistration": r.get("priorRegistration"),
                }
            )
    _dump(ENTITY_DEMO / "logs" / "kinship.json", _envelope(kinship))
    _dump(
        ENTITY_DEMO / "logs" / "ledger.json",
        _envelope(build_ledger_log_entries(births, kinship)),
    )

    family_by_person = {
        (r.get("personLabel") or ""): r.get("jobFamily") or r.get("job_family")
        for r in source_rows.get("find_positions_by_title", [])
        if r.get("personLabel") and not r.get("vacant")
    }
    for row in roster_rows:
        if not row.get("job_family"):
            row["job_family"] = family_by_person.get(row.get("personLabel") or "")

    graph_payload = build_graph_page_payload(
        roster_rows,
        births,
        source_rows.get("find_working_processes", []),
    )
    _dump(
        ENTITY_DEMO / "graph" / "index.json",
        _envelope([], **graph_payload),
    )

    data_version = _now_version()
    pages = {
        "workforce": [
            "workforce/kpis.json",
            "workforce/roster.json",
            "workforce/by_job_family.json",
            "workforce/status_mix.json",
            "workforce/age_pyramid.json",
        ],
        "logs": [
            "logs/ledger.json",
        ],
        "graph": [
            "graph/index.json",
        ],
        "processes": [
            "processes/processes.json",
        ],
    }

    _dump(
        ENTITY_DEMO / "manifest.json",
        {
            "schema_version": SCHEMA,
            "data_version": data_version,
            "entity_id": ENTITY_ID,
            "graph": str(GRAPH_FILE.relative_to(PERSONNEL_ROOT)),
            "datasets": {"entity": "entity.json", "pages": pages},
        },
    )
    _dump(
        ENTITY_DEMO / "entity.json",
        {
            "schema_version": SCHEMA,
            "data_version": data_version,
            "entity_id": ENTITY_ID,
            "display_name": "Naas.ai",
            "organizationLabel": "Naas.ai",
        },
    )
    _dump(
        WEB_DATA / "globals" / "entities.json",
        {
            "schema_version": SCHEMA,
            "data_version": data_version,
            "entities": [
                {
                    "entity_id": ENTITY_ID,
                    "display_name": "Naas.ai",
                    "url_slug": "demo",
                    "entity_type": "organization",
                    "organizationLabel": "Naas.ai",
                }
            ],
        },
    )
    _dump(
        WEB_DATA / "globals" / "organizations.json",
        {
            "schema_version": SCHEMA,
            "data_version": data_version,
            "organizations": [
                {
                    "entity_id": ENTITY_ID,
                    "label": "Naas.ai",
                    "organizationLabel": "Naas.ai",
                    "organization_uri": "http://ontology.naas.ai/abi/Organization/demo",
                }
            ],
        },
    )
    print("done.")


if __name__ == "__main__":
    main()
