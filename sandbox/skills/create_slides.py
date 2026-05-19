#!/usr/bin/env python3
"""
Create a standalone HTML slide deck with a one-click Export to PPTX button.

The generated HTML is a self-contained presentation (no server needed) that
uses PptxGenJS loaded from CDN to produce a real .pptx file in the browser.

Input format (JSON via --json, stdin, or --title/--slides flags):
    {
        "title": "My Presentation",
        "subtitle": "Optional subtitle",
        "author": "Name",
        "theme": "dark",          // "dark" | "light" | "blue"
        "slides": [
            {
                "title": "Slide title",
                "layout": "title",        // "title" | "bullets" | "two-col" | "image" | "blank"
                "content": "Line1\nLine2\nLine3",
                "right": "Right column content (two-col only)",
                "image": "https://... or base64 (image layout)",
                "notes": "Speaker notes"
            }
        ]
    }

Usage:
    python create_slides.py --json spec.json -o slides.html
    python create_slides.py --title "Q2 Review" --theme dark -o slides.html
    echo '{"title":"Demo","slides":[{"title":"Hello","content":"World"}]}' | python create_slides.py
    opencode: "create a slide deck about X and run create_slides.py"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ─── Default content when none is provided ────────────────────────────────────

DEFAULT_SPEC: dict = {
    "title": "Untitled Presentation",
    "subtitle": "",
    "author": "",
    "theme": "dark",
    "slides": [
        {
            "title": "Title Slide",
            "layout": "title",
            "content": "Edit this presentation",
        }
    ],
}

# ─── Theme palettes ────────────────────────────────────────────────────────────

THEMES: dict[str, dict] = {
    "dark": {
        "bg": "#0f0f13",
        "surface": "#1a1a24",
        "border": "#2a2a3a",
        "accent": "#6366f1",
        "accent2": "#a78bfa",
        "text": "#f1f5f9",
        "muted": "#94a3b8",
        "slide_bg": "#13131a",
        "pptx_bg": "1E1B2E",
        "pptx_text": "F1F5F9",
        "pptx_accent": "6366F1",
    },
    "light": {
        "bg": "#f8fafc",
        "surface": "#ffffff",
        "border": "#e2e8f0",
        "accent": "#6366f1",
        "accent2": "#818cf8",
        "text": "#0f172a",
        "muted": "#64748b",
        "slide_bg": "#ffffff",
        "pptx_bg": "FFFFFF",
        "pptx_text": "0F172A",
        "pptx_accent": "6366F1",
    },
    "blue": {
        "bg": "#0c1a2e",
        "surface": "#102040",
        "border": "#1e3a5f",
        "accent": "#38bdf8",
        "accent2": "#7dd3fc",
        "text": "#e0f2fe",
        "muted": "#7dd3fc",
        "slide_bg": "#0d1f35",
        "pptx_bg": "0C1A2E",
        "pptx_text": "E0F2FE",
        "pptx_accent": "38BDF8",
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
<script src="https://cdn.jsdelivr.net/npm/pptxgenjs@3.12.0/dist/pptxgen.bundle.js"></script>
<script src="https://cdn.jsdelivr.net/npm/file-saver@2.0.5/dist/FileSaver.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: {bg};
    color: {text};
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }}
  /* ── Top bar ── */
  .topbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 20px;
    background: {surface};
    border-bottom: 1px solid {border};
    flex-shrink: 0;
    gap: 12px;
  }}
  .topbar-title {{ font-size: 13px; font-weight: 600; color: {text}; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .topbar-nav {{ display: flex; align-items: center; gap: 8px; }}
  .nav-btn {{
    background: {surface};
    border: 1px solid {border};
    color: {muted};
    padding: 5px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    transition: all .15s;
  }}
  .nav-btn:hover {{ color: {text}; border-color: {accent}; }}
  .slide-counter {{ font-size: 12px; color: {muted}; min-width: 60px; text-align: center; }}
  .export-btn {{
    background: {accent};
    color: #fff;
    border: none;
    padding: 6px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 600;
    transition: opacity .15s;
    white-space: nowrap;
  }}
  .export-btn:hover {{ opacity: .85; }}
  .export-btn:disabled {{ opacity: .5; cursor: not-allowed; }}
  /* ── Main area ── */
  .main {{
    display: flex;
    flex: 1;
    overflow: hidden;
  }}
  /* ── Thumbnails sidebar ── */
  .sidebar {{
    width: 160px;
    background: {surface};
    border-right: 1px solid {border};
    overflow-y: auto;
    padding: 8px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }}
  .thumb {{
    border: 2px solid {border};
    border-radius: 6px;
    cursor: pointer;
    padding: 8px 6px;
    font-size: 9px;
    color: {muted};
    background: {slide_bg};
    transition: border-color .15s;
    min-height: 72px;
    display: flex;
    flex-direction: column;
    gap: 3px;
    overflow: hidden;
  }}
  .thumb.active {{ border-color: {accent}; }}
  .thumb:hover {{ border-color: {accent2}; }}
  .thumb-num {{ font-size: 8px; color: {muted}; opacity: .6; }}
  .thumb-title {{ font-size: 9px; font-weight: 600; color: {text}; line-height: 1.2; }}
  .thumb-body {{ font-size: 8px; color: {muted}; line-height: 1.3; }}
  /* ── Slide canvas ── */
  .canvas-wrap {{
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    overflow: hidden;
  }}
  .slide {{
    background: {slide_bg};
    border: 1px solid {border};
    border-radius: 12px;
    width: 100%;
    max-width: 900px;
    aspect-ratio: 16 / 9;
    display: none;
    flex-direction: column;
    padding: 48px 56px;
    gap: 20px;
    box-shadow: 0 20px 60px rgba(0,0,0,.4);
    overflow: hidden;
    position: relative;
  }}
  .slide.active {{ display: flex; }}
  .slide-accent-bar {{
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 5px;
    background: {accent};
    border-radius: 12px 0 0 12px;
  }}
  .slide-num {{
    position: absolute;
    bottom: 16px; right: 20px;
    font-size: 11px;
    color: {muted};
    opacity: .5;
  }}
  /* layout: title */
  .layout-title {{ justify-content: center; text-align: center; }}
  .layout-title .slide-title {{
    font-size: clamp(24px, 4vw, 44px);
    font-weight: 700;
    color: {text};
    line-height: 1.15;
  }}
  .layout-title .slide-sub {{
    font-size: clamp(13px, 1.8vw, 20px);
    color: {muted};
    margin-top: 8px;
  }}
  /* layout: bullets */
  .layout-bullets .slide-title {{
    font-size: clamp(18px, 2.5vw, 30px);
    font-weight: 700;
    color: {accent2};
    flex-shrink: 0;
  }}
  .layout-bullets ul {{
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 10px;
    overflow-y: auto;
  }}
  .layout-bullets li {{
    font-size: clamp(12px, 1.6vw, 18px);
    color: {text};
    padding-left: 18px;
    position: relative;
    line-height: 1.4;
  }}
  .layout-bullets li::before {{
    content: '▸';
    position: absolute;
    left: 0;
    color: {accent};
    font-size: .8em;
    top: .1em;
  }}
  /* layout: two-col */
  .layout-two-col .slide-title {{
    font-size: clamp(16px, 2.2vw, 26px);
    font-weight: 700;
    color: {accent2};
    flex-shrink: 0;
  }}
  .cols {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    flex: 1;
    overflow: hidden;
  }}
  .col {{ display: flex; flex-direction: column; gap: 8px; overflow-y: auto; }}
  .col-label {{ font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: {accent}; }}
  .col p {{ font-size: clamp(11px, 1.4vw, 15px); color: {text}; line-height: 1.5; }}
  /* layout: blank */
  .layout-blank {{ justify-content: center; align-items: center; }}
  .layout-blank .blank-content {{
    font-size: clamp(14px, 2vw, 22px);
    color: {text};
    text-align: center;
    white-space: pre-wrap;
    line-height: 1.6;
  }}
  /* Notes bar */
  .notes-bar {{
    background: {surface};
    border-top: 1px solid {border};
    padding: 8px 20px;
    font-size: 11px;
    color: {muted};
    flex-shrink: 0;
    min-height: 32px;
    max-height: 60px;
    overflow-y: auto;
  }}
  /* Scrollbar */
  ::-webkit-scrollbar {{ width: 4px; height: 4px; }}
  ::-webkit-scrollbar-track {{ background: transparent; }}
  ::-webkit-scrollbar-thumb {{ background: {border}; border-radius: 2px; }}
</style>
</head>
<body>

<div class="topbar">
  <span class="topbar-title">{title}</span>
  <div class="topbar-nav">
    <button class="nav-btn" onclick="prevSlide()">&#8592;</button>
    <span class="slide-counter" id="counter">1 / {slide_count}</span>
    <button class="nav-btn" onclick="nextSlide()">&#8594;</button>
  </div>
  <button class="export-btn" id="exportBtn" onclick="exportPptx()">&#8595; Export PPTX</button>
</div>

<div class="main">
  <div class="sidebar" id="sidebar">{thumbnails}</div>
  <div class="canvas-wrap">
    {slides_html}
  </div>
</div>

<div class="notes-bar" id="notesBar">Speaker notes will appear here</div>

<script>
const SPEC = {spec_json};

let current = 0;
const slides = document.querySelectorAll('.slide');
const thumbs = document.querySelectorAll('.thumb');
const counter = document.getElementById('counter');
const notesBar = document.getElementById('notesBar');

function showSlide(n) {{
  slides.forEach(s => s.classList.remove('active'));
  thumbs.forEach(t => t.classList.remove('active'));
  current = Math.max(0, Math.min(n, slides.length - 1));
  slides[current].classList.add('active');
  thumbs[current].classList.add('active');
  thumbs[current].scrollIntoView({{ block: 'nearest' }});
  counter.textContent = (current + 1) + ' / ' + slides.length;
  const notes = SPEC.slides[current]?.notes || '';
  notesBar.textContent = notes || 'No speaker notes';
}}

function nextSlide() {{ showSlide(current + 1); }}
function prevSlide() {{ showSlide(current - 1); }}

document.addEventListener('keydown', e => {{
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') nextSlide();
  if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') prevSlide();
}});

// ── PPTX export via PptxGenJS ──────────────────────────────────────────────
async function exportPptx() {{
  const btn = document.getElementById('exportBtn');
  btn.disabled = true;
  btn.textContent = 'Generating…';

  try {{
    const pptx = new PptxGenJS();
    pptx.layout = 'LAYOUT_WIDE';
    pptx.title = SPEC.title || 'Presentation';
    pptx.author = SPEC.author || '';

    const BG = SPEC._theme?.pptx_bg || '1E1B2E';
    const FG = SPEC._theme?.pptx_text || 'F1F5F9';
    const ACCENT = SPEC._theme?.pptx_accent || '6366F1';
    const MUTED = '94A3B8';

    for (const sd of SPEC.slides) {{
      const slide = pptx.addSlide();
      slide.background = {{ color: BG }};

      // Accent bar
      slide.addShape(pptx.ShapeType.rect, {{
        x: 0, y: 0, w: 0.08, h: '100%',
        fill: {{ color: ACCENT }},
        line: {{ color: ACCENT }},
      }});

      const layout = sd.layout || 'bullets';
      const lines = (sd.content || '').split('\\n').filter(Boolean);

      if (layout === 'title') {{
        slide.addText(sd.title || '', {{
          x: 0.5, y: 2.8, w: 9, h: 1.2,
          fontSize: 36, bold: true, color: FG,
          align: 'center', fontFace: 'Segoe UI',
        }});
        if (sd.content) {{
          slide.addText(sd.content, {{
            x: 0.5, y: 4.1, w: 9, h: 0.8,
            fontSize: 18, color: MUTED,
            align: 'center', fontFace: 'Segoe UI',
          }});
        }}
      }} else if (layout === 'two-col') {{
        slide.addText(sd.title || '', {{
          x: 0.3, y: 0.3, w: 9.4, h: 0.7,
          fontSize: 22, bold: true, color: ACCENT, fontFace: 'Segoe UI',
        }});
        const leftLines = lines.map(t => ({{ text: t, options: {{ bullet: {{ type: 'bullet' }}, color: FG, fontSize: 14, fontFace: 'Segoe UI' }} }}));
        const rightLines = (sd.right || '').split('\\n').filter(Boolean).map(t => ({{ text: t, options: {{ bullet: {{ type: 'bullet' }}, color: FG, fontSize: 14, fontFace: 'Segoe UI' }} }}));
        if (leftLines.length) slide.addText(leftLines, {{ x: 0.3, y: 1.2, w: 4.5, h: 4.5 }});
        if (rightLines.length) slide.addText(rightLines, {{ x: 5.2, y: 1.2, w: 4.5, h: 4.5 }});
      }} else if (layout === 'blank') {{
        slide.addText(sd.content || '', {{
          x: 0.5, y: 1.5, w: 9, h: 5,
          fontSize: 16, color: FG, fontFace: 'Segoe UI',
          valign: 'middle', align: 'center',
        }});
      }} else {{
        // bullets (default)
        slide.addText(sd.title || '', {{
          x: 0.3, y: 0.3, w: 9.4, h: 0.7,
          fontSize: 22, bold: true, color: ACCENT, fontFace: 'Segoe UI',
        }});
        const bulletItems = lines.map(t => ({{
          text: t,
          options: {{ bullet: {{ type: 'bullet', indent: 10 }}, color: FG, fontSize: 15, fontFace: 'Segoe UI', paraSpaceAfter: 4 }}
        }}));
        if (bulletItems.length) {{
          slide.addText(bulletItems, {{ x: 0.4, y: 1.2, w: 9.2, h: 5.0 }});
        }}
      }}

      // Slide number
      slide.addText((SPEC.slides.indexOf(sd) + 1) + ' / ' + SPEC.slides.length, {{
        x: 8.5, y: 6.8, w: 1.3, h: 0.3,
        fontSize: 9, color: MUTED, align: 'right',
      }});

      if (sd.notes) slide.addNotes(sd.notes);
    }}

    await pptx.writeFile({{ fileName: (SPEC.title || 'presentation').replace(/[^a-z0-9]/gi, '_') + '.pptx' }});
  }} catch(e) {{
    alert('Export failed: ' + e.message);
    console.error(e);
  }} finally {{
    btn.disabled = false;
    btn.textContent = '↓ Export PPTX';
  }}
}}

// Init
showSlide(0);
</script>
</body>
</html>
"""


