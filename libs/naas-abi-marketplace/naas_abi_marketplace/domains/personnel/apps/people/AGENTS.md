# AGENTS — People Search

> Scope: `domains/personnel/apps/people/`. A configurable people directory over
> the personnel graph. See `README.md` for how to run and retarget it.

## The chain

```
data/demo/person/*/index.json          source (fictional, for the demo)
  -> pipelines/                        ActOfWorking, ActOfStudying, ActOfCertification, PersonProfile
  -> graphs/demo/personnel.ttl         the graph, ontology-backed
  -> ontologies/queries/*.ttl          competency queries
  -> dataset service (DuckLake)        nine typed tables in the `personnel` namespace
  -> api/ + web/                       this app
```

Every step is replaceable except the order. Never shortcut it by putting people
data in this folder: an app with its own copy of the directory is the fork this
app exists to prevent.

## Instances

This app is mounted more than once. `config_loader`, `build_router` and the
exporter all take a config path; the one shipped here is a default, not the
only one. Two consequences, both easy to break:

- **Never read the shipped `config.yaml` implicitly** in code that serves a
  request. Take the path, or the already-loaded config dict, as an argument.
  `load_config()` with no argument is for scripts and tests.
- **Never resolve an instance's file against `APP_ROOT`.** Brand files, the
  graph TTL and portraits belong to whoever owns the config; use
  `web_root_for(config_path)` and the `data.*` keys.

`web/` is served to every instance from this package, so a path in the JS is a
path in everyone's app. Instance-owned files are referenced relatively and
instance-agnostic ones absolutely under the API prefix.

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
3. Add its table to `scripts/datasets.TABLES`, its shaping to `scripts/profile_payload._section_items`,
   and its rows to `scripts/export_people_from_graph.py`.
4. Add the competency query it reads to `ontologies/queries/PersonnelSparqlQueries.ttl`
   and register its label in `agents/PersonnelAgent.get_sparql_tools()`.
5. Add it to `config.yaml` with a label, an order and an `empty_text`.

If the graph cannot answer step 4, the section has no business existing yet.
Extend the ontology first.

Which sections are **process-shaped** (ActOfWorking / ActOfStudying / ActOfCertification) vs **person-level**
(PersonProfilePipeline) is documented in
[`personnel/README.md`](../../README.md) under **Profile sections vs ontology layers**.

## Rules

- **An empty section is an answer.** A person with no recommendations renders
  the configured `empty_text`. Never hide the section, and never fill it with a
  placeholder: "nothing recorded" and "we failed to load it" must not look alike.
- **The ontology page reads `ontologies/processes/*.ttl`.** A new process slice
  shows up there, and in the bucket colours, by being filed in that directory
  (the file list is read when the server starts: restart it after adding or
  renaming one). Do not list slices by name in the app.
- **The ontology page follows the Nexus ontology network** (`naas_abi` nexus web,
  `components/ontology` and `components/graph`): toolbar with the relations to
  show and the layout, BFO-coloured square cards, square-corner connectors, a
  bucket panel, an inspector and a status bar. Keep it in step with Nexus rather
  than restyling it here. The pieces are `web/lib/network-canvas.js` (one 2D
  canvas, no dependency), `network-layout.js`, `orthogonal-route.js` and
  `ontology-graph.js` (the payload as terms and relations).
- **The default layout places the classes in BFO zones**, as in
  `naas_abi/ontologies/docs/BFO_7B.html`: Process (top left) and Temporal Region
  (top right) in the occurrents band, Process taking 70% of it; Material Entity,
  Site, GDC, Quality, Realizable in the continuants band. A zone is as wide as
  the cards it holds, cards are centred in it, and rows line up across a band.
  Do not hard-code zone sizes: they follow the number of classes shown.
- **Connectors are routed together, not one by one** (`orthogonal-route.js`): on
  a grid of corridors, each connector its own track, ports spread along a card's
  side. Two relations that are each other's inverse are drawn as one two-way
  connector. Do not route a connector on its own: that is how they end up
  drawn on top of one another. Restrictions are the only relation on by default.
