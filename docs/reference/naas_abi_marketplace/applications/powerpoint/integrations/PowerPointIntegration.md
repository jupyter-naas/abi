# PowerPointIntegration

## What it is
- A `python-pptx`-based integration for creating, inspecting, and editing PowerPoint (`.pptx`) presentations.
- Supports:
  - Creating/opening presentations (optionally from a template)
  - Listing slides and shapes (including geometry, rotation, alt text)
  - Adding slides, shapes, text boxes, images, and tables
  - Updating shape text (with partial formatting preservation and link handling)
  - Replacing existing tables by recreating them in place
  - Duplicating slides across presentations (including notes)
  - Exporting a presentation to bytes
  - Updating slide background/title/subtitle and notes “Sources” section
  - Removing all slides

## Public API

### Configuration
- `PowerPointIntegrationConfiguration(template_path: str | None = None)`
  - Optional default `.pptx` template path used by `create_presentation()` when no explicit `template_path` is provided.

### Class: `PowerPointIntegration`
- `create_presentation(template_path: str | None = None) -> pptx.presentation.Presentation`
  - Create/open a presentation from `template_path` (arg) or configured `template_path`, otherwise creates a blank presentation.
- `save_presentation(presentation, output_path: str) -> None`
  - Save a presentation to a file.
- `list_slides(presentation, text: bool = False) -> list[dict]`
  - Return a slide list with per-slide shape inventories (id/type/text/position/size/rotation/alt text).
  - Note: `text` argument is accepted but not used in the implementation.
- `get_shapes_from_slide(slide_number: int, presentation: Presentation | None = None) -> list[dict[str, Any]]`
  - Return shape inventory for one slide; creates a presentation via `create_presentation()` if `presentation` is `None`.
- `get_all_shapes_and_slides(presentation: Presentation | None = None) -> list[dict[str, Any]]`
  - Return all slides with their shape inventories; creates a presentation if `presentation` is `None`.
- `add_slide(presentation: Presentation | None = None, layout_index: int = 6) -> tuple[Presentation, int]`
  - Add a slide using `layout_index` and return `(presentation, new_slide_index)`.
- `add_shape(presentation, slide_index: int, shape_type: int, left: float, top: float, width: float, height: float, ..., text: str | None = None, ...) -> Presentation`
  - Add an auto-shape; optionally set text and basic font/fill/line styling.
- `add_text_box(presentation, slide_index: int, left: float, top: float, width: float, height: float, text: str, ...) -> Presentation`
  - Add a text box; supports alignment, optional line spacing, and basic font styling.
- `update_shape(presentation, slide_index: int, shape_id: int, ..., text: str | None = None, ...) -> Presentation`
  - Update an existing shape by `shape_id`:
    - If `text` is provided: replaces text while attempting to preserve formatting from the first run of the first paragraph.
    - Adds limited formatting behaviors:
      - For lines containing `PREFIX: rest` (excluding lines containing `Source:`), `PREFIX:` is bold.
      - Markdown-style links `[label](url)` are converted to a displayed `(label)` run with a hyperlink address.
  - Can also update fill/line color and geometry.
- `add_image(presentation, slide_index: int, image_path: str, left: float, top: float, width: float | None = None, height: float | None = None) -> Presentation`
  - Add an image from a file path; optional width/height.
- `add_table(presentation, slide_index: int, rows: int, cols: int, left: float, top: float, width: float, height: float, data: list[list[str]] | None = None) -> Presentation`
  - Add a table; optionally populate cell text from `data`.
- `replace_table(presentation, slide_index: int, shape_id: int, data: list[list[str]]) -> Presentation`
  - Replace an existing table shape (by `shape_id`) by removing it and recreating a new table at the same position/size.
- `get_presentation_bytes(presentation) -> bytes`
  - Save to an in-memory `bytes` payload.
- `set_slide_format(presentation, slide_index: int, background_color: tuple[int,int,int] | None = None, title: str | None = None, subtitle: str | None = None) -> Presentation`
  - Set slide background color; update title (`slide.shapes.title`) and subtitle (`slide.placeholders[1]`) when present.
- `duplicate_slide(source_presentation, source_slide_number: int, presentation) -> tuple[Presentation, int]`
  - Duplicate a slide from `source_presentation` into `presentation`:
    - Selects a destination layout by matching layout name (with fallbacks).
    - Clears layout shapes on the new slide.
    - Copies pictures/placeholders-with-empty-text by re-adding from image blob; otherwise deep-copies shape XML.
    - Copies notes text if source slide has notes.
- `remove_all_slides(presentation) -> Presentation`
  - Delete all slides from a presentation by dropping slide relationships.
- `update_notes(presentation, slide_number: int, sources: list[str]) -> Presentation`
  - Adds/updates a “Sources:” section in slide notes and appends unique sources as lines prefixed with `• `.
  - If “Sources:” exists, removes subsequent note paragraphs before adding new items.

### Function: `as_tools(configuration: PowerPointIntegrationConfiguration) -> list`
- Returns LangChain `StructuredTool` wrappers bound to an internal `PowerPointIntegration` instance:
  - `powerpoint_get_shapes_from_slide(slide_number: int)`
  - `powerpoint_get_all_shapes_and_slides()`

## Configuration/Dependencies
- Dependencies:
  - `python-pptx` (`pptx`) for PowerPoint manipulation.
  - `naas_abi_core` for `logger` and base `Integration` / `IntegrationConfiguration`.
  - `langchain_core` and `pydantic` only when using `as_tools()`.
- Units:
  - Geometry parameters (`left`, `top`, `width`, `height`) are converted using `pptx.util.Cm(...)` (centimeters), even where docstrings mention inches.

## Usage

```python
from naas_abi_marketplace.applications.powerpoint.integrations.PowerPointIntegration import (
    PowerPointIntegration,
    PowerPointIntegrationConfiguration,
)
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN

cfg = PowerPointIntegrationConfiguration(template_path=None)
ppt = PowerPointIntegration(cfg)

prs = ppt.create_presentation()
prs, slide_idx = ppt.add_slide(prs, layout_index=6)

prs = ppt.add_text_box(
    prs, slide_idx, left=1, top=1, width=12, height=2,
    text="Title: Hello",
    align=PP_ALIGN.LEFT,
    font_size=18,
)

prs = ppt.add_shape(
    prs, slide_idx,
    shape_type=MSO_AUTO_SHAPE_TYPE.RECTANGLE,
    left=1, top=3.5, width=12, height=2,
    text="Note: [Example](https://example.com)",
    fill_color=(240, 240, 240),
    line_color=(0, 0, 0),
)

ppt.save_presentation(prs, "output.pptx")
```

## Caveats
- `list_slides(..., text=False)` accepts `text` but does not use it.
- Several docstrings mention inches; implementation uses centimeters via `Cm(...)`.
- `update_shape()` uses internal `python-pptx` structures (`_p`, `_r`, `_element`) and may be sensitive to `python-pptx` version changes.
- Notes “bullets” in `update_notes()` are simulated with a `• ` prefix (not true bullet formatting).
