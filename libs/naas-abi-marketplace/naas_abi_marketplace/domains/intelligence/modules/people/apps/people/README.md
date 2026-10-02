# People Search

A people directory: Google-style search, a profile page per person. Everything
it shows comes from the personnel knowledge graph, and everything it looks like
comes from `config.yaml`.

```
person + experience  ->  graph (ontology-backed)  ->  datasets  ->  app
   pipelines/            graphs/demo/*.ttl           dataset        web/
                                                     service
```

## Run it

```bash
cd libs/naas-abi-marketplace/naas_abi_marketplace/domains/personnel
make people            # rebuild the graph and the datasets, then serve
make app-personnel-people   # serve what is already exported
PORT=4000 make app-personnel-people
```

Then open <http://localhost:3001/>. On WSL, if `localhost` does not answer from
Windows, use the IP from `hostname -I`.

Inside Nexus the same app is served from the manifest (`html:web/index.html`)
and its API is mounted by this module, so nothing needs to be rebuilt to embed
it.

## Rebuild the datasets

```bash
make people-datasets                       # demo graph -> dataset service
python -m naas_abi_marketplace.domains.personnel.apps.people.scripts.export_people_from_graph \
    --graph /path/to/your.ttl \
    --catalog sqlite:storage/datasets.sqlite --data-path storage/datasets/
```

The exporter runs the competency queries in
`ontologies/queries/PersonnelSparqlQueries.ttl` and writes nine tables. It
refuses to publish an email address or a phone number anywhere in the text.

Contact details have one way through. A source states them on the person
(`person.email`, `person.phone`, `person.linkedin_url`). The pipeline writes them
as the `personnel:email_address`, `personnel:telephone_number` and
`personnel:linkedin_url` data properties of `abi:Person`. The exporter puts them
in the `email`, `phone` and `linkedin_url` columns of `people`, checked for
shape, and only when `privacy.publish_contact_details` is true; otherwise those
columns are left empty. The profile header shows each one that a person has,
under `profile.contact`. They are never searchable, never a facet and never a
fact.

`linkedin_url` is the person's own LinkedIn page. `linkedin_profile_url` is the
page their profile was *read from*, shown under Sources, and can be any site.

| Table | One row per |
|---|---|
| `people` | person, plus the folded `search_text` the search matches on |
| `people_experience` | role, grouped by employer with `group_seq` |
| `people_education` | course of study |
| `people_skills` | person and skill |
| `people_certifications` | certification or licence |
| `people_languages` | language a person works in |
| `people_recommendations` | recommendation written about them |
| `people_interests` | interest |
| `people_sources` | source the profile was built from |

## Make it yours

Everything below is `config.yaml`. Nothing here needs a code change.

| Section | What it controls |
|---|---|
| `brand` | Name, description, the letter used when no logo is set, **and the logo and favicon files** (named relative to `web/assets/`) |
| `theme.css_variables` | Every colour, font and width, applied to `:root` |
| `app.pages` | Which of the three pages exist, their labels, URL segments and order |
| `search` | Which fields are searchable and how heavily they weight, the facet field and its label, snippet length, autocomplete threshold, page size, the example queries on the home page |
| `profile.facts` | The row under the name on a profile |
| `profile.contact` | Email, phone and LinkedIn links under the place line, in this order |
| `profile.sections` | Which sections appear, in what order, under what title, and what each says when it is empty |
| `data` | The dataset namespace and the table names to read |
| `privacy` | What the exporter refuses to publish, and `publish_contact_details` |

**Your own logo and favicon:** drop the files in `web/assets/`, then name them:

```yaml
brand:
  mark: "F"                          # used when no logo file is set
  logo_src: "assets/my-logo.svg"     # .svg, .png, .ico …
  favicon_src: "assets/my-icon.png"
```

Both are optional. With neither, the app draws `brand.mark` in `--accent`, so it
never ships someone else's logo by accident. A path that does not resolve is a
startup error, not a broken image. The catalog tile is separate: that comes from
`icon_emoji` / `avatar_url` in `manifest.json`, so change both together.

