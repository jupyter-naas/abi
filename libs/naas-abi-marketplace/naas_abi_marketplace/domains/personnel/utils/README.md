# Personnel utilities

Small, dependency-free helpers shared across the personnel bucket — pipelines, demo graph
scripts, and cockpit exporters. Nothing here touches services or I/O; import freely from
any personnel code path.

## Layout

```
utils/
├── individual_uri.py   # mint and compact personnel individual IRIs
├── README.md           # this file
└── AGENTS.md           # guidance for coding agents
```

## Individual URI helpers (`individual_uri.py`)

Personnel individuals are minted under a single namespace:

```
http://ontology.naas.ai/personnel/{uuid}
```

That matches `ABIModule.Configuration.ontology_namespace` in the bucket module and keeps
demo data, graph exports, and UI payloads aligned on one IRI shape.

| Symbol | Purpose |
|---|---|
| `PERSONNEL_ONTOLOGY` | Base namespace (`http://ontology.naas.ai/personnel/`) |
| `DEMO_UUID_NS` | Fixed UUID namespace for deterministic demo seeds |
| `personnel_individual_uri(seed=None)` | Mint a full IRI. With *seed*, returns a stable uuid5 for idempotent demo writes; without, a fresh uuid4 |
| `uuid_part(uri)` | Extract the trailing segment; validates UUID form when possible |
| `compact_personnel(uri)` | Shorthand for UI payloads: `personnel:{uuid}` |

### When to use a seed

Pass a seed when the same logical entity must get the same IRI across runs — demo graph
generation, repeatable exports, or tests that assert on fixed triples. Omit the seed when
creating genuinely new individuals at runtime.

### Compact IDs in the cockpit

The graph page shows nodes with compact ids (`personnel:…`, `abi:…`) instead of full HTTP
IRIs. `apps/cockpit/graph_payload.compact_graph_id()` prefixes known namespaces locally and
falls back to `compact_personnel()` for anything else under the personnel ontology.

## Import paths

Prefer the submodule import when only one helper is needed:

```python
from naas_abi_marketplace.domains.personnel.utils.individual_uri import (
    personnel_individual_uri,
)
```

Re-exports are available from the package root:

```python
from naas_abi_marketplace.domains.personnel.utils import compact_personnel
```
