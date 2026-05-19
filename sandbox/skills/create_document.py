#!/usr/bin/env python3
"""
Create a standalone HTML document with a one-click Export to DOCX button.

The generated HTML is a styled, print-ready document that uses html-docx-js
(loaded from CDN) to convert the document to a real .docx file in the browser.

Input format (JSON via --json, stdin, or markdown via --md):
    {
        "title": "Document Title",
        "subtitle": "Optional subtitle",
        "author": "Name",
        "date": "2026-05-19",
        "theme": "light",          // "light" | "dark" | "corporate"
        "sections": [
            {
                "heading": "Section Title",    // optional
                "level": 1,                    // 1-3, default 1
                "content": "Paragraph text.",
                "type": "paragraph"            // "paragraph" | "bullets" | "table" | "code"
            }
        ]
    }

    For "bullets" type, content is newline-separated items.
    For "table" type, content is "Col1|Col2|Col3" rows separated by newlines
      (first row is treated as header).
    For "code" type, content is the code block.

Usage:
    python create_document.py --json spec.json -o document.html
    python create_document.py --md report.md -o report.html
    echo '{"title":"Report","sections":[{"heading":"Intro","content":"Hello world"}]}' | python create_document.py
    opencode: "create a business document about X and run create_document.py"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

# ─── Themes ────────────────────────────────────────────────────────────────────

THEMES: dict[str, dict] = {
    "light": {
        "bg": "#f0f4f8",
        "paper": "#ffffff",
        "text": "#1a202c",
        "muted": "#718096",
        "accent": "#4f46e5",
        "border": "#e2e8f0",
        "code_bg": "#f7fafc",
        "heading": "#1a202c",
        "th_bg": "#4f46e5",
        "th_fg": "#ffffff",
    },
    "dark": {
        "bg": "#0f0f13",
        "paper": "#1a1a24",
        "text": "#e2e8f0",
        "muted": "#94a3b8",
        "accent": "#818cf8",
        "border": "#2d3748",
        "code_bg": "#0d0d14",
        "heading": "#f1f5f9",
        "th_bg": "#6366f1",
        "th_fg": "#ffffff",
    },
    "corporate": {
        "bg": "#f5f5f0",
        "paper": "#ffffff",
        "text": "#1c1c1c",
        "muted": "#666666",
        "accent": "#0066cc",
        "border": "#d0d0d0",
        "code_bg": "#f0f0f0",
        "heading": "#0d1f3c",
        "th_bg": "#0066cc",
        "th_fg": "#ffffff",
    },
}

# ─── HTML template ─────────────────────────────────────────────────────────────

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/html-docx-js@0.3.1/dist/html-docx.js"></script>
<script src="https://cdn.jsdelivr.net/npm/file-saver@2.0.5/dist/FileSaver.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Georgia', 'Times New Roman', serif;
    background: {bg};
    color: {text};
    min-height: 100vh;
    padding: 0;
  }}
  /* ── Toolbar ── */
  .toolbar {{
    position: sticky;
    top: 0;
    z-index: 100;
    background: {paper};
    border-bottom: 1px solid {border};
    padding: 10px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    box-shadow: 0 2px 8px rgba(0,0,0,.08);
  }}
  .toolbar-title {{ font-size: 13px; font-weight: 600; color: {text}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .toolbar-actions {{ display: flex; gap: 8px; flex-shrink: 0; }}
  .export-btn {{
    background: {accent};
    color: #fff;
    border: none;
    padding: 7px 18px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 600;
    font-family: inherit;
    transition: opacity .15s;
  }}
  .export-btn:hover {{ opacity: .85; }}
  .export-btn:disabled {{ opacity: .5; cursor: not-allowed; }}
  /* ── Paper ── */
  .page {{
    max-width: 760px;
    margin: 36px auto;
    background: {paper};
    border-radius: 8px;
    box-shadow: 0 4px 24px rgba(0,0,0,.1);
    padding: 60px 72px;
  }}
  /* ── Cover ── */
  .cover {{
    margin-bottom: 48px;
    padding-bottom: 32px;
    border-bottom: 3px solid {accent};
  }}
  .cover h1 {{
    font-size: 32px;
    font-weight: 700;
    color: {heading};
    line-height: 1.2;
    margin-bottom: 10px;
  }}
  .cover .subtitle {{
    font-size: 18px;
    color: {muted};
    font-style: italic;
    margin-bottom: 16px;
  }}
  .cover .meta {{
    font-size: 12px;
    color: {muted};
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }}
  /* ── Content ── */
  .section {{ margin-bottom: 28px; }}
  h2 {{
    font-size: 22px;
    font-weight: 700;
    color: {heading};
    margin-bottom: 12px;
    padding-bottom: 6px;
    border-bottom: 1px solid {border};
  }}
  h3 {{
    font-size: 17px;
    font-weight: 600;
    color: {heading};
    margin-bottom: 10px;
  }}
  h4 {{
    font-size: 14px;
    font-weight: 600;
    color: {accent};
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: .05em;
  }}
  p {{
    font-size: 15px;
    line-height: 1.75;
    color: {text};
    margin-bottom: 12px;
  }}
  ul {{
    padding-left: 20px;
    margin-bottom: 12px;
  }}
  ul li {{
    font-size: 15px;
    line-height: 1.7;
    color: {text};
    margin-bottom: 4px;
  }}
  ul li::marker {{ color: {accent}; }}
  pre {{
    background: {code_bg};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 16px;
    overflow-x: auto;
    margin-bottom: 16px;
  }}
  code {{
    font-family: 'Fira Code', 'Consolas', monospace;
    font-size: 13px;
    color: {text};
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 16px;
    font-size: 14px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  }}
  thead tr {{ background: {th_bg}; color: {th_fg}; }}
  th {{ padding: 10px 14px; text-align: left; font-weight: 600; }}
  td {{ padding: 9px 14px; border-bottom: 1px solid {border}; color: {text}; }}
  tbody tr:nth-child(even) {{ background: rgba(0,0,0,.02); }}
  @media print {{
    .toolbar {{ display: none; }}
    .page {{ box-shadow: none; margin: 0; border-radius: 0; padding: 40px; }}
    body {{ background: white; }}
  }}
  ::-webkit-scrollbar {{ width: 4px; }}
  ::-webkit-scrollbar-thumb {{ background: {border}; border-radius: 2px; }}
</style>
</head>
<body>

<div class="toolbar">
  <span class="toolbar-title">{title}</span>
  <div class="toolbar-actions">
    <button class="export-btn" onclick="window.print()">🖨 Print / PDF</button>
    <button class="export-btn" id="exportBtn" onclick="exportDocx()">&#8595; Export DOCX</button>
  </div>
</div>

<div class="page" id="documentBody">
  <div class="cover">
    <h1>{title}</h1>
    {subtitle_html}
    <div class="meta">
      {author_html}
      {date_html}
    </div>
  </div>
  {sections_html}
</div>

<script>
async function exportDocx() {{
  const btn = document.getElementById('exportBtn');
  btn.disabled = true;
  btn.textContent = 'Generating…';
  try {{
    // Grab the document body content (excluding toolbar)
    const body = document.getElementById('documentBody');
    const html = '<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body>' + body.innerHTML + '</body></html>';
    const converted = htmlDocx.asBlob(html);
    saveAs(converted, '{filename}.docx');
  }} catch(e) {{
    alert('Export failed: ' + e.message);
    console.error(e);
  }} finally {{
    btn.disabled = false;
    btn.textContent = '↓ Export DOCX';
  }}
}}
</script>
</body>
</html>
"""

