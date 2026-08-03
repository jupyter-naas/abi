# Slides templates

Canonical seed decks for Nexus Slides (`/slides`).

Mirrored for Zen deploys at `src/zen/assets/slides/templates/` in the Zen repo.

| File | Catalog name | Notes |
|---|---|---|
| `minimal-light-v1.html` | Minimal Light | Quiet light deck; CDN pptxgen (gallery default) |
| `pitch-dark-v1.html` | Pitch Dark | Dark high-contrast pitch; CDN pptxgen |
| `executive-v1.html` | Executive | Navy / cream institutional; CDN pptxgen |
| `catalog.json` | : | Gallery metadata (name, description, preview colors) |
| `NOTICE.md` | : | MIT notice for Frontend Slides aesthetic inspiration |

Each deck is a self-contained HTML file with:

- `.deck` / `.slide` structure (1280×720)
- Fixed `deck-menubar` + Export menu (PDF / PPTX / Print)
- In-browser `buildPptx()` (pptxgenjs)
- Decorative bands as SVG `data:` URLs

New Slides projects copy the chosen seed into Forgejo at `slides/<slug>/deck.html` on branch `slides/<slug>`, and also seed `slides/<slug>/assets/` (`.gitkeep` + README).

## How to add a template

1. Copy an existing `*.html` seed and restyle under the Zen contract above.
2. Name the file `<kebab-id>.html` (e.g. `swiss-modern-v1.html`). The stem is the `template_id`.
3. Register it in `catalog.json` with `id`, `name`, `description`, and `preview` colors (`bg`, `panel`, `accent`, `ink`) for the gallery CSS miniature.
4. Mirror the same files into Zen `src/zen/assets/slides/templates/` when shipping on Zen.
5. Run API tests: `pytest …/slides__primary_adapter__FastAPI_test.py -k seed`.
6. Optional: progressive style packs can be imported later by dropping more HTML + catalog rows; do not vendor external skill trees as source.

Gallery UI: **File → New Presentation** (`/slides/new`) loads `GET /api/slides/templates` and posts the selected `template_id` to `POST /api/slides/projects`.

## Assets / images

Decorative bands use SVG `data:` URLs. Binary extract into `assets/` with relative paths is deferred until an asset-serving route exists for Preview.
