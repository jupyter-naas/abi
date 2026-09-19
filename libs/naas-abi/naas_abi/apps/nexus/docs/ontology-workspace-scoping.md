# Workspace ontology catalogs

Configure the ontology catalog under each workspace in the active engine YAML:

```yaml
modules:
  - module: naas_abi
    config:
      nexus_config:
        organizations:
          - name: Example
            slug: example
            workspaces:
              - name: Product safety
                slug: product-safety
                ontologies:
                  - adqcc:AdqccOntology.ttl
                  - bfo:bfo-core.ttl
                  - cco:AgentOntology.ttl
```

Use `module:filename.ttl` identifiers from registered ontology files. List every
shared dependency the workspace needs. `owl:imports` does not grant visibility.
Exact filenames and file paths remain supported for compatibility, but qualified
identifiers avoid ambiguity between files with the same name.

## Defaults and enforcement

- Missing `ontologies`, `null`, an empty list, or a workspace missing from the YAML
  seed gives an empty catalog.
- Catalog reads and export require `workspace_id` and authenticated workspace
  access. A path outside that workspace's catalog returns 404.
- Dictionary, statistics, file listings and graph expansion use the same allowlist.
- Graph imports resolve only against permitted local catalog files. References to
  an excluded import may remain visible where they are declared in an allowed
  source; its labels, definitions and hierarchy are not loaded from that import.
- Import caches include the permitted file set and file revisions. Refresh clears
  those local snapshots; no remote import is fetched through these catalog routes.
- Sidebar System, Ontology and Types filters only narrow the permitted catalog.
  They cannot grant access. There is no workspace ontology-permission editor yet.

## Presentation filters

System checkboxes select the union of files declaring those systems, their
subsystems and their processes. The Dashboard and dictionary use that same source
scope; ontology checkboxes intersect it, then type and search filters narrow the
list. A stale system selection returns no matches, never the entire catalog.
System ownership is explicit navigation metadata and file provenance, not an IRI
prefix. Shared types are counted once; metadata coverage uses only selected files.

The System canvas shows the navigation hierarchy and processes in scope. Detailed
term exploration can resolve shared ancestors from the workspace's permitted
catalog without changing that catalog's access policy.

## Migration and operations

Before enabling these defaults, add explicit lists for existing workspaces that
previously omitted the field. Decide each workspace's allowed catalog, including
shared BFO/CCO/ABI files. Existing explicit lists keep their current scope.

ABI selects `config.<ENV>.yaml` when present, otherwise `config.yaml`. Restart the
API after changing the active configuration; the engine caches it at startup.
An enabled module is also required: listing an unavailable file does not load its
module or grant access to another file.

This is the boundary for the Ontology catalog HTTP surface. It does not change
permissions on source-code/files APIs, the engine's internal ontology loading,
the instance graph/triple store, or agent tools. Those surfaces need their own
workspace authorization. Internal service calls with `catalog_refs=None` remain
trusted full-catalog enumeration and must not be exposed through HTTP.
