"""Workspace slide templates for ABI Desktop."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

DEFAULT_SLIDE_DOWNLOAD = (
    Path.home() / "Downloads" / "Data_Governance_Quality_ISO27001 2 (2).html"
)
DATA_GOVERNANCE_SLIDE = "data-governance-quality-iso27001.html"

_SLIDE_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def sanitize_template_filename(name: str) -> str:
    """Return a filesystem-safe slide filename (keeps extension)."""
    path = Path(name.strip())
    stem = re.sub(r"\([^)]*\)", "", path.stem).replace("_", "-")
    stem = _SLIDE_NAME_RE.sub("-", stem).strip("-").lower()
    stem = re.sub(r"-+", "-", stem).strip("-")
    if not stem:
        stem = "slide"
    suffix = path.suffix.lower() if path.suffix else ".html"
    if suffix not in {".html", ".htm"}:
        suffix = ".html"
    return f"{stem}{suffix}"


STARTER_DECK_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Starter deck</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: system-ui, -apple-system, sans-serif;
      background: #0f172a;
      color: #f8fafc;
      line-height: 1.5;
    }
    .slide {
      min-height: 100vh;
      padding: 4rem 6vw;
      display: flex;
      flex-direction: column;
      justify-content: center;
      border-bottom: 1px solid #334155;
    }
    h1 { font-size: clamp(2rem, 5vw, 3.5rem); margin-bottom: 1rem; }
    h2 { font-size: clamp(1.25rem, 3vw, 2rem); color: #94a3b8; margin-bottom: 1.5rem; }
    ul { margin-left: 1.25rem; font-size: 1.125rem; }
    li { margin: 0.5rem 0; }
    .accent { color: #22c55e; }
  </style>
</head>
<body>
  <section class="slide">
    <h2>ABI Desktop</h2>
    <h1>Starter slide deck</h1>
    <p>Edit this HTML in the Code section. Use Split view for a live preview.</p>
  </section>
  <section class="slide">
    <h2>Outline</h2>
    <ul>
      <li>Add a <span class="accent">&lt;section class="slide"&gt;</span> per slide</li>
      <li>Ask the coding agent to restyle or extend content</li>
      <li>Save with Cmd/Ctrl+S</li>
    </ul>
  </section>
</body>
</html>
"""

SLIDES_README = """# Slide templates

HTML slide decks for ABI Desktop Code section.

- `starter-deck.html` — minimal multi-slide HTML starter
- `data-governance-quality-iso27001.html` — example deck (when copied from Downloads)

Open a file in Code, switch to **Split** view for live preview, and ask the coding
agent to modify the open HTML.
"""


def ensure_templates(
    workspace: str | Path,
    *,
    source_slide: Path | None = None,
) -> Path:
    """Create ``templates/slides/`` and seed starter files when missing."""
    root = Path(workspace).expanduser().resolve()
    slides_dir = root / "templates" / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    readme = slides_dir / "README.md"
    if not readme.exists():
        readme.write_text(SLIDES_README, encoding="utf-8")

    starter = slides_dir / "starter-deck.html"
    if not starter.exists():
        starter.write_text(STARTER_DECK_HTML, encoding="utf-8")

    source = source_slide if source_slide is not None else DEFAULT_SLIDE_DOWNLOAD
    target = slides_dir / DATA_GOVERNANCE_SLIDE
    if source.is_file() and not target.exists():
        shutil.copy2(source, target)

    return slides_dir
