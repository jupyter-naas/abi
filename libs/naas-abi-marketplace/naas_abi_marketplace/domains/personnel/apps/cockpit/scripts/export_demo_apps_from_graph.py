#!/usr/bin/env python3
"""Run personnel SPARQL queries against the demo TTL and write app JSON.

Reads ``graphs/demo/personnel.ttl``, executes competency queries, then:

1. Writes a **structure reference copy** under ``apps/cockpit/data/`` (committed).
2. Publishes the **runtime datasets** to ObjectStorage at
   ``personnel/apps/cockpit/data/`` (fs: ``.abi/storage/datastore/...``).

The dev server reads from ObjectStorage only. Regenerate with ``make demo-data``.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from naas_abi_marketplace.domains.personnel.apps.cockpit.config_loader import (
    load_config,
    load_default_entity,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.data_store import (
    publish_data_tree,
    runtime_storage_prefix,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.graph_payload import (
    build_graph_page_payload,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.log_payload import (
    build_ledger_log_rows,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.paths import (
    DATA_ROOT,
    DEFAULT_ENTITY_ID,
    DEFAULT_ENTITY_SLUG,
    ENTITY_DATA,
    GRAPH_FILE,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.processes_payload import (
    build_processes_page_payload,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.scripts.workforce_metrics import (
    build_workforce_metrics,
)
from naas_abi_marketplace.domains.personnel.paths import PERSONNEL_ROOT
from rdflib import Graph, Literal

QUERIES_TTL = (
    PERSONNEL_ROOT / "ontologies" / "queries" / "PersonnelSparqlQueries.ttl"
)

SCHEMA = "1.0"
ENTITY_ID = DEFAULT_ENTITY_ID
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


def _run_select(graph: Graph, sparql: str) -> list[dict]:
    result = graph.query(sparql)
    keys = [str(v) for v in result.vars] if result.vars else []
    return [_row_to_dict(row, keys) for row in result]


def main() -> None:
    if not GRAPH_FILE.exists():
        raise SystemExit(
            f"Missing {GRAPH_FILE}. Run make demo-graph first."
        )

    print(f"Loading {GRAPH_FILE.relative_to(PERSONNEL_ROOT)}…")
    graph = Graph()
    graph.parse(GRAPH_FILE, format="turtle")
    print(f"  {len(graph)} triples")

    templates = _parse_query_templates(QUERIES_TTL.read_text(encoding="utf-8"))
    print(f"  {len(templates)} SPARQL templates")

    # --- SPARQL query rows (in memory → page datasets) --------------------
    print("queries/")
    source_rows: dict[str, list[dict]] = {}
    arg_overrides = {
        "find_employees_by_status": {"status_value": "active"},
        "find_employees_by_organization": {"organization_name": ""},
        "find_positions_by_title": {"job_title": ""},
        "find_employee_by_id": {"employee_id": "E-10428"},
        "find_employee_roster": {"limit": "500"},
        "find_working_processes": {"limit": "500"},
        "find_skills_developed": {"limit": "500"},
        "find_acts_of_studying": {"limit": "500"},
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

    # --- page datasets ------------------------------------------------------
    print(f"data/entities/{ENTITY_ID}/")
    roster_rows = [
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

    family_by_person = {
        (r.get("personLabel") or ""): r.get("jobFamily") or r.get("job_family")
        for r in source_rows.get("find_positions_by_title", [])
        if r.get("personLabel") and not r.get("vacant")
    }
    for row in roster_rows:
        if not row.get("job_family"):
            row["job_family"] = family_by_person.get(row.get("personLabel") or "")

    org_label = load_default_entity().get("organizationLabel") or "Demo"
    kpis, roster_rows = build_workforce_metrics(
        roster_rows,
        source_rows.get("find_working_processes", []),
        source_rows.get("find_acts_of_studying", []),
        org_label=org_label,
    )

    _dump(
        ENTITY_DATA / "dashboard" / "kpis.json",
        _envelope([], kpis=kpis),
    )
    _dump(ENTITY_DATA / "dashboard" / "roster.json", _envelope(roster_rows))

    graph_payload = build_graph_page_payload(
        roster_rows,
        source_rows.get("find_working_processes", []),
        source_rows.get("find_skills_developed", []),
        source_rows.get("find_acts_of_studying", []),
    )
    _dump(
        ENTITY_DATA / "graph" / "index.json",
        _envelope([], **graph_payload),
    )
    logs_config = load_config()["logs"]
    mutation_started_at = datetime.now(UTC).isoformat()
    mutation_completed_at = datetime.now(UTC).isoformat()
    data_version = _now_version()
    _dump(
        ENTITY_DATA / "processes" / "processes.json",
        build_processes_page_payload(entity_id=ENTITY_ID, data_version=data_version),
    )
    _dump(
        ENTITY_DATA / "logs" / "ledger.json",
        _envelope(
            build_ledger_log_rows(
                source_rows.get("find_working_processes", []),
                source_rows.get("find_acts_of_studying", []),
                owner_person_id=logs_config["owner"]["person"]["entity_id"],
                owner_person_label=logs_config["owner"]["person"]["display_name"],
                owner_agent_id=logs_config["owner"]["agent"]["entity_id"],
                owner_agent_label=logs_config["owner"]["agent"]["display_name"],
                server_site_id=logs_config["server"]["site_id"],
                server_label=logs_config["server"]["display_name"],
                server_ip=logs_config["server"]["ip_address"],
                target_graph=logs_config["target_graph"],
                target_graph_label=logs_config["target_graph_label"],
                process_label=logs_config["process_label"],
                started_at=mutation_started_at,
                completed_at=mutation_completed_at,
                default_operation=logs_config["default_operation"],
                default_status=logs_config["default_status"],
            )
        ),
    )

    page_datasets = {
        "dashboard": [
            "dashboard/kpis.json",
            "dashboard/roster.json",
        ],
        "graph": [
            "graph/index.json",
        ],
        "processes": [
            "processes/processes.json",
        ],
        "logs": [
            "logs/ledger.json",
        ],
    }
    pages = {
        page["page_id"]: page_datasets[page["page_id"]]
        for page in load_config()["app"]["pages"]
        if page.get("enabled") and page["page_id"] in page_datasets
    }

    _dump(
        ENTITY_DATA / "manifest.json",
        {
            "schema_version": SCHEMA,
            "data_version": data_version,
            "entity_id": ENTITY_ID,
            "graph": str(GRAPH_FILE.relative_to(PERSONNEL_ROOT)),
            "datasets": {"pages": pages},
        },
    )
    _dump(
        DATA_ROOT / "globals" / "entities.json",
        {
            "schema_version": SCHEMA,
            "data_version": data_version,
            "entities": [
                {
                    "entity_id": ENTITY_ID,
                    "display_name": "Demo",
                    "url_slug": DEFAULT_ENTITY_SLUG,
                    "entity_type": "organization",
                    "is_default": True,
                    "organizationLabel": "Demo",
                    "organization_uri": "http://ontology.naas.ai/abi/Organization/demo",
                }
            ],
        },
    )
    print("done.")
    published = publish_data_tree(DATA_ROOT)
    print(
        f"  published {len(published)} files to object storage "
        f"({runtime_storage_prefix()}/)"
    )


if __name__ == "__main__":
    main()
