"""Interactive pyvis network graph of the Periodic Table ontology."""

from __future__ import annotations

import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Timer
from urllib.parse import urlparse

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from naas_abi.ontologies.periodic_table.loader import (
    SECTION_META,
    label_for,
    load_periodic_table_graph,
)

OUTPUT_HTML = Path(__file__).parent / "periodic_table_graph.html"

COLORS = {
    "element": "#e2e8f0",
    "section": "#1e293b",
    "bfo": "#7c3aed",
    "abi": "#0ea5e9",
    "cco": "#f97316",
}
SECTION_COLORS = {k: v["color"] for k, v in SECTION_META.items()}


def _short(uri: str) -> str:
    for prefix in (
        "http://ontology.naas.ai/zen/pts/",
        "http://ontology.naas.ai/zen/",
        "http://ontology.naas.ai/abi/",
        "http://purl.obolibrary.org/obo/",
        "https://www.commoncoreontologies.org/",
    ):
        if uri.startswith(prefix):
            return uri[len(prefix) :]
    return urlparse(uri).path.rsplit("/", 1)[-1] or uri


def _node_kind(uri: str) -> str:
    if "zen/pts/" in uri:
        return "section" if _short(uri).startswith("Software") else "element"
    if "purl.obolibrary.org/obo/" in uri:
        return "bfo"
    if "ontology.naas.ai/abi/" in uri:
        return "abi"
    if "commoncoreontologies.org/" in uri:
        return "cco"
    return "element"


def _element_section(g: Graph, uri: URIRef) -> str | None:
    val = g.value(uri, URIRef("http://ontology.naas.ai/zen/pts/section"))
    return str(val) if val else None


def build_pyvis_graph(g: Graph | None = None):
    from pyvis.network import Network

    graph = g or load_periodic_table_graph()

    net = Network(
        height="900px",
        width="100%",
        bgcolor="#0f172a",
        font_color="#f8fafc",
        directed=True,
        notebook=False,
        cdn_resources="remote",
    )

    added: set[str] = set()
    edges: set[tuple[str, str]] = set()

    def add_node(uri: str, label: str | None = None, color: str | None = None) -> None:
        if uri in added:
            return
        kind = _node_kind(uri)
        section = _element_section(graph, URIRef(uri)) if kind == "element" else None
        display = label or label_for(graph, uri)
        net.add_node(
            uri,
            label=display,
            title=f"{display}\n{uri}",
            color=color or SECTION_COLORS.get(section or "", COLORS.get(kind, COLORS["element"])),
            size=14 if kind == "element" else 20,
        )
        added.add(uri)

    def add_edge(src: str, dst: str, color: str = "#64748b", width: float = 1.0) -> None:
        key = (src, dst)
        if key in edges:
            return
        add_node(src)
        add_node(dst, label_for(graph, dst))
        net.add_edge(src, dst, color=color, width=width, arrows="to")
        edges.add(key)

    for cls in graph.subjects(RDF.type, OWL.Class):
        uri = str(cls)
        if uri.startswith("http://ontology.naas.ai/zen/pts/Software"):
            add_node(uri, label_for(graph, uri), COLORS["section"])
        elif uri.startswith("http://ontology.naas.ai/abi/"):
            add_node(uri, label_for(graph, uri), COLORS["abi"])
        elif uri.startswith("http://ontology.naas.ai/zen/pts/"):
            if _short(uri).startswith("Software"):
                continue
            number = graph.value(cls, URIRef("http://ontology.naas.ai/zen/pts/elementNumber"))
            label = graph.value(cls, RDFS.label)
            title = f"{number}. {label}" if number else str(label or _short(uri))
            section = _element_section(graph, cls)
            add_node(uri, str(title), SECTION_COLORS.get(section or "", COLORS["element"]))

    for s, o in graph.subject_objects(RDFS.subClassOf):
        if isinstance(o, URIRef):
            add_edge(str(s), str(o), "#60a5fa", 0.8)

    maps_to = URIRef("http://ontology.naas.ai/zen/mapsToBFOBucket")
    for s, o in graph.subject_objects(maps_to):
        if isinstance(o, URIRef):
            add_edge(str(s), str(o), "#a78bfa", 1.0)

    maps_code = URIRef("http://ontology.naas.ai/zen/mapsToBFOCode")
    for s, o in graph.subject_objects(maps_code):
        if isinstance(o, URIRef):
            add_node(str(o), label_for(graph, o), COLORS["bfo"])
            add_edge(str(s), str(o), "#c4b5fd", 0.5)

    for s, o in graph.subject_objects(OWL.equivalentClass):
        if isinstance(o, URIRef):
            add_edge(str(s), str(o), "#38bdf8", 0.6)

    for s, o in graph.subject_objects(SKOS.closeMatch):
        if isinstance(o, URIRef):
            add_node(str(o), label_for(graph, o), COLORS["cco"])
            add_edge(str(s), str(o), "#fb923c", 0.6)

    renders = URIRef("http://ontology.naas.ai/zen/pts/renders")
    for s, o in graph.subject_objects(renders):
        if isinstance(o, URIRef):
            add_edge(str(s), str(o), "#facc15", 1.0)

    net.set_options(
        """
    {
      "physics": {
        "enabled": true,
        "barnesHut": {
          "gravitationalConstant": -4800,
          "centralGravity": 0.06,
          "springLength": 192,
          "springConstant": 0.035,
          "avoidOverlap": 1,
          "damping": 0.22
        },
        "stabilization": { "enabled": true, "iterations": 500, "fit": true }
      },
      "nodes": { "margin": 12 },
      "edges": { "smooth": false },
      "interaction": { "hover": true, "navigationButtons": true, "zoomView": true, "dragView": true }
    }
    """
    )
    return net


def _inject_stabilize_script(html: str) -> str:
    script = """
<script>
  window.addEventListener("load", function () {
    if (typeof network === "undefined") return;
    network.once("stabilizationIterationsDone", function () {
      network.setOptions({ physics: { enabled: false } });
    });
  });
</script>
"""
    return html.replace("</body>", script + "</body>")


def write_graph_html(path: Path | None = None) -> Path:
    out = path or OUTPUT_HTML
    out.parent.mkdir(parents=True, exist_ok=True)
    net = build_pyvis_graph()
    net.write_html(str(out), notebook=False)
    out.write_text(_inject_stabilize_script(out.read_text(encoding="utf-8")), encoding="utf-8")
    return out


def serve_graph(port: int = 5007, open_browser: bool = True) -> None:
    import os

    out = write_graph_html()
    url = f"http://127.0.0.1:{port}/{out.name}"
    print(f"Periodic Table graph: {url}")
    print(f"Written: {out}")

    os.chdir(out.parent)
    server = ThreadingHTTPServer(("127.0.0.1", port), SimpleHTTPRequestHandler)
    if open_browser:
        Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
