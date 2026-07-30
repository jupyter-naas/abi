# Slides templates

Canonical seed decks for Nexus Slides (`/slides`).

| File | Source |
|---|---|
| `bob-fmz-v1.html` | Emma Petit BOB / Forvis Mazars slide template (`BOB_Slides_FMZ_Template.html`) |

Each deck is a self-contained HTML file with an in-browser `buildPptx()` export (pptxgenjs). PPTX fidelity is best-effort vs the live HTML preview.

New Slides projects copy this seed into Forgejo at `slides/<slug>/deck.html` on branch `slides/<slug>`, and also seed `slides/<slug>/assets/` (`.gitkeep` + README).

## Assets / images (deferred)

The BOB template embeds JPEG/PNG images as `data:` URLs inside `deck.html`. Extracting those binaries into `assets/` and rewriting the HTML to relative paths is deferred:

1. Forgejo `upsert_file` is text-only today.
2. Preview loads via `srcDoc`, so relative `assets/` URLs would not resolve without an asset-serving route.

Until then, Preview/Export keep using the embedded data-URLs; the sidebar still shows an `assets/` folder for manual drops and future extract.
