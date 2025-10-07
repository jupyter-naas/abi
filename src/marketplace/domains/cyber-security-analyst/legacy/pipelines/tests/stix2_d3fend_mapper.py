import json
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, RDFS, XSD, OWL

def map_stix_to_d3fend(stix_json_path, output_ttl_path):
    """
    Maps STIX 2.0 objects to D3FEND ontology and outputs as TTL file.
    
    Args:
        stix_json_path: Path to the STIX 2.0 JSON file
        output_ttl_path: Path to output the resulting TTL file
    """
    # Load the STIX JSON data
    with open(stix_json_path, 'r') as f:
        stix_data = json.load(f)
    
    # Initialize RDF graph
    g = Graph()
    
    # Define namespaces
    D3F = Namespace("http://d3fend.mitre.org/ontologies/d3fend.owl#")
    STIX = Namespace("http://docs.oasis-open.org/cti/ns/stix#")
    ABI = Namespace("http://ontology.naas.ai/abi/")
    
    # Bind namespaces to prefixes for readability
    g.bind("d3f", D3F)
    g.bind("stix", STIX)
    g.bind("abi", ABI)
    
    # Dictionary to store STIX ID to D3FEND URI mappings
    id_mappings = {}
    
    # Define mappings between STIX types and D3FEND classes
    stix_to_d3fend_class = {
        "threat-actor": D3F.Agent,               # Map to more general Agent class
        "attack-pattern": D3F.OffensiveTechnique, # Map to offensive technique
        "indicator": D3F.DigitalArtifact,        # Map to general digital artifact
        "identity": D3F.Agent,                   # Map to Agent class
        "report": D3F.DigitalArtifact,          # Map to general digital artifact
        "observed-data": D3F.DigitalArtifact,    # Map to general digital artifact
        "malware": D3F.Software,                 # Map to Software class
        "url": D3F.URL                           # Keep existing URL mapping
    }
    
    # Process each object in the STIX bundle
    for obj in stix_data.get("objects", []):
        obj_type = obj.get("type")
        obj_id = obj.get("id")
        
        # Skip if no ID or type
        if not obj_id or not obj_type:
            continue
        
        # Create a D3FEND URI for this object
        d3f_uri = ABI[obj_id]
        g.add((d3f_uri, RDF.type, OWL.NamedIndividual))
        id_mappings[obj_id] = d3f_uri

        # Map to D3FEND class if a mapping exists
        if obj_type in stix_to_d3fend_class:
            g.add((d3f_uri, RDF.type, stix_to_d3fend_class[obj_type]))
        else:
            # If no specific mapping, use a generic class
            g.add((d3f_uri, RDF.type, D3F.CyberTechnique))

        # Add name/label if available
        if "name" in obj:
            g.add((d3f_uri, RDFS.label, Literal(obj["name"])))
        
        # Add description if available
        if "description" in obj:
            g.add((d3f_uri, D3F.description, Literal(obj["description"])))

        # Add created if available
        if "created" in obj:
            g.add((d3f_uri, ABI.created, Literal(obj["created"].split(".")[0], datatype=XSD.dateTime)))

        # Add modified if available
        if "modified" in obj:
            g.add((d3f_uri, ABI.modified, Literal(obj["modified"].split(".")[0], datatype=XSD.dateTime)))

        # Add spec version if available
        if "spec_version" in obj:
            g.add((d3f_uri, ABI.spec_version, Literal(obj["spec_version"])))
        
        # # Handle special properties for different types
        # if obj_type == "attack-pattern":
        #     # For MITRE ATT&CK patterns, add kill chain phases
        #     for phase in obj.get("kill_chain_phases", []):
        #         kill_chain = phase.get("kill_chain_name")
        #         phase_name = phase.get("phase_name")
        #         if kill_chain and phase_name:
        #             phase_node = BNode()
        #             g.add((phase_node, RDF.type, D3F.KillChainPhase))
        #             g.add((phase_node, D3F.kill_chain_name, Literal(kill_chain)))
        #             g.add((phase_node, D3F.phase_name, Literal(phase_name)))
        #             g.add((d3f_uri, D3F.has_kill_chain_phase, phase_node))
        
        # # Handle external references
        # for ref in obj.get("external_references", []):
        #     ref_node = BNode()
        #     g.add((ref_node, RDF.type, D3F.ExternalReference))
            
        #     if "source_name" in ref:
        #         g.add((ref_node, D3F.source_name, Literal(ref["source_name"])))
            
        #     if "url" in ref:
        #         g.add((ref_node, D3F.url, Literal(ref["url"])))
                
        #     if "external_id" in ref:
        #         g.add((ref_node, D3F.external_id, Literal(ref["external_id"])))
            
        #     g.add((d3f_uri, D3F.has_external_reference, ref_node))
    
    # # Process relationships after all objects have been created
    # for obj in stix_data.get("objects", []):
    #     obj_id = obj.get("id")
        
    #     # Skip if no ID or not in our mappings
    #     if not obj_id or obj_id not in id_mappings:
    #         continue
            
    #     source_uri = id_mappings[obj_id]
        
    #     # Handle created_by references
    #     if "created_by_ref" in obj and obj["created_by_ref"] in id_mappings:
    #         target_uri = id_mappings[obj["created_by_ref"]]
    #         g.add((source_uri, D3F.created_by, target_uri))
        
    #     # Handle object references in reports
    #     if obj.get("type") == "report" and "object_refs" in obj:
    #         for ref_id in obj["object_refs"]:
    #             if ref_id in id_mappings:
    #                 target_uri = id_mappings[ref_id]
    #                 g.add((source_uri, D3F.references, target_uri))
        
    #     # Handle marking definitions
    #     if "object_marking_refs" in obj:
    #         for marking_ref in obj["object_marking_refs"]:
    #             # Create a marking node if it doesn't exist in our mappings
    #             if marking_ref not in id_mappings:
    #                 marking_uri = ABI[marking_ref]
    #                 id_mappings[marking_ref] = marking_uri
    #                 g.add((marking_uri, RDF.type, D3F.MarkingDefinition))
    #             else:
    #                 marking_uri = id_mappings[marking_ref]
                
    #             g.add((source_uri, D3F.has_marking, marking_uri))
    
    # Add custom relationships based on STIX content
    # Here we could add more specific D3FEND relationships based on STIX patterns or other content
    
    # Serialize the graph to Turtle format
    g.serialize(destination=output_ttl_path, format="turtle")
    
    return g

def main():
    # Set paths
    stix_json_path = "src/custom/modules/cyber_threat_intelligence/pipelines/tests/5869.pretty.stix2.json"
    output_ttl_path = "src/custom/modules/cyber_threat_intelligence/pipelines/tests/stix_to_d3fend.ttl"
    
    # Map STIX to D3FEND
    map_stix_to_d3fend(stix_json_path, output_ttl_path)
    print(f"Mapping complete. Output written to {output_ttl_path}")

if __name__ == "__main__":
    main() 