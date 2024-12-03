from rdflib import Graph, Namespace, Literal, URIRef
from typing import Dict

def send_profile_to_ontology(profile_data: Dict, output_path: str) -> None:
    """
    Convert LinkedIn profile data to TTL format and save to ontology
    
    Args:
        profile_data: Dictionary containing LinkedIn profile information
        output_path: Path to save the TTL file
    """
    # Initialize RDF graph
    g = Graph()
    
    # Define namespaces
    LINKEDIN = Namespace("http://example.org/linkedin/")
    FOAF = Namespace("http://xmlns.com/foaf/0.1/")
    
    # Bind namespaces
    g.bind("linkedin", LINKEDIN)
    g.bind("foaf", FOAF)
    
    # Create URI for the person
    person_uri = URIRef(LINKEDIN[profile_data.get('id', 'profile')])
    
    # Add basic profile information
    g.add((person_uri, FOAF.name, Literal(profile_data.get('name', ''))))
    g.add((person_uri, LINKEDIN.headline, Literal(profile_data.get('headline', ''))))
    g.add((person_uri, LINKEDIN.location, Literal(profile_data.get('location', ''))))
    
    # Add experience
    for exp in profile_data.get('experience', []):
        exp_uri = URIRef(LINKEDIN[f"experience_{exp.get('id', '')}"]) 
        g.add((person_uri, LINKEDIN.hasExperience, exp_uri))
        g.add((exp_uri, LINKEDIN.title, Literal(exp.get('title', ''))))
        g.add((exp_uri, LINKEDIN.company, Literal(exp.get('company', ''))))
        
    # Add education
    for edu in profile_data.get('education', []):
        edu_uri = URIRef(LINKEDIN[f"education_{edu.get('id', '')}"])
        g.add((person_uri, LINKEDIN.hasEducation, edu_uri))
        g.add((edu_uri, LINKEDIN.school, Literal(edu.get('school', ''))))
        g.add((edu_uri, LINKEDIN.degree, Literal(edu.get('degree', ''))))
    
    # Serialize and save to TTL file
    g.serialize(destination=output_path, format='turtle')