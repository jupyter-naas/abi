"""Periodic Table of Software, HoloViz/Panel visualization app."""

from __future__ import annotations

import panel as pn
import param

from naas_abi.ontologies.periodic_table.loader import (
    BFO_BUCKET_LABELS,
    SECTION_META,
    PeriodicElement,
    extract_elements,
    load_periodic_table_graph,
)

pn.extension("tabulator", design="material", sizing_mode="stretch_width")

SECTION_ORDER = ["object", "property", "action", "interface", "intelligence", "rule"]


class ElementSelection(param.Parameterized):
    obj = param.Parameter(default=None)


IMPORT_CHAIN = [
    ("BFO", "ISO/IEC 21838-2 top-level ontology"),
    ("BFO 7 Buckets", "Seven-bucket operational distillation"),
    ("ABI Ontology", "NaasAI platform ontology (CCO-aligned)"),
    ("Periodic Table", "119 software elements for SaaS/AI systems"),
]


def _element_button(el: PeriodicElement, selected: ElementSelection) -> pn.widgets.Button:
    meta = SECTION_META.get(el.section, {})
    color = meta.get("color", "#94a3b8")

    btn = pn.widgets.Button(
        name=f"{el.number}",
        button_type="default",
        width=52,
        height=52,
        margin=(2, 2),
        styles={
            "background": color,
            "color": "#0f172a",
            "font-weight": "700",
            "font-size": "11px",
            "border": "1px solid #1e293b",
            "border-radius": "6px",
        },
    )

    def _click(event, element=el):
        selected.obj = element

    btn.on_click(_click)
    return btn


def _detail_pane(selected: ElementSelection) -> pn.Column:
    @pn.depends(selected.param.obj)
    def _render(el: PeriodicElement | None):
        if el is None:
            return pn.pane.Markdown(
                "_Select an element to see its BFO 7 bucket mapping and definition._"
            )

        section_title = SECTION_META.get(el.section, {}).get("title", el.section)
        bfo_label = el.bfo_bucket_label or BFO_BUCKET_LABELS.get(el.bfo_bucket, el.bfo_bucket)
        alt = f"\n- **Alt label:** {el.alt_label}" if el.alt_label else ""

        return pn.pane.Markdown(
            f"""
## {el.number}. {el.label}

- **Section:** {section_title}
- **IRI:** `{el.uri}`
- **BFO 7 bucket:** {bfo_label}
- **ABI class:** `{el.bfo_abi_class}`
- **BFO code:** `{el.bfo_code}`{alt}

{el.definition}
            """
        )

    return pn.Column(_render, sizing_mode="stretch_width")


def _section_grid(
    section: str, elements: list[PeriodicElement], selected: ElementSelection
) -> pn.Column:
    meta = SECTION_META[section]
    section_elements = [e for e in elements if e.section == section]
    buttons = [_element_button(el, selected) for el in section_elements]
    rows = []
    cols_per_row = 7 if section == "object" else 5
    for i in range(0, len(buttons), cols_per_row):
        rows.append(pn.Row(*buttons[i : i + cols_per_row], sizing_mode="stretch_width"))

    start, end = meta["range"]
    header = pn.pane.Markdown(
        f"### {meta['title']} ({start}-{end})",
        styles={"color": meta["color"]},
    )
    return pn.Column(header, *rows, sizing_mode="stretch_width")


def _stats_row(elements: list[PeriodicElement]) -> pn.Row:
    cards = []
    for section in SECTION_ORDER:
        meta = SECTION_META[section]
        count = sum(1 for e in elements if e.section == section)
        cards.append(
            pn.indicators.Number(
                name=meta["title"].split(" (")[0],
                value=count,
                format="{value}",
                colors=[(count, meta["color"])],
                font_size="24pt",
                title_size="10pt",
            )
        )
    return pn.Row(*cards, sizing_mode="stretch_width")


def _import_chain_pane() -> pn.pane.Markdown:
    lines = ["## Ontology import chain", ""]
    for i, (name, desc) in enumerate(IMPORT_CHAIN, start=1):
        prefix = "└─" if i == len(IMPORT_CHAIN) else "├─"
        lines.append(f"{prefix} **{name}**: {desc}")
    return pn.pane.Markdown("\n".join(lines))


def build_app() -> pn.template.FastListTemplate:
    graph = load_periodic_table_graph()
    elements = extract_elements(graph)
    selected = ElementSelection()

    title = pn.pane.Markdown(
        """
# Periodic Table of Software

The essential elements for building any SaaS product or system.
Grounded in **BFO 7 Buckets** via **ABI Ontology**. Collaboration
interfaces: **Doc**, **Sheet**, **Slide**, and **Portal**.
        """
    )

    grids = [_section_grid(section, elements, selected) for section in SECTION_ORDER]

    template = pn.template.FastListTemplate(
        title="ABI · Periodic Table of Software",
        sidebar=[
            _import_chain_pane(),
            pn.pane.Markdown("### BFO 7 bucket legend"),
            pn.pane.Markdown(
                "\n".join(f"- **{v}**" for v in BFO_BUCKET_LABELS.values())
            ),
        ],
        main=[
            title,
            _stats_row(elements),
            pn.layout.Divider(),
            *grids,
            pn.layout.Divider(),
            pn.pane.Markdown("### Element detail"),
            _detail_pane(selected),
        ],
        accent="#3b82f6",
        theme="default",
    )
    return template


def serve(show: bool = True, port: int = 5007, **kwargs) -> None:
    """Launch the Panel server."""
    pn.serve(build_app, port=port, show=show, **kwargs)


if __name__ == "__main__":
    serve()