# ─── Helpers ───────────────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _section_html(sec: dict) -> str:
    heading = sec.get("heading", "")
    level = min(max(int(sec.get("level", 1)), 1), 3)
    tag = f"h{level + 1}"  # h2 for level 1, h3 for level 2, h4 for level 3
    sec_type = sec.get("type", "paragraph")
    content = sec.get("content", "")

    parts = ['<div class="section">']
    if heading:
        parts.append(f"  <{tag}>{_esc(heading)}</{tag}>")

    if sec_type == "bullets":
        parts.append("  <ul>")
        for line in content.split("\n"):
            line = line.strip().lstrip("-*• ").strip()
            if line:
                parts.append(f"    <li>{_esc(line)}</li>")
        parts.append("  </ul>")
    elif sec_type == "table":
        rows = [r.strip() for r in content.split("\n") if r.strip()]
        parts.append("  <table>")
        for i, row in enumerate(rows):
            cells = [c.strip() for c in row.split("|")]
            if i == 0:
                parts.append("    <thead><tr>")
                for c in cells:
                    parts.append(f"      <th>{_esc(c)}</th>")
                parts.append("    </tr></thead><tbody>")
            else:
                parts.append("    <tr>")
                for c in cells:
                    parts.append(f"      <td>{_esc(c)}</td>")
                parts.append("    </tr>")
        parts.append("    </tbody></table>")
    elif sec_type == "code":
        parts.append(f"  <pre><code>{_esc(content)}</code></pre>")
    else:
        for para in content.split("\n\n"):
            para = para.strip()
            if para:
                parts.append(f"  <p>{_esc(para)}</p>")

    parts.append("</div>")
    return "\n".join(parts)


