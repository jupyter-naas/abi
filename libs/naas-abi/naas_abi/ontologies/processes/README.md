# ABI Process Ledger

37 processes across 9 subsystems, 111 scoped steps, and one shared vocabulary.
The ledger uses `http://ontology.naas.ai/abi/` throughout.

The existing System → subsystem → process navigation, seven-bucket overview,
and detailed ontology view use these files directly.

- `*.ttl`: 38 Turtle ontologies loaded by the `naas_abi` module.
- `source_ledger.json`: the complete source process descriptions and bucket values.
- `process_ledger_manifest.json`: file list, stable process codes and source checksum.
- `build_process_ledger.py`: explicit regeneration; never runs at startup.
- `process_ledger_test.py`: syntax, structure, bucket mapping and provenance checks.

These remain draft schemas from a simulated ledger, not validated procedures or
records of executions. Existing modeling distinctions are preserved: software,
goals, triggers and status indicators are information; material hosts and roles
are separate. Quality/bearer mappings remain unresolved where the source does
not establish them.

## Use

Enable the existing `naas_abi` module. Its recursive ontology discovery includes
this directory. Workspace visibility is controlled by the normal ontology catalog.
Workspace visibility is controlled by the normal ontology catalog; BFO/CCO
foundations load through the usual module discovery path.
In Ontology, open System and select **ABI process ledger**.

## Rebuild and check

From the ABI repository root:

```sh
uv run python libs/naas-abi/naas_abi/ontologies/processes/build_process_ledger.py
uv run python libs/naas-abi/naas_abi/ontologies/processes/process_ledger_test.py
```

Edit the bundled source ledger to change a process, then rebuild and check.
Process IRIs use stable codes, so changing a display name preserves identity.
