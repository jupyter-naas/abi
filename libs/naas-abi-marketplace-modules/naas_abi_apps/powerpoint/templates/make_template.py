"""Generate ``TemplateMinimal.pptx``: the default template of the module.

    uv run python -m naas_abi_apps.powerpoint.templates.make_template

Three slide types the agent picks from by ``template_slide_number``. Each text
shape's alternative text (``descr``) says what goes in it: the agent reads it
from ``powerpoint_get_all_shapes_and_slides`` as ``shape_alt_text``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pptx import Presentation
from pptx.util import Cm, Pt

OUTPUT = Path(__file__).with_name("TemplateMinimal.pptx")
# Fixed properties: the presentation's identity in the graph is derived from them.
CREATED = datetime(2026, 1, 1)


def _text_box(
    slide,
    name: str,
    alt_text: str,
    left,
    top,
    width,
    height,
    size: int,
    bold: bool = False,
):
    box = slide.shapes.add_textbox(left, top, width, height)
    box.name = name
    box._element._nvXxPr.cNvPr.set("descr", alt_text)
    frame = box.text_frame
    frame.word_wrap = True
    run = frame.paragraphs[0].add_run()
    run.text = name
    run.font.size = Pt(size)
    run.font.bold = bold
    return box


def build() -> Presentation:
    presentation = Presentation()
    presentation.slide_width, presentation.slide_height = Cm(33.867), Cm(19.05)  # 16:9
    blank = presentation.slide_layouts[6]
    width = presentation.slide_width - Cm(4)

    title = presentation.slides.add_slide(blank)
    _text_box(
        title, "Title", "Presentation title", Cm(2), Cm(6), width, Cm(3), 40, bold=True
    )
    _text_box(title, "Subtitle", "One-line subtitle", Cm(2), Cm(9.5), width, Cm(2), 24)
    _text_box(
        title, "Date", "Date of the presentation", Cm(2), Cm(15), width, Cm(1.5), 14
    )

    content = presentation.slides.add_slide(blank)
    _text_box(
        content, "Title", "Slide title", Cm(2), Cm(1), width, Cm(2), 32, bold=True
    )
    _text_box(
        content,
        "Subtitle",
        "Key message of the slide",
        Cm(2),
        Cm(3.2),
        width,
        Cm(1.5),
        18,
    )
    _text_box(
        content,
        "Content",
        "Body: bullet points, one per line",
        Cm(2),
        Cm(5.2),
        width,
        Cm(12),
        16,
    )

    columns = presentation.slides.add_slide(blank)
    half = (width - Cm(1)) // 2
    _text_box(
        columns, "Title", "Slide title", Cm(2), Cm(1), width, Cm(2), 32, bold=True
    )
    _text_box(
        columns,
        "Left",
        "Left column: bullet points, one per line",
        Cm(2),
        Cm(4),
        half,
        Cm(13),
        16,
    )
    _text_box(
        columns,
        "Right",
        "Right column: bullet points, one per line",
        Cm(3) + half,
        Cm(4),
        half,
        Cm(13),
        16,
    )

    properties = presentation.core_properties
    properties.author = "naas.ai"
    properties.last_modified_by = "naas.ai"
    properties.title = "Minimal template"
    properties.created = CREATED
    properties.modified = CREATED
    return presentation


if __name__ == "__main__":
    build().save(OUTPUT)
    print(f"Wrote {OUTPUT}")
