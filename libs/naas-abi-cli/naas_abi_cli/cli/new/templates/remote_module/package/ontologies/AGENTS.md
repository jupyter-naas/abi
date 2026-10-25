# `ontologies/` — AGENTS.md

> Scope: the ontologies of the `{{module_name_snake}}` module. See the module's [AGENTS.md](../AGENTS.md).

Every `.ttl` file here is sent to the engine's schema graph, as the ontologies of
an in-engine module are. The module never imports `naas_abi_core`: `run_module`
sends the files over NATS.

## Layout

```
ontologies/
├── modules/    {{module_name_pascal}}Ontology.ttl   shared classes and properties
└── sandbox/    work in progress: never sent
```

`modules/`, `processes/` and `queries/` follow the in-engine convention; any
folder works. `ontologies/**/*.ttl` is found recursively. A path with `sandbox`
in it (under `ontologies/`, any case) is skipped.

## When and how it is sent

- Each file is stored as `module/{{module_id}}/<path under ontologies/>`, e.g.
  `module/{{module_id}}/modules/{{module_name_pascal}}Ontology.ttl`. The engine accepts
  a module only under its own id.
- The module sends once discovery reports it `READY` or `DEGRADED`: never while
  `STAGED` (the generation behind a live one), and not at all if it is asked to
  drain first. A module run without discovery sends at start.
- A file whose content the engine already holds writes nothing; a changed file
  applies the diff (triples added and removed).
- Sending is in the background and never changes readiness. A failed load (the
  engine down or busy, invalid Turtle) is logged as an error
  (`naas_abi_sdk.ontologies`) and retried after 1 s, then twice as long, up to
  every minute, until it succeeds. Fix invalid Turtle and the next retry sends it.
- Loading is **additive**: a file you delete or rename stays in the schema graph
  (a rename loads the new file next to the old one). Remove stale triples with
  the engine's tools, not by deleting the file.

## Rules

- `ABIModule.dependencies` declares `triple_store`: a module with ontologies
  refuses to start without it. Remove every `.ttl` (or set `ontologies = ()`)
  to drop both.
- File and folder names use letters, digits, `_`, `.` and `-`, end in `.ttl`, and
  keep the whole `module/{{module_id}}/<path>` within 512 characters. The module
  refuses to start on a name the engine would refuse.
- **Absolute IRIs only**, stable, under `http://ontology.naas.ai/{{module_name_snake}}/`.
  A relative IRI resolves against `http://ontology.naas.ai/module/{{module_id}}/<path>`.
- Do not use the engine's own `http://triple-store.internal` vocabulary: the engine
  refuses the file (`INVALID_ARGUMENT`).
- One `owl:imports` statement per IRI. The engine does not resolve imports; the
  ABI ontologies are already in its schema graph.
- **Schema only.** Named individuals belong in your data. Anything in a `.ttl`
  here lands in the engine's live triple store.
- Reuse CCO and `abi:` classes before minting one; pair every relation with its
  inverse.

## Check it

```bash
uv run --with rdflib python -c "import rdflib, pathlib; [rdflib.Graph().parse(p) for p in pathlib.Path('.').rglob('*.ttl')]"
```

from this folder parses every file. With the engine up, the schema graph holds an `internal:Schema`
whose `filePath` is the `module/...` key once the module is `READY`.
