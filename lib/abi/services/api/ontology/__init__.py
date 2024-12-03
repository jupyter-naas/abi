from fastapi import APIRouter, HTTPException, Query
from abi.ontology import OntologyManager, OntologyLevel
from typing import List, Dict, Optional
from analytics.visualization.ontology_graph import OntologyVisualizer
from fastapi.responses import HTMLResponse

router = APIRouter()
ontology_manager = OntologyManager()

@router.get("/structure")
async def get_ontology_structure():
    """Get current ontology structure"""
    return ontology_manager.export_level_structure()

@router.get("/ontologies/{level}")
async def get_ontologies_by_level(level: OntologyLevel):
    """Get ontologies in a specific level"""
    return ontology_manager.get_ontologies_by_level(level)

@router.get("/ontology/{level}/{name}")
async def get_ontology_details(
    level: OntologyLevel, 
    name: str,
    include_classes: bool = Query(True, description="Include class definitions"),
    include_properties: bool = Query(True, description="Include property definitions"),
    include_individuals: bool = Query(True, description="Include individual instances")
):
    """Get detailed information about a specific ontology"""
    return ontology_manager.get_ontology_details(level, name, include_classes, include_properties, include_individuals)

@router.get("/query")
async def query_ontology(q: str = Query(..., description="SPARQL query to execute")):
    """Execute SPARQL query against the ontologies"""
    results = ontology_manager.query_ontology(q)
    if results is None:
        raise HTTPException(status_code=400, detail="Invalid SPARQL query")
    return results

@router.get("/visualize", response_class=HTMLResponse)
async def visualize_ontology(max_nodes: int = Query(150, description="Maximum number of nodes to display")):
    """Generate an interactive visualization of the ontology"""
    try:
        visualizer = OntologyVisualizer()
        visualizer.load_ontology()
        visualizer.create_visualization(max_nodes=max_nodes)
        
        output_path = "assets/static/ontology_graph.html"
        visualizer.save_visualization(output_path)
        
        with open(output_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
            
        return HTMLResponse(content=html_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating visualization: {str(e)}")
