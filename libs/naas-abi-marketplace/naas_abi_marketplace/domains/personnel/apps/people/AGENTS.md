# AGENTS — People Search

> Scope: `domains/personnel/apps/people/`. A configurable people directory over
> the personnel graph. See `README.md` for how to run and retarget it.

## The chain

```
data/demo/person/*/index.json          source (fictional, for the demo)
  -> pipelines/                        ActOfWorking, ActOfStudying, PersonProfile
  -> graphs/demo/personnel.ttl         the graph, ontology-backed
  -> ontologies/queries/*.ttl          competency queries
  -> dataset service (DuckLake)        nine typed tables in the `personnel` namespace
  -> api/ + web/                       this app
```

Every step is replaceable except the order. Never shortcut it by putting people
data in this folder: an app with its own copy of the directory is the fork this
app exists to prevent.

## The two contracts

1. **Configuration may not create behaviour.** `config.yaml` can reorder,
   rename, retitle, hide and point elsewhere. It cannot add a page or a profile
   section, because those are renderers. The registered ids live in two places
   and must change together:

   | Thing | Python | JavaScript |
   |---|---|---|
   | Pages | `config_loader.REGISTERED_PAGE_IDS` | `web/lib/registry.js` |
   | Profile sections | `config_loader.REGISTERED_SECTION_IDS` | `web/components/profile/sections.js` |

   `config_loader_test.py` asserts that every registered section is configured,
   so adding one to the renderer and forgetting `config.yaml` fails the suite.

2. **The browser never reads the warehouse.** Table names, the namespace and the
   privacy rules are dropped by `public_config()`. Requests go to
   `/api/personnel-people/*`, which decides what may be read. Do not add a route
   that takes a table name or a SQL fragment from the client.

## Adding a profile section

1. Write the renderer in `web/components/profile/sections.js` and add it to
   `SECTION_RENDERERS`.
2. Add its id to `REGISTERED_SECTION_IDS` in `config_loader.py`.
3. Add its table to `datasets.TABLES`, its shaping to `profile_payload._section_items`,
   and its rows to `scripts/export_people_from_graph.py`.
4. Add the competency query it reads to `ontologies/queries/PersonnelSparqlQueries.ttl`
   and register its label in `agents/PersonnelAgent.get_sparql_tools()`.
5. Add it to `config.yaml` with a label, an order and an `empty_text`.

If the graph cannot answer step 4, the section has no business existing yet.
Extend the ontology first.

## Rules

- **An empty section is an answer.** A person with no recommendations renders
  the configured `empty_text`. Never hide the section, and never fill it with a
  placeholder: "nothing recorded" and "we failed to load it" must not look alike.
- **Nothing is computed that a source did not state.** `years_of_experience` is
  a claim carried by the profile summary, not a sum over acts of working. A
  period shows the dates and the source's own duration label.
- **No contact details.** The exporter refuses an email address or a run of nine
  or more digits, and the test suite pins both. Eight digits pass so that
  `2018-2021` is not mistaken for a phone number.
- **Portraits are addresses, not bytes.** `people.photo_url` points at object
  storage or a published page. The demo ships abstract marks, not invented faces.
- **No branding in code.** The logo and the favicon come from `web/assets/` by way
  of `config.yaml`; with neither set, the app draws `brand.mark`. A hardcoded
  logo makes the app one client's, which is the opposite of the point.
- **SQL takes no client strings.** Values reaching `ds.sql_literal` are folded
  search words, a slug that matched `SLUG_PATTERN`, or a facet value read back
  out of the people table.

## Naming

Python package `people` · catalog id `personnel-people` · API prefix
`/api/personnel-people` · dataset namespace `personnel` · Nexus app id
`naas_abi_marketplace.domains.personnel:people`.

## Tests

```bash
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/domains/personnel -q
```

`datasets_test.py` runs against a real DuckLake warehouse in a temporary
directory. It is the only way the SQL, the types and the flush are actually
exercised, so do not replace it with a fake store.
