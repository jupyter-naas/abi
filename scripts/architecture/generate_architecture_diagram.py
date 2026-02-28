#!/usr/bin/env python3
"""Generate ABI platform architecture diagram."""

import os
from pathlib import Path
import graphviz

OUTPUT_DIR = Path(__file__).parent
os.chdir(OUTPUT_DIR)

NAVY   = "#002868"; RED    = "#BF0A30"; AMBER  = "#B06000"
GREEN  = "#1A6B2A"; PURPLE = "#5B2D8E"
C1 = "#E8EDF8"; C2 = "#FAE8EB"; C3 = "#FFF4E0"; C4 = "#E8F5E8"; C5 = "#F0E8FA"

g = graphviz.Digraph("abi_architecture", format="png")
g.attr(rankdir="TB", bgcolor="white", dpi="200", pad="0.6",
       nodesep="0.5", ranksep="0.9", fontname="Arial", fontsize="13",
       splines="polyline", compound="true")
g.attr("node", shape="box", style="filled,rounded", fontname="Arial",
       fontsize="12", margin="0.25,0.15", penwidth="1.8",
       width="2.2", height="0.7")
g.attr("edge", fontname="Arial", fontsize="10", penwidth="1.6",
       arrowsize="0.8", color="#444466")

# LAYER 1: USER LAYER
with g.subgraph(name="cluster_L1") as c:
    c.attr(label="LAYER 1  -  USER LAYER\nNexus UI  .  YasGUI  .  REST API  .  MCP  .  Element",
           style="filled,rounded", fillcolor=C1, color=NAVY,
           penwidth="3", fontname="Arial Bold", fontsize="14", fontcolor=NAVY)
    for nid, lbl in [
        ("nexus",  "Nexus UI\n(React / Next.js)"),
        ("yasgui", "YasGUI\nSPARQL Workbench"),
        ("api",    "REST API\nFastAPI"),
        ("mcp",    "MCP Server\nProtocol Interface"),
        ("element","Element\n(Matrix Client)"),
    ]:
        c.node(nid, lbl, fillcolor="#D0DAEF", color=NAVY, fontcolor="#1A1A2E")
    with c.subgraph() as s:
        s.attr(rank="same")
        for n in ["nexus","yasgui","api","mcp","element"]: s.node(n)
    for a, b in [("nexus","yasgui"),("yasgui","api"),("api","mcp"),("mcp","element")]:
        g.edge(a, b, style="invis")

# LAYER 2: AGENT LAYER
with g.subgraph(name="cluster_L2") as c:
    c.attr(label="LAYER 2  -  AGENT LAYER\nSuperAssistant orchestrator  .  Domain expert agents  .  LiteLLM / OpenRouter / Ollama",
           style="filled,rounded", fillcolor=C2, color=RED,
           penwidth="3", fontname="Arial Bold", fontsize="14", fontcolor=RED)
    for nid, lbl in [
        ("super",   "SuperAssistant\nOrchestrator"),
        ("ag1",     "Domain Agent\n(Custom)"),
        ("ag2",     "Analytics Agent"),
        ("ag3",     "Integration Agent"),
        ("ag4",     "Automation Agent"),
    ]:
        c.node(nid, lbl, fillcolor="#F5D6DB", color=RED, fontcolor="#1A1A2E")
    with c.subgraph() as s:
        s.attr(rank="same")
        for n in ["super","ag1","ag2","ag3","ag4"]: s.node(n)
    for a, b in [("super","ag1"),("ag1","ag2"),("ag2","ag3"),("ag3","ag4")]:
        g.edge(a, b, style="invis")