# ─── Slide HTML renderers ──────────────────────────────────────────────────────

def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _render_slide(sd: dict, idx: int, total: int, t: dict) -> str:
    layout = sd.get("layout", "bullets")
    title = _esc(sd.get("title", ""))
    content = sd.get("content", "")
    lines = [_esc(l) for l in content.split("\n") if l.strip()]
    active = " active" if idx == 0 else ""

    parts = [
        f'<div class="slide layout-{layout}{active}" id="slide-{idx}">',
        f'  <div class="slide-accent-bar"></div>',
        f'  <span class="slide-num">{idx + 1} / {total}</span>',
    ]

    if layout == "title":
        parts.append(f'  <div class="slide-title">{title}</div>')
        if sd.get("content"):
            parts.append(f'  <div class="slide-sub">{_esc(content)}</div>')
    elif layout == "two-col":
        right = sd.get("right", "")
        right_lines = [_esc(l) for l in right.split("\n") if l.strip()]
        parts.append(f'  <div class="slide-title">{title}</div>')
        parts.append('  <div class="cols">')
        parts.append('    <div class="col"><span class="col-label">Left</span>')
        for l in lines:
            parts.append(f'      <p>{l}</p>')
        parts.append("    </div>")
        parts.append('    <div class="col"><span class="col-label">Right</span>')
        for l in right_lines:
            parts.append(f'      <p>{l}</p>')
        parts.append("    </div></div>")
    elif layout == "blank":
        parts.append(f'  <div class="blank-content">{_esc(content)}</div>')
    else:  # bullets
        parts.append(f'  <div class="slide-title">{title}</div>')
        parts.append("  <ul>")
        for l in lines:
            parts.append(f"    <li>{l}</li>")
        parts.append("  </ul>")

    parts.append("</div>")
    return "\n".join(parts)


