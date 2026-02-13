"""
Jena seeding command for demo data.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import click
from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import XSD
from rich.console import Console

from naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2 import (
    ApacheJenaTDB2,
)

console = Console()

NEXUS = Namespace("urn:nexus:kg:")
FUSEKI_URL = "http://admin:abi@localhost:3030/ds"


# Get project root
def _get_project_root() -> Path:
    """Find project root by looking for libs/naas-abi directory."""
    root = Path(os.environ.get("ABI_PROJECT_ROOT", os.getcwd()))
    if not (root / "libs/naas-abi").exists():
        # Traverse up from current file
        root = Path(__file__).resolve()
        for _ in range(10):
            if (root / "libs/naas-abi").exists():
                break
            root = root.parent
        else:
            root = Path.cwd()
    return root


def _node_uri(workspace_id: str, node_id: str) -> URIRef:
    return URIRef(f"urn:nexus:workspace:{workspace_id}:node:{node_id}")


def _edge_uri(workspace_id: str, edge_id: str) -> URIRef:
    return URIRef(f"urn:nexus:workspace:{workspace_id}:edge:{edge_id}")


def json_to_nexus_rdf(json_data: dict, workspace_id: str) -> Graph:
    """Convert demo JSON to Nexus schema RDF."""
    g = Graph()
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    for node in json_data.get("nodes", []):
        subject = _node_uri(workspace_id, node["id"])
        g.add((subject, RDF.type, NEXUS.Node))
        g.add((subject, NEXUS.nodeId, Literal(node["id"])))
        g.add((subject, NEXUS.workspaceId, Literal(workspace_id)))
        g.add((subject, NEXUS.nodeType, Literal(node["type"])))
        g.add((subject, RDFS.label, Literal(node["label"])))
        g.add(
            (
                subject,
                NEXUS.properties,
                Literal(json.dumps(node.get("properties", {}))),
            )
        )
        g.add((subject, NEXUS.createdAt, Literal(now, datatype=XSD.dateTime)))
        g.add((subject, NEXUS.updatedAt, Literal(now, datatype=XSD.dateTime)))

    for edge in json_data.get("edges", []):
        subject = _edge_uri(workspace_id, edge["id"])
        g.add((subject, RDF.type, NEXUS.Edge))
        g.add((subject, NEXUS.edgeId, Literal(edge["id"])))
        g.add((subject, NEXUS.workspaceId, Literal(workspace_id)))
        g.add((subject, NEXUS.sourceId, Literal(edge["source"])))
        g.add((subject, NEXUS.targetId, Literal(edge["target"])))
        g.add((subject, NEXUS.edgeType, Literal(edge["type"])))
        g.add(
            (
                subject,
                NEXUS.properties,
                Literal(json.dumps(edge.get("properties", {}))),
            )
        )
        g.add((subject, NEXUS.createdAt, Literal(now, datatype=XSD.dateTime)))

    return g


@click.command("seed-jena")
@click.option("--reset", is_flag=True, help="Clear existing data first")
@click.option(
    "--url",
    default=FUSEKI_URL,
    help="Fuseki URL (default: http://admin:abi@localhost:3030/ds)",
)
def seed_jena(reset: bool, url: str):
    """Seed Apache Jena Fuseki with Nexus demo data."""
    
    console.print("🌱 Seeding Jena Fuseki...\n", style="bold green")
    
    # Find demo directory
    project_root = _get_project_root()
    demo_dir = project_root / "libs/naas-abi/naas_abi/apps/nexus/demo/graphs"
    
    if not demo_dir.exists():
        console.print(f"❌ Demo directory not found: {demo_dir}", style="red")
        console.print(f"   Project root: {project_root}", style="dim")
        return
    
    try:
        adapter = ApacheJenaTDB2(jena_tdb2_url=url, timeout=30)
        
        if reset:
            console.print("🗑️  Clearing existing data...")
            adapter.query("DELETE WHERE { ?s ?p ?o }")
            console.print("   ✓ Cleared\n")
        
        console.print("📊 Loading demo graphs into default graph...\n")
        
        total_nodes = 0
        total_edges = 0
        
        for json_file in sorted(demo_dir.glob("*.json")):
            with open(json_file) as f:
                data = json.load(f)
            
            workspace_id = data["id"]
            rdf_graph = json_to_nexus_rdf(data, workspace_id)
            
            adapter.insert(rdf_graph)
            
            nodes = len([t for t in rdf_graph if t[1] == RDF.type and t[2] == NEXUS.Node])
            edges = len([t for t in rdf_graph if t[1] == RDF.type and t[2] == NEXUS.Edge])
            
            total_nodes += nodes
            total_edges += edges
            
            console.print(f"   ✓ {workspace_id}: {len(rdf_graph)} triples ({nodes} nodes, {edges} edges)")
        
        # Verify
        node_count = list(
            adapter.query("SELECT (COUNT(?n) as ?c) WHERE { ?n a <urn:nexus:kg:Node> }")
        )[0]["c"]
        edge_count = list(
            adapter.query("SELECT (COUNT(?e) as ?c) WHERE { ?e a <urn:nexus:kg:Edge> }")
        )[0]["c"]
        
        console.print(f"\n✅ Successfully seeded {node_count} nodes, {edge_count} edges", style="green")
        console.print(f"\n🌐 View at: http://localhost:3030", style="cyan")
    
    except Exception as e:
        console.print(f"\n❌ Error: {e}", style="red")
        import traceback
        console.print(traceback.format_exc(), style="dim")