# LAYER 3: STORAGE LAYER
with g.subgraph(name="cluster_L3") as c:
    c.attr(label="LAYER 3  -  STORAGE LAYER\nKnowledge graph  .  Vector store  .  Relational  .  Object storage  .  Cache",
           style="filled,rounded", fillcolor=C3, color=AMBER,
           penwidth="3", fontname="Arial Bold", fontsize="14", fontcolor=AMBER)
    for nid, lbl in [
        ("jena",   "Jena / Fuseki\nBFO-RDF  SPARQL"),
        ("qdrant", "Qdrant\nVector Store"),
        ("pg",     "PostgreSQL\nAgent Memory"),
        ("minio",  "MinIO\nObject Storage"),
        ("redis",  "Redis\nCache / KV"),
    ]:
        c.node(nid, lbl, fillcolor="#FDEBC8", color=AMBER, fontcolor="#1A1A2E")
    with c.subgraph() as s:
        s.attr(rank="same")
        for n in ["jena","qdrant","pg","minio","redis"]: s.node(n)
    for a, b in [("jena","qdrant"),("qdrant","pg"),("pg","minio"),("minio","redis")]:
        g.edge(a, b, style="invis")

# LAYER 4: EXECUTION LAYER
with g.subgraph(name="cluster_L4") as c:
    c.attr(label="LAYER 4  -  EXECUTION LAYER\nOntologies  .  Pipelines  .  Event bus  .  Connectors  .  Proxy  .  Observability",
           style="filled,rounded", fillcolor=C4, color=GREEN,
           penwidth="3", fontname="Arial Bold", fontsize="14", fontcolor=GREEN)
    for nid, lbl in [
        ("bfo",   "BFO Ontologies\nISO 21838-2"),
        ("dag",   "Dagster\nPipelines"),
        ("rmq",   "RabbitMQ\nEvent Bus"),
        ("src",   "Source Connectors\nAPIs  .  Files  .  DBs"),
        ("caddy", "Caddy\nReverse Proxy  TLS"),
        ("otel",  "OpenTelemetry\n+ Grafana"),
    ]:
        c.node(nid, lbl, fillcolor="#C8E6C9", color=GREEN, fontcolor="#1A1A2E")
    with c.subgraph() as s:
        s.attr(rank="same")
        for n in ["bfo","dag","rmq","src","caddy","otel"]: s.node(n)
    for a, b in [("bfo","dag"),("dag","rmq"),("rmq","src"),("src","caddy"),("caddy","otel")]:
        g.edge(a, b, style="invis")

# LAYER 5: FEDERATION LAYER
with g.subgraph(name="cluster_L5") as c:
    c.attr(label="LAYER 5  -  FEDERATION LAYER\nFederated messaging  .  Multi-site mesh VPN (Enterprise)",
           style="filled,rounded", fillcolor=C5, color=PURPLE,
           penwidth="3", fontname="Arial Bold", fontsize="14", fontcolor=PURPLE)
    for nid, lbl in [
        ("matrix",    "Matrix (Synapse)\nFederated Messaging"),
        ("headscale", "Headscale\nWireGuard VPN (Enterprise)"),
        ("element2",  "Element\nMatrix Client"),
    ]:
        c.node(nid, lbl, fillcolor="#E0D0F5", color=PURPLE, fontcolor="#1A1A2E")
    with c.subgraph() as s:
        s.attr(rank="same")
        for n in ["matrix","headscale","element2"]: s.node(n)
    for a, b in [("matrix","headscale"),("headscale","element2")]:
        g.edge(a, b, style="invis")

# FLOW EDGES
for s, t in [("nexus","super"),("api","super"),("mcp","super")]:
    g.edge(s, t, color=NAVY, penwidth="1.8")
for s, t in [("super","jena"),("super","qdrant"),("ag1","pg"),("ag2","minio"),("super","redis")]:
    g.edge(s, t, color=RED, penwidth="1.8")
for s, t in [("jena","src"),("jena","rmq"),("qdrant","dag")]:
    g.edge(s, t, color=AMBER, penwidth="1.8")
for s, t in [("caddy","matrix"),("dag","matrix")]:
    g.edge(s, t, color=GREEN, penwidth="1.8")

g.render("abi_architecture", cleanup=True)
kb = (OUTPUT_DIR / "abi_architecture.png").stat().st_size // 1024
print(f"  OK  abi_architecture.png  ({kb} KB)")

if __name__ == "__main__":
    pass