def _render_thumb(sd: dict, idx: int, t: dict) -> str:
    title = _esc(sd.get("title", ""))
    preview = _esc((sd.get("content") or "")[:60])
    active = " active" if idx == 0 else ""
    return (
        f'<div class="thumb{active}" onclick="showSlide({idx})">'
        f'<span class="thumb-num">{idx + 1}</span>'
        f'<span class="thumb-title">{title}</span>'
        f'<span class="thumb-body">{preview}</span>'
        f"</div>"
    )


# ─── Main ──────────────────────────────────────────────────────────────────────

def build_html(spec: dict, theme_name: str = "dark") -> str:
    theme = THEMES.get(theme_name, THEMES["dark"])
    slides = spec.get("slides", [])
    if not slides:
        slides = [{"title": "Empty", "layout": "title", "content": "No slides provided"}]

    spec["_theme"] = theme  # embed theme for JS export

    slides_html = "\n".join(_render_slide(sd, i, len(slides), theme) for i, sd in enumerate(slides))
    thumbnails = "\n".join(_render_thumb(sd, i, theme) for i, sd in enumerate(slides))
    spec_json = json.dumps(spec, ensure_ascii=False)

    return HTML_TEMPLATE.format(
        title=_esc(spec.get("title", "Presentation")),
        slide_count=len(slides),
        slides_html=slides_html,
        thumbnails=thumbnails,
        spec_json=spec_json,
        **theme,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", "-j", help="Path to JSON spec file")
    parser.add_argument("--title", help="Presentation title (quick mode)")
    parser.add_argument("--theme", default="dark", choices=list(THEMES), help="Color theme (default: dark)")
    parser.add_argument("--stdin", action="store_true", help="Read JSON spec from stdin")
    parser.add_argument("--output", "-o", default="slides.html", help="Output HTML file (default: slides.html)")
    args = parser.parse_args()

    if args.json:
        spec = json.loads(Path(args.json).read_text())
    elif args.stdin:
        spec = json.loads(sys.stdin.read())
    else:
        spec = dict(DEFAULT_SPEC)

    if args.title:
        spec["title"] = args.title
    if "theme" not in spec:
        spec["theme"] = args.theme

    html = build_html(spec, spec.get("theme", args.theme))
    out = Path(args.output)
    out.write_text(html, encoding="utf-8")
    print(f"✅ Slides created: {out.resolve()}")
    print(f"   {len(spec.get('slides', []))} slide(s) — open in browser, click 'Export PPTX' to download")


if __name__ == "__main__":
    main()
