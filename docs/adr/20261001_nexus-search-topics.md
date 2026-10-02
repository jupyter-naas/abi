# Nexus search by topic

Status: Proposed

Date: 2026-10-01

## Context

The personnel module ships People Search (`domains/personnel/apps/people/`), a standalone app with its own home, results, profile and ontology pages, served in an iframe. Every new search "layer" (organizations, offerings, markets…) built this way repeats the same UI in a new app and leaves Nexus's own `/search` page aside. That page was a client-side aggregator of web engines and a label `CONTAINS` over the whole triple store, and the dock's Search button only opened the quick-open palette.

What differs between search layers is the data, not the screens: which class is searched, how it matches the typed text, what a hit shows, and what the detail lists. All of it can be stated as SPARQL over the graphs a workspace may read.

## Decision

Search in Nexus is organised by **topic**. A topic is data: a label, an icon, the ontology class it searches, and SPARQL SELECT templates, each with a **role** whose projected variables fill fixed UI slots:

| Role | Placeholders | Required | Optional |
|---|---|---|---|
| `results` | `{{ q }}`, `{{ limit }}`, `{{ offset }}` | `?uri ?title` | `?subtitle ?snippet ?image ?score` |
| `header` | `{{ uri }}` | `?title` | `?subtitle ?snippet ?image ?url`, any other variable becomes a labelled fact |
| `section` (0..n) | `{{ uri }}`, `{{ limit }}` | `?title` | `?item ?subtitle ?snippet ?image ?start ?end ?url ?tags` (newline-separated labels shown as chips, e.g. the skills and languages an experience developed) |
| `image` (0..1) | `{{ uris }}` | `?uri ?image` | |
| `row` (0..n) | `{{ uris }}` | `?uri ?value` | |

`image` and `row` queries decorate a page of results: they run once per page, with `{{ uris }}` rendered as that page's validated IRIs (`VALUES ?uri { {{ uris }} }`). The image query gives each result its picture (a person's portrait); each row query is one labelled metadata line under every result (organization, role, location; people and consultants for an organization), several values joined. A broken image or row query leaves its slot empty and never hides the results. A topic also names its **detail label**, the tab that shows one individual ("Profile" for a person, "Card" for an organization).

A section may name a `link_topic`: its `?item` then opens in that topic's detail (experience → organization, organization → people), so topics link to each other without code.

- **API** (`services/search/topics/`, under `/api/search/topics`): list, results, detail, contract, preview, save (PUT) and reset (DELETE). Templates run through `WorkspaceGraphStore`, which pins the SPARQL dataset to the graphs the workspace can read. Placeholders are substituted only through `sparql_safe` (`{{ q }}` escaped as literal content, `{{ uri }}` validated as an IRI, integers checked). On save, every template is parsed and checked against its role (SELECT only; required variables projected; no `SERVICE` or `FROM`, using the scoped store's own `query_shape` guard).
- **Storage**: built-in topics (`person`, `organization`) live in code (`builtin.py`). A workspace's overrides and custom topics are rows in `search_topics` (migration `0046`), behind `SearchTopicStorePort`. Reset deletes the row, so a built-in comes back as shipped. Reading needs workspace access; editing and previewing need owner or admin.
- **Scopes**: the search page reads three kinds of scope, listed in one registry (`web/src/lib/search-scopes.ts`): the enabled **topics**, the Nexus **features** the workspace has (Apps, Chats, Files, Documents, Slides, Sheets, Datasets, Ontology, Knowledge graph, Maps, Agents — hidden when the workspace feature flag is off), and **Web** (the former multi-source search). Each scope has a provider (`search-providers.ts`) that returns one hit shape (title, subtitle, snippet, image, action). Feature providers read the feature's own API or store, so search shows what the feature would show this user. Topic ids may not take a feature's id (`RESERVED_TOPIC_IDS`).
- **Web**: `/search?scope=&q=&item=&tab=`. Without a scope the page is **All**: the query runs in every scope that is switched on, and each answers with a short group linking to its full view. A topic opens in three tabs: **Results** (one full-width list, like Apps, Agents or Chats), **Ontology**, and its detail label (Profile, Card…), empty until a result is opened, which switches to it and keeps the individual across tabs (`tab=details`). Its views are the results, the detail and the ontology (the class's dictionary entry and the topic's queries; every block can show the SPARQL that filled it), a feature with its full list, and Web with its source filters. Settings → Search edits topics, with a per-query **Test** against the workspace graphs.
- **Sidebar**: the dock's Search button now navigates to `/search` like every other section. The topnav keeps the quick-open palette (⌘K). The Search column lists every scope, grouped Topics / Workspace / Web, each with a switch that includes it in All (kept per browser; Web is off until switched on, because the query leaves Nexus) and a link that opens it alone, plus the current query's hit counts. Web's sources are toggled under it. "Manage topics" links to the settings for admins.

## Consequences

A new search layer is a settings entry, or a built-in added in `builtin.py`, not a new app. A new Nexus feature becomes searchable with one provider and one registry entry. The UI's slot set is the contract: anything a layer needs to show that does not fit `title/subtitle/snippet/image/period/item/facts` is a change to the contract, made once for every topic.

Built-in topics read `abi:Person` / `abi:Organization` and join personnel properties only in `OPTIONAL`, so they work in a workspace without the personnel module. They are written against the default graph (the union of readable graphs), not a named `GRAPH`, unlike `PersonnelSparqlQueries.ttl`.

Feature providers filter workspace-sized lists in the browser. Files is the exception that shows: the files API filters names in one folder only, so the Files scope covers the top folder and says so. A recursive file search, and full-text search in documents and chats, need server-side endpoints; only those providers change. Topic matching is `CONTAINS` over labels, with no index, which is fine for directories of thousands of people. Larger graphs need the jena-text path the graph query compiler already anticipates (`resolve_fts_backend`).

The People Search app keeps working; it is not removed by this change. Once the Person topic covers its sections, the app can be retired or kept as a reference renderer.

### Next: a search ontology

Topics are meant to become individuals of a small, generic search ontology, so that a module ships its topics as TTL next to its competency queries (as `intentMapping:TemplatableSparqlQuery` does today) and Nexus loads them, instead of Python in `builtin.py`. The schema names are chosen to map one to one:

| Code | Ontology term (draft) |
|---|---|
| `SearchTopic` | `search:SearchTopic`, a directive information content entity |
| `class_iri` | `search:searchesClass` → `owl:Class` |
| `results_query` / `header_query` / `sections[].query` | `search:hasResultsQuery` / `search:hasHeaderQuery` / `search:hasSection`, each a `search:TopicQuery` that is an `intentMapping:TemplatableSparqlQuery` |
| query role | `search:ResultsRole`, `search:HeaderRole`, `search:SectionRole`, `search:ImageRole`, `search:RowRole` |
| slot (`title`, `subtitle`, …) | `search:Slot` individuals; `search:requiresSlot` / `search:allowsSlot` on each role |
| `link_topic` | `search:linksToTopic` |

Then a module's `*SearchTopics.ttl` file is discovered like its apps, and a workspace override is a triple-store-backed copy in place of a Postgres row.