def _parse_markdown(md_text: str) -> dict:
    """Convert basic markdown to our JSON spec."""
    lines = md_text.split("\n")
    title = "Document"
    sections: list[dict] = []
    buf: list[str] = []
    cur_heading = ""
    cur_level = 1

    def flush():
        nonlocal buf, cur_heading
        text = "\n".join(buf).strip()
        if text or cur_heading:
            sections.append({"heading": cur_heading, "level": cur_level, "content": text, "type": "paragraph"})
        buf = []
        cur_heading = ""

    for line in lines:
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            flush()
            depth = len(m.group(1))
            if depth == 1 and not title.strip("Document "):
                title = m.group(2).strip()
            else:
                cur_heading = m.group(2).strip()
                cur_level = max(1, depth - 1)
        else:
            buf.append(line)

    flush()
    return {"title": title, "sections": sections}


# ─── Main ──────────────────────────────────────────────────────────────────────

def build_html(spec: dict, theme_name: str = "light") -> str:
    theme = THEMES.get(theme_name, THEMES["light"])
    title = spec.get("title", "Document")
    subtitle = spec.get("subtitle", "")
    author = spec.get("author", "")
    doc_date = spec.get("date", str(date.today()))
    sections = spec.get("sections", [])

    subtitle_html = f'<div class="subtitle">{_esc(subtitle)}</div>' if subtitle else ""
    author_html = f'<span>✍ {_esc(author)}</span>' if author else ""
    date_html = f'<span>📅 {_esc(doc_date)}</span>' if doc_date else ""
    sections_html = "\n".join(_section_html(s) for s in sections)
    filename = re.sub(r"[^a-z0-9]", "_", title.lower()).strip("_") or "document"

    return HTML_TEMPLATE.format(
        title=_esc(title),
        subtitle_html=subtitle_html,
        author_html=author_html,
        date_html=date_html,
        sections_html=sections_html,
        filename=filename,
        **theme,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", "-j", help="Path to JSON spec file")
    parser.add_argument("--md", help="Path to Markdown file (auto-parsed)")
    parser.add_argument("--title", help="Document title (quick mode)")
    parser.add_argument("--stdin", action="store_true", help="Read JSON or markdown from stdin")
    parser.add_argument("--theme", default="light", choices=list(THEMES), help="Color theme (default: light)")
    parser.add_argument("--output", "-o", default="document.html", help="Output HTML file (default: document.html)")
    args = parser.parse_args()

    if args.json:
        spec = json.loads(Path(args.json).read_text())
    elif args.md:
        spec = _parse_markdown(Path(args.md).read_text())
    elif args.stdin:
        raw = sys.stdin.read().strip()
        spec = json.loads(raw) if raw.startswith("{") else _parse_markdown(raw)
    else:
        spec = {"title": "Untitled Document", "sections": [{"heading": "Introduction", "content": "Start writing here.", "type": "paragraph"}]}

    if args.title:
        spec["title"] = args.title
    if "theme" not in spec:
        spec["theme"] = args.theme

    html = build_html(spec, spec.get("theme", args.theme))
    out = Path(args.output)
    out.write_text(html, encoding="utf-8")
    print(f"✅ Document created: {out.resolve()}")
    print(f"   Open in browser — click 'Export DOCX' to download as .docx")


if __name__ == "__main__":
    main()
