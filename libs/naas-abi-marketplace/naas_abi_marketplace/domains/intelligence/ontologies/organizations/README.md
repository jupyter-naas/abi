# organizations — S2 intelligence

Vocabulary and process ledger for organizations: who they are, how they cooperate, and how they
restructure. Filed under `intelligence/ontologies/` because its deliverable is vocabulary — see
[`../../../AGENT.md`](../../../AGENT.md) for the filing rules and how ontology building works.

```
organizations/
├── __init__.py
└── ontologies/
    ├── modules/
    │   └── OrganizationOntology.ttl                (+ .py)   247 triples
    ├── processes/
    │   ├── OrganizationAllianceProcess.ttl         (+ .py)   157 triples
    │   └── OrganizationRestructuringProcess.ttl    (+ .py)   134 triples
    └── queries/
        └── OrganizationSparqlQueries.ttl                      10 queries
```

The generated `classes/` stubs do **not** land inside this module — they are written to
`intelligence/ontologies/classes/` (34 files), one level up. That is deterministic, not a mistake:
`onto2py` derives its output root by scanning the TTL path for the first path segment named
`ontologies` and stopping there (`onto2py.py:1928`). A module filed under a bucket's `ontologies/`
component folder has two such segments, and the bucket's wins. The generated imports are absolute
and resolve correctly either way, so this is a placement quirk rather than a break — but do not
"fix" it by moving the folder, because the next regeneration puts it straight back.

## The split

`OrganizationOntology.ttl` was one 379-line file mixing the organization taxonomy, the information
content entities that identify an organization, and nine "Act of …" process classes. It is now
three files along the line the BFO buckets already draw:

| File | Holds | Bucket |
|---|---|---|
| `modules/OrganizationOntology.ttl` | CCO organization taxonomy, website, ticker, industry, brand, capabilities, headquarters | WHO / HOW WE KNOW / WHY / WHERE |
| `processes/OrganizationAllianceProcess.ttl` | 6 alliance acts + the `StrategicAlliance` agreement hierarchy | WHAT + HOW WE KNOW |
| `processes/OrganizationRestructuringProcess.ttl` | merger, acquisition, subsidiary establishment + their records | WHAT + HOW WE KNOW |

**Why two process files and not nine.** The split is on what the act does to the organization, not
on the act's name. An **alliance** leaves every party a distinct legal entity; **restructuring**
changes the set of organizations or who controls whom. That is a real boundary a query has to
respect — a merged-away entity keeps its alliance history — whereas partnership-vs-joint-venture
is a difference of terms, not of kind. Both files import the module ontology, never the reverse.

**Acts and records are kept paired but distinct.** Each `abi:ActOf*` is the occurrent — it happens,
has participants, occupies an interval. Each `abi:StrategicAlliance` subclass is the continuant
document that records it and outlives it. Ask "who is allied with whom" over the acts, because only
acts carry participants; ask "what does the agreement say" over the records.

**Merger and acquisition are not "M&A".** Merger participants are symmetric
(`abi:hasMergingOrganization`). Acquisition is directional
(`abi:hasAcquiringOrganization` / `abi:hasAcquiredOrganization`). Modelling both through one
symmetric relation would make *who bought whom* unanswerable.

## Queries

Ten `intentMapping:TemplatableSparqlQuery` entries over
`GRAPH <http://ontology.naas.ai/graph/organizations>`:

| Query | Answers | Arguments |
|---|---|---|
| `find_organizations_by_name` | What do we know about this company? | `organization_name`, `limit` |
| `find_organizations_by_industry` | Who operates in this sector? | `industry_name`, `limit` |
| `find_organization_by_ticker` | Which company is this ticker? | `ticker_symbol` |
| `find_organization_headquarters` | Where is it based? | `organization_name`, `limit` |
| `find_alliances_by_organization` | Who is it allied with? | `organization_name`, `limit` |
| `find_alliances_by_type` | Show all joint ventures / licensing deals | `alliance_type`, `limit` |
| `find_alliance_agreements` | What agreements record those alliances? | `limit` |
| `find_acquisitions_by_organization` | Who bought whom? | `organization_name`, `limit` |
| `find_mergers` | Which organizations merged? | `limit` |
| `find_subsidiaries` | What does it own? | `organization_name`, `limit` |

Every term used in a `sparqlTemplate` is declared in one of the three ontologies or an upper
ontology they import, and every `{{ placeholder }}` has a matching `intentMapping:QueryArgument`
with a validation pattern.

**Subclass matching is written out explicitly.** The triple store runs no reasoner, so matching
`?x rdf:type abi:StrategicAlliance` would miss a document typed only `abi:JointVenture`. Queries
over a class hierarchy list the concrete subclasses in a `FILTER(?type IN (…))` instead. Adding a
new alliance subclass means updating those filters.

To wire these into an agent, follow `PersonnelAgent.get_tools()` — the module already declares
`naas_abi_core.modules.templatablesparqlquery` in `dependencies.modules`. There is no organizations
agent yet.

## Three pre-existing defects fixed in passing

The original file had never loaded. All three are worth knowing about because the same mistakes are
easy to repeat:

1. **The TTL did not parse.** It used `obo:` (4×) and `dcterms:` (4×) without declaring either
   prefix, so `rdflib` raised `BadSyntax` at line 48. `obo:` is now `bfo:` and `dcterms:` is now
   `dc:` — both already bound to the same namespaces.
2. **The ontologies sat outside the module's load path.** `BaseModule.on_load()` globs
   `<module_root>/ontologies/**/*.ttl`, and the module root is `organizations/`, so files at
   `organizations/modules/` were never discovered. They now live under
   `organizations/ontologies/`, which also makes the `abi:ontologyResource` paths resolve.
3. **`cco:ont00001102` was referenced without importing `FacilityOntology`**, where it is defined —
   the headquarters classes had no resolvable parent.

Two further changes were needed to pass the seven-buckets validator:

- **`TechnologicalCapabilities` / `HumanCapabilities`** traced only to `BFO_0000017` (realizable
  entity), which is one level above every bucket root. They now also subclass `bfo:BFO_0000016`
  (disposition) and carry an inheres-in restriction naming the organization as bearer. A capability
  is realized in acts and grounded in its bearer, so disposition is the right bucket.
- **20 object and data properties were added** — `hasAllianceParticipant`, the acquisition
  direction pair, `hasSubsidiaryOrganization`/`hasParentOrganization`, `hasIndustry`,
  `hasHeadquarters`, `ticker_symbol`, `website_url` and their inverses. The original declared
  classes but almost no relations between them, so nothing could be traversed. No class or property
  was removed: all 41 original terms survive.

## Regenerating

```bash
uv run python -m naas_abi_core.utils.onto2py \
  libs/naas-abi-marketplace/naas_abi_marketplace/domains/intelligence/ontologies/organizations/ontologies/modules/OrganizationOntology.ttl
uvx ruff check --fix <same dir> && uvx ruff format <same dir>
```

Expect `could not resolve owl:imports` warnings for `bfo-core.ttl` and the CCO mid-level
ontologies — they carry no locator annotations, so onto2py skips them by design. The TTL still
loads into the triple store in full.
