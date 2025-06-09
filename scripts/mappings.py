# Add standard RDF terms
rdf_terms = {
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": "type",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#first": "first",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#rest": "rest",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#nil": "nil",
}

# Add RDFS terms
rdfs_terms = {
    "http://www.w3.org/2000/01/rdf-schema#domain": "domain",
    "http://www.w3.org/2000/01/rdf-schema#label": "label",
    "http://www.w3.org/2000/01/rdf-schema#range": "range",
    "http://www.w3.org/2000/01/rdf-schema#subClassOf": "subclassOf",
}

# Add OWL terms
owl_terms = {
    "http://www.w3.org/2002/07/owl#complementOf": "complementOf",
    "http://www.w3.org/2002/07/owl#intersectionOf": "intersectionOf",
    "http://www.w3.org/2002/07/owl#inverseOf": "inverseOf",
    "http://www.w3.org/2002/07/owl#unionOf": "unionOf",
}

# Add SKOS terms
skos_terms = {
    "http://www.w3.org/2004/02/skos/core#altLabel": "altLabel",
    "http://www.w3.org/2004/02/skos/core#definition": "definition",
    "http://www.w3.org/2004/02/skos/core#example": "example",
}

# Add DC terms
dc_terms = {
    "http://purl.org/dc/elements/1.1/identifier": "identifier",
    "http://purl.org/dc/terms/title": "title",
    "http://purl.org/dc/terms/description": "description",
    "http://purl.org/dc/terms/license": "license",
    "http://purl.org/dc/terms/rights": "rights",
    "http://purl.org/dc/terms/contributor": "contributor",
}