- **In the BFO zone layout the sides of a connector are fixed by the buckets it
  joins** (`web/lib/bfo-edge-rules.js`, the only place the table is written; the
  layout and the router read what `sidesFor` says, not the table). N/S/W/E are
  the top, bottom, left and right of a card; a rule holds both ways, for every
  family (subClassOf, restriction, object property):

  | Pair | Sides | Shape |
  |---|---|---|
  | Process / Temporal Region | N / N | U over the top |
  | Process / Quality, Process / Realizable | E / W | east out of Process, down between the zones |
  | Process / GDC | S / W | south out of Process, west into GDC |
  | Process / Site | W / N | west out of Process, top of Site |
  | Process / Material Entity | W / W | C down the left margin |
  | Material Entity, Site or GDC / GDC, Quality or Realizable (the pairs listed in the file) | S / S | U under the bottom band |
  | same bucket; Material Entity / Site; GDC / Quality; Quality / Realizable; Temporal Region with anything but Process; Entity, Unknown, Other | free | shortest route, any side |

  The layout sizes what the rules force, from what `sidesFor` returns: a margin
  under the bottom band at a track per S/S connector, a left margin at a track
  per connector leaving Process by the west, the corridors for what passes
  through them, and cards wide enough that the ports on one side stay a track
  apart. It also puts the cards a side is used most on where that side is open.
  A rule that has no way through falls back to a free route and is reported;
  a fixed connector needing more than three bends is reported too. Both go to
  `console.warn`, never hidden. **Exempt: the tree layouts (top to bottom, left
  to right), which have no rules, and the plain elbows drawn while a card is
  dragged.** A card with another card in front of the side a rule gives it cannot
  be left by that side in a straight line, so its connectors need more than three
  bends: that is the layout, not the router, and it is why the count is reported.
- **The ontology is one merged document.** The first file entry is the module and
  every process slice read as one graph, so a class the slices restate is one
  block (`merged_turtle`); the individual files stay listed under it.
- **The canvas draws only classes a visible connection reaches.** A file that
  says `subClassOf abi:Role` names `Role`, but with the hierarchy off nothing
  links it, so it is not drawn. `connectedNodes` decides this from the relations
  that are on and the file chosen; the bucket and hide-by-hand filters do not
  change it (choosing Why shows its connected roles, without connections among
  them). The BFO 7 Buckets panel lists the connected classes and its counts and
  ticks are what is on the canvas, so its total equals the status bar's. Pinned
  in `web/lib/ontology-graph.test.js`.
- **Facility classes are WHERE.** The process slices say an act occurs in a CCO
  facility (Office Building, Educational Facility, Facility), which BFO/CCO file
  under Material Artifact. `bfo_bucket_resolution.py` treats `cco:ont00000192` as
  a WHERE root so the facilities, and their subclasses, are drawn in the Site
  zone; the payload (`_add_imported_classes`) states the CCO classes the
  personnel files use, with their labels, so the page can name them. A new CCO
  class used by a slice is picked up if it belongs to the Facility ontology.
- **The Turtle panel is resizable.** A handle on its right edge (drag, arrow keys,
  Home or double-click to reset) sets its width, kept between 240px and what
  leaves the network 320px, and remembered in `localStorage`. Stacked under 900px
  wide it keeps its fixed height and the handle is hidden.
- **Zones can be switched off, in two levels.** "Zone Top Level" (the OCCURRENTS /
  CONTINUANTS bands) and "Zone BFO 7 Buckets" (a zone per bucket) are separate
  checkboxes, BFO zones layout only; only the top level is on by default. Each hides its zones
  with their titles (`setZonesVisible`). It is drawing only: the cards, the side
  rules and the routing do not change, so nothing is re-laid out.
- **Nothing is computed that a source did not state.** `years_of_experience` is
  a claim carried by the profile summary, not a sum over acts of working. A
  period shows the dates and the source's own duration label.
- **Contact details go in their own columns only.** The exporter refuses an
  email address or a run of nine or more digits in any other column, and the
  test suite pins both. Eight digits pass so that `2018-2021` is not mistaken
  for a phone number. `people.email`, `people.phone` and `people.linkedin_url`
  are the exception: shape-checked, and empty unless
  `privacy.publish_contact_details` is true. Do not add them to
  `PERSON_FIELDS`. That would make them searchable and usable as facets.
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

An instance picks its own prefix and namespace and keeps everything else, for
example `/api/personnel-people-acme` and `personnel_acme`.

## Tests

```bash
uv run pytest libs/naas-abi-marketplace/naas_abi_marketplace/domains/personnel -q

# the ontology page's layout and router (Node 20, no install), from apps/people
node --test web/lib/
```

`node --test` is not part of the pytest run: run it whenever `web/lib/` changes.
`bfo-edge-rules.test.js` lays out cards for all seven buckets, routes one
connector per rule and checks the sides it leaves and enters by, its bends and
that no two share a track.

`datasets_test.py` runs against a real DuckLake warehouse in a temporary
directory. It is the only way the SQL, the types and the flush are actually
exercised, so do not replace it with a fake store.
