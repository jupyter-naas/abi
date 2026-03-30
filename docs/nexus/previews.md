# Preview modes

The Lab editor supports rich previews for Markdown and HTML/slide files alongside the Monaco editor.

## Markdown preview

Triggered automatically when you open any `.md` or `.mdx` file.

### View modes

| Button | Mode | Description |
|---|---|---|
| `</>` Code | Edit | Monaco editor only |
| `⫿` Split | Split | Editor left, preview right |
| `👁` Preview | Preview | Preview only (default on open) |

### Rendering

Uses `react-markdown` + `remark-gfm` for GitHub Flavored Markdown:
- Tables, task lists, strikethrough, autolinks
- Fenced code blocks with monospace font
- Blockquotes, nested lists
- Images with rounded border

Styles are injected as inline CSS (no Tailwind typography plugin dependency) to match VS Code's Markdown preview appearance.

### Source

`.abi/libs/naas-abi/naas_abi/apps/nexus/apps/web/src/app/workspace/[workspaceId]/lab/page.tsx` — `MarkdownPreview` component, `MD_STYLES` constant.

---

## HTML / Slides preview

Triggered automatically when you open any `.html` or `.htm` file.

### View modes

| Button | Mode | Description |
|---|---|---|
| `</>` Edit | Edit | Monaco editor only |
| `⫿` Split | Split | Editor left, preview right (default on open) |
| `👁` Slides | Slides | Full-width preview only |

### How the preview works

1. **CSS inlining** — any `<link rel="stylesheet" href="...">` with a relative path is fetched via the Lab API and inlined as a `<style>` block, making the `srcdoc` iframe self-contained.

2. **Image loading** — a `<base href="{apiUrl}/api/lab/fs/raw/{fileDir}/">` tag is injected so that relative image paths (e.g. `images/hero.jpg`) resolve through the raw-file API endpoint. This is necessary because `srcdoc` iframes have no URL origin.

3. **Universal scaler** — a small script is injected into `<head>` that:
   - Overrides any existing `scaleSlides` function in the HTML
   - Scales each `.slide` (1280×720) to fit its container width on every `resize`
   - Handles both the `slide-wrapper` variant and bare `.slide` variant

4. **Reload button** — re-runs the full CSS inline + scaler injection process. Use after editing `slides.css` separately.

5. **Full button** — opens the processed HTML in a new browser tab for full-screen presentation.

### Reload behaviour

The iframe remounts (via React `key`) every time:
- The file content changes (after save)
- You click **Reload**

### Source

`.abi/libs/naas-abi/naas_abi/apps/nexus/apps/web/src/app/workspace/[workspaceId]/lab/page.tsx` — `prepareHtmlPreview`, `AIA_SCALER_SCRIPT`, `HtmlPreview`, `HtmlViewToggle`.
