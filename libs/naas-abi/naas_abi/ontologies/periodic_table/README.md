# Periodic Table of Software

119 element vocabulary grounded in BFO 7 Buckets via ABI Ontology.

## Ontology chain

```
BFO -> BFO 7 Buckets -> ABI Ontology -> Periodic Table
```

## Layout

```
naas_abi/ontologies/
├── modules/
│   └── PeriodicTableOntology.ttl   # CANONICAL (owl:Ontology; Nexus sidebar)
└── periodic_table/
    ├── schema.ttl                  # authoring: section classes + properties
    ├── generate_elements.py        # regenerates elements/ + modules TTL
    ├── loader.py                   # rdflib loader (reads modules TTL)
    └── elements/
        ├── 001_Company.ttl
        └── … (119 authoring fragments; not under modules/)
```

Nexus `list_ontology_files` only keeps TTL paths that contain `modules`, are not under `sandbox`, and declare `owl:Ontology`. Element fragments stay outside `modules/` so they never become separate sidebar ontologies. `ABIModule.on_load` also drops authoring paths from `module.ontologies` so `EngineOntologyLoader` only loads the catalog file.

## Regenerate

From the ABI repo root:

```bash
uv run python libs/naas-abi/naas_abi/ontologies/periodic_table/generate_elements.py
```

## Named graph

Loaded at ABI API boot into `http://ontology.naas.ai/graph/abi-periodic-table`.

## Visualization app

Catalog app: `naas_abi/apps/periodic_table/` (`html:periodic_table_graph.html`). Standalone: `uv run python -m naas_abi.apps.periodic_table`.