**A different population:** point `data.tables` at your own tables, keeping the
columns in `datasets.py`. `make people-datasets` is one way to fill them; any
writer that produces those columns works.

## A second directory, on the same app

A client does not fork this folder. They make one of their own holding a
`config.yaml`, a `web/index.html` and a `web/assets/` — nothing else — and mount
this app from their module:

```python
from naas_abi_marketplace.domains.personnel.apps.people.api.mount import mount_people_app

class ABIModule(BaseModule):
    dependencies = ModuleDependencies(modules=[], services=[DatasetService])

    def api(self, app):
        mount_people_app(app, prefix="/api/their-people", config_path=HERE / "config.yaml")
```

`mount_people_app` adds the routes **and** serves this package's `web/` at
`<prefix>/web`. Their `index.html` names both:

```html
<meta name="people-api-base" content="/api/their-people" />
<link rel="stylesheet" href="/api/their-people/web/css/app.css" />
<script type="module" src="/api/their-people/web/js/shell.js"></script>
```

Absolute, and under `/api/`, because Nexus proxies `/api/` and `/app-html/` and
nothing else. Their own files stay relative (`assets/logo.svg`), so they resolve
against their page in both the dev server and Nexus.

Everything per-instance is resolved against the folder holding the config: brand
files, `data.graph.file`, and `data.portrait_prefix`. Run one locally with

```bash
PEOPLE_APP_CONFIG=/path/to/their/config.yaml PEOPLE_API_PREFIX=/api/their-people \
  python -m naas_abi_marketplace.domains.personnel.apps.people.api.dev_server
```

and export into it with `--config`.

What configuration **cannot** do is invent a page or a profile section. Those are
renderers, registered in `web/lib/registry.js` and `config_loader.py`. Adding one
means adding it to both, in the same change.

## Resume and graph views

A profile opens as a resume. The switch at its top right turns it into a graph:
the cockpit's own graph page (`apps/cockpit/web/components/pages/graph/`), not a
copy of it, opened on that person.

- **Data, live.** `GET <prefix>/people/<slug>/graph` runs the cockpit's graph
  queries (`apps/cockpit/graph_query.py`) against this instance's graph file
  (`data.graph.file`) with `?person` bound to the profile's person. The result
  is complete and takes well under a second, even on a large directory. It is
  cached until the graph file changes.
- **Scripts.** The cockpit's page modules are mounted under
  `<prefix>/cockpit-pages/`, and the profile imports `GraphPage.js` from there
  with `syncUrl: false`, so the page leaves this app's address bar alone.
- **Styles.** `GET <prefix>/graph-view.css` holds the cockpit `app.css` rules
  that name a class the graph page renders, scoped under `.profile-graph`. Change
  the look in the cockpit stylesheet; this one is derived from it.
- **Settings.** Graph defaults (2D/3D, distance, parameters, BFO colours) come
  from the cockpit's `config.yaml`.

The graph shows one person. To look at someone else, open their profile.

## Files

```
people/
├── config.yaml              # the retargeting surface
├── config_loader.py         # validates it, and decides what the browser sees
├── datasets.py              # the nine table schemas and how they are read
├── text.py                  # folding, shared by the exporter and search
├── search_payload.py        # candidates from SQL, ranked and summarised
├── profile_payload.py       # one person, assembled into sections
├── scripts/                 # graph -> datasets
├── api/                     # routes, dataset service resolution, dev server
└── web/                     # the page: vanilla ES modules, no build step
    └── assets/              # logo, favicon, demo portraits
```

## Demo data

The eight people in the demo are fictional (`data/demo/person/*/index.json`).
Some of them have no recommendations, no languages or no certifications, on
purpose: the profile page has to show that a section is empty as clearly as it
shows a full one, and a demo where everyone is complete never proves it.

The portraits in `web/assets/portraits/` are abstract marks, not photographs. A
fictional person has no face, and inventing one would be inventing a person.
