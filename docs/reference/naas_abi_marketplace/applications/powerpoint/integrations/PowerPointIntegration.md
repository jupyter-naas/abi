# PowerPointIntegration

## What it is
- A `python-pptx`-based integration for creating, inspecting, and editing PowerPoint (`.pptx`) presentations.
- Supports: creating from a template, adding slides/shapes/text/images/tables, duplicating slides, updating shape text while preserving formatting, exporting bytes, and editing slide notes.

## Public API

### Configuration
- `PowerPointIntegrationConfiguration(template_path: Optional[str] = None)`
  - Optional default path to a `.pptx` template used by `create_presentation()`.

### Class: `PowerPointIntegration`
- `create_presentation(template_path: Optional[str] = None) -> Presentation`
  - Create/open a presentation. Uses `template_path` arg or configuration `template_path`, else creates a blank presentation.
- `save_presentation(presentation, output_path: str) -> None`
  - Save a presentation to disk.
- `list_slides(presentation, text: bool = False) -> List[dict]`
  - Return slide/shape inventory (shape id/type/text/position/size/rotation, alt text, etc.).  
  - Note: `text` parameter is accepted but not used.
- `get_shapes_from_slide(slide_number: int, presentation: Optional[Presentation] = None) -> List[Dict[str, Any]]`
  - Return shape inventory for a single slide. If `presentation` is `None`, creates one via `create_presentation()`.
- `get_all_shapes_and_slides(presentation: Optional[Presentation] = None) -> List[Dict[str, Any]]`
  - Return shape inventory for all slides. If `presentation` is `None`, creates one via `create_presentation()`.
- `add_slide(presentation: Optional[Presentation] = None, layout_index: int = 6) -> Tuple[Presentation, int]`
  - Add a slide using the given layout index (default `6`, typically “Blank”). Returns `(presentation, new_slide_index)`.
- `add_shape(presentation, slide_index: int, shape_type: int, left: float, top: float, width: float, height: float, ..., text: Optional[str]=None, ...) -> Presentation`
  - Add an auto-shape to a slide, optionally setting text and simple styling.
  - Uses `Cm()` for positioning/sizing (despite docstrings mentioning inches).
- `add_text_box(presentation, slide_index: int, left: float, top: float, width: float, height: float, text: str, ...) -> Presentation`
  - Add a text box with alignment, line spacing, and basic font styling.
  - Uses `Cm()` for geometry.
- `update_shape(presentation, slide_index: int, shape_id: int, text: Optional[str]=None, fill_color: Optional[Tuple[int,int,int]]=None, line_color: Optional[Tuple[int,int,int]]=None, left/top/width/height: Optional[float]=None) -> Presentation`
  - Update an existing shape by `shape_id`.
  - If `text` is provided, replaces the text while attempting to preserve formatting from the first run of the first paragraph.
  - Adds limited formatting behavior:
    - If a line contains `PREFIX: rest` (excluding `Source:`), `PREFIX:` is bolded.
    - Markdown-style links like `[label](url)` are converted to a run with hyperlink; label displayed as `(label)`.
- `add_image(presentation, slide_index: int, image_path: str, left: float, top: float, width: Optional[float]=None, height: Optional[float]=None) -> Presentation`
  - Add an image from a file path. Uses `Cm()` units; `width`/`height` optional.
- `add_table(presentation, slide_index: int, rows: int, cols: int, left: float, top: float, width: float, height: float, data: Optional[List[List[str]]]=None) -> Presentation`
  - Add a table and optionally populate cell text.
- `replace_table(presentation, slide_index: int, shape_id: int, data: List[List[str]]) -> Presentation`
  - Remove an existing table shape (by `shape_id`) and recreate it at the same position/size with new data.
- `get_presentation_bytes(presentation) -> bytes`
  - Save the presentation into an in-memory `bytes` payload.
- `set_slide_format(presentation, slide_index: int, background_color: Optional[Tuple[int,int,int]]=None, title: Optional[str]=None, subtitle: Optional[str]=None) -> Presentation`
  - Set slide background color and update title/subtitle placeholders when present.
- `duplicate_slide(source_presentation, source_slide_number: int, presentation) -> Tuple[Presentation, int]`
  - Duplicate a slide from `source_presentation` into `presentation`, attempting to match layout name in the destination.
  - Copies shapes:
    - Pictures/placeholders with empty text: re-adds picture from image blob (fallback: rectangle with message).
    - Other shapes: deep-copies XML element into destination slide.
  - Copies notes text when available.
- `remove_all_slides(presentation) -> Presentation`
  - Deletes all slides from a presentation.
- `update_notes(presentation, slide_number: int, sources: List[str]) -> Presentation`
  - Updates slide notes by adding a **Sources:** section and appending unique sources as lines prefixed with `• `.
  - If a “Sources:” paragraph exists, it removes subsequent paragraphs in the notes frame before adding new items.

### Function: `as_tools(configuration: PowerPointIntegrationConfiguration) -> list`
- Returns LangChain `StructuredTool` wrappers:
  - `powerpoint_get_shapes_from_slide(slide_number: int)`
  - `powerpoint_get_all_shapes_and_slides()`
- Each tool uses an internal `PowerPointIntegration(configuration)` instance.

## Configuration/Dependencies
- Depends on:
  - `python-pptx` (`pptx`) for presentation manipulation.
  - `naas_abi_core` for `logger` and base `Integration` / `IntegrationConfiguration`.
  - `langchain_core` + `pydantic` only when calling `as_tools()`.
- Units:
  - Geometry passed to most methods is converted via `pptx.util.Cm(...)` (values interpreted as centimeters).

## Usage

```python
from naas_abi_marketplace.applications.powerpoint.integrations.PowerPointIntegration import (
    PowerPointIntegration,
    PowerPointIntegrationConfiguration,
)
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN

cfg = PowerPointIntegrationConfiguration(template_path=None)
pptx_integ = PowerPointIntegration(cfg)

prs = pptx_integ.create_presentation()
prs, idx = pptx_integ.add_slide(prs, layout_index=6)

prs = pptx_integ.add_text_box(
    prs, idx, left=1, top=1, width=10, height=2,
    text="Title: Hello",
    align=PP_ALIGN.LEFT,
    font_size=18,
)

prs = pptx_integ.add_shape(
    prs, idx, shape_type=MSO_AUTO_SHAPE_TYPE.RECTANGLE,
    left=1, top=3.5, width=10, height=2,
    text="Note: [Source](https://example.com)",
    fill_color=(240, 240, 240),
)

pptx_integ.save_presentation(prs, "output.pptx")
```

## Caveats
- `list_slides(..., text=False)` accepts `text` but does not use it.
- Several docstrings mention “inches”; the implementation uses `Cm()` (centimeters).
- `update_shape()` relies on internal `python-pptx` XML manipulation (`_element`, `_p`, `_r`) and may be sensitive to `python-pptx` version changes.
- `update_notes()` simulates bullets by prefixing `• ` (notes text frame bullet formatting is not used).
