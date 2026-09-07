# Slides templates

Canonical seed decks for Nexus Slides (`/slides`).

These are served under the reserved `abi` namespace, as `abi/<id>`. A deploy
can add seed trees of its own by declaring them in `config.yaml` under
`modules.naas_abi.config.nexus_config.slides_template_sources`, each with a
`namespace` and a `path`; those are listed alongside these as
`<namespace>/<id>`. The list is additive, so these seeds are always served.

Bare ids still load, resolved in declaration order, so `project.json` files
written before the namespaces existed keep opening.

| File | Catalog name | Notes |
|---|---|---|
| `minimal-light-v1.html` | Minimal Light | Quiet light deck; CDN pptxgen (gallery default) |
| `pitch-dark-v1.html` | Pitch Dark | Dark high-contrast pitch; CDN pptxgen |
| `executive-v1.html` | Executive | Navy / cream institutional; CDN pptxgen |
| `catalog.json` | : | Gallery metadata (name, description, preview colors) |
| `NOTICE.md` | : | MIT notice for Frontend Slides aesthetic inspiration |

Each deck is a self-contained HTML file with:

- `.deck` / `.slide` structure (1280x720)
- Fixed `deck-menubar` + Export menu (PDF / PPTX / Print)
- In-browser `buildPptx()` that walks the live `.slide` DOM (pptxgenjs). HTML is the source; PPTX is a closest-fit reconstruction (same geometry, type, colors). Not pixel-perfect.
- Decorative bands as SVG `data:` URLs

New Slides projects copy the chosen seed into Forgejo at `slides/<slug>/deck.html` on branch `slides/<slug>`, and also seed `slides/<slug>/assets/` (`.gitkeep` + README).

## How to add a template

1. Copy an existing `*.html` seed and restyle under the Nexus contract above.
2. Name the file `<kebab-id>.html` (e.g. `swiss-modern-v1.html`). The stem is the id; the advertised `template_id` is `abi/<stem>`.
3. Register it in `catalog.json` with `id` (the stem), `name`, `description`, and `preview` colors (`bg`, `panel`, `accent`, `ink`) for the gallery CSS miniature. Catalog order is picker order.
4. Seeds that belong to one deploy rather than to ABI go in that deploy's own tree, declared as a `slides_template_sources` entry. Same file layout as here.
5. Run API tests: `pytest …/slides__primary_adapter__FastAPI_test.py -k seed`.
6. Optional: progressive style packs can be imported later by dropping more HTML + catalog rows; do not vendor external skill trees as source.

New Presentation seeds Minimal Light (`abi/minimal-light-v1`) and opens Abi. Catalog rows remain for API seed lookup, not a gallery in front of chat.

## Assets / images

Decorative bands use SVG `data:` URLs. Binary extract into `assets/` with relative paths is deferred until an asset-serving route exists for Preview.
