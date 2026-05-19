# Sandbox

The sandbox is the working directory for the **Code** section of the ABI platform. Everything in here is yours: files the AI creates live here, and anything you place here is accessible to the AI.

---

## How the Code section works

The Code section gives you three panels:

| Panel | Purpose |
|---|---|
| File explorer (left) | Browse and open files in the sandbox. Click a file to view it. Markdown files render as formatted documents; code files open in the editor with syntax highlighting. |
| Editor / viewer (center) | Monaco editor for code files. Markdown viewer with a toggle to switch to raw source. |
| AI chat (right) | An opencode-powered assistant that can read, create, and modify files in your sandbox. Each conversation gets its own session folder. |

### Session folders

Every chat session creates a dedicated subfolder:

```
sandbox/
  nexus-<session-id>/    <- files created during that session
  nexus-<session-id>/    <- files from another session
  skills/                <- reusable scripts (see below)
```

The AI is told its session folder at the start of every message, so files it creates land there automatically. You can open them immediately in the file explorer.

---

## Skills

Skills are executable scripts in `sandbox/skills/` that opencode discovers and uses on demand. Every message you send includes a manifest listing the available skills and their purpose, so the AI can pick the right one without you naming it explicitly.

### How to trigger a skill

Just describe what you want in natural language:

- "Create a slide deck about our Q3 roadmap"
- "Write a business brief on competitive positioning"
- "Generate a chart from this CSV data"

The AI matches your intent to the right skill and runs it with `bash`.

### Available skills

| Script | What it does |
|---|---|
| `create_slides.py` | Generates a standalone HTML slide deck (16:9, themes: dark/light/blue) with a one-click **Export PPTX** button powered by PptxGenJS |
| `create_document.py` | Generates a styled HTML document (themes: light/dark/corporate) with **Print/PDF** and **Export DOCX** buttons powered by html-docx-js |

Both scripts produce a single `.html` file with all libraries loaded from CDN — no install required. Open the file in any browser to view and export.

### Adding a new skill

1. Create a `.py`, `.sh`, `.ts`, or `.js` file in `sandbox/skills/`
2. Put a one-liner description as the **first line of the docstring** — this becomes the skill's intent label in the manifest:

```python
#!/usr/bin/env python3
"""
Generate an HTML competitive analysis report from a list of company names.
...
"""
```

3. That's it. The skill shows up in the manifest on the next message.

**Naming rules:**
- Descriptive filenames: `generate_report.py`, `fetch_github_data.py`
- Files starting with `_` are ignored (use for helpers/shared code)
- Output files to the session working directory (the AI handles this automatically)

### Asking opencode to create a skill

You can ask opencode to write a new skill for you directly in the chat:

> "Create a skill that converts a CSV into an interactive HTML bar chart using Chart.js"

It will write the script, place it in `sandbox/skills/`, and it becomes available immediately on the next message.

---

## File access

The file explorer shows **only the sandbox folder**. The AI can read files anywhere in the project (for context), but it can only write inside the sandbox. This keeps the rest of the codebase safe while giving the AI full freedom to create and iterate on output files.
