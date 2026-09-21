"""Starter files for a new app project: static, no build, same shape as the
bundled module apps (``manifest.json`` with ``url: html:index.html``)."""

from __future__ import annotations

import html
import json

_INDEX = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <main class="app">
    <h1>{icon} {title}</h1>
    <p class="lead">{description}</p>
    <button id="counter" type="button">Clicked 0 times</button>
  </main>
  <script src="app.js"></script>
</body>
</html>
"""

_STYLES = """:root {
  color-scheme: light dark;
  --accent: #0057b8;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}

body {
  margin: 0;
  min-height: 100vh;
  display: grid;
  place-items: center;
}

.app {
  max-width: 40rem;
  padding: 2rem;
}

.lead {
  opacity: 0.75;
}

button {
  border: 0;
  border-radius: 0.5rem;
  padding: 0.6rem 1rem;
  background: var(--accent);
  color: white;
  font: inherit;
  cursor: pointer;
}
"""

_SCRIPT = """const button = document.getElementById("counter");
let clicks = 0;

button.addEventListener("click", () => {
  clicks += 1;
  button.textContent = `Clicked ${clicks} time${clicks === 1 ? "" : "s"}`;
});
"""


def starter_files(
    *, title: str, description: str, icon_emoji: str, author: str
) -> dict[str, bytes]:
    manifest = {
        "name": title,
        "description": description,
        "url": "html:index.html",
        "category": "application",
        "icon_emoji": icon_emoji,
        "version": "0.1.0",
        "author": author,
        "keywords": [],
        "pricing": {"type": "free", "price": 0},
    }
    index = _INDEX.format(
        title=html.escape(title),
        icon=html.escape(icon_emoji),
        description=html.escape(description or "Built in Nexus."),
    )
    return {
        "manifest.json": (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode(),
        "index.html": index.encode(),
        "styles.css": _STYLES.encode(),
        "app.js": _SCRIPT.encode(),
    }
