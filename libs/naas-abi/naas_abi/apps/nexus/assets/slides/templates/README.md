# Slides templates

Canonical seed decks for Nexus Slides (`/slides`).

| File | Notes |
|---|---|
| `default-v1.html` | Generic cold-start deck (cover, agenda, section dividers, sample content) with `buildPptx()` |

Each deck is a self-contained HTML file with an in-browser `buildPptx()` export (pptxgenjs). PPTX fidelity is best-effort vs the live HTML preview.

New Slides projects copy this seed into Forgejo at `slides/<slug>/deck.html` on branch `slides/<slug>`, and also seed `slides/<slug>/assets/` (`.gitkeep` + README).

## Assets / images

Decorative bands use neutral SVG `data:` URLs (gradients / geometric panels), not client photos or brand logos. Binary extract into `assets/` with relative paths is deferred until an asset-serving route exists for Preview.
