from naas_abi_marketplace.domains.document import ABIModule
from naas_abi_marketplace.domains.document.ontologies.modules.DocumentOntology import File

def file_already_ingested(sha256: str, graph_name: str) -> bool:
    query = f"""
    PREFIX doc: <http://ontology.naas.ai/abi/document/>
    SELECT ?file WHERE {{
        GRAPH <{str(graph_name)}> {{
            ?file doc:sha256 "{sha256}" .
        }}
    }}
    """
    module = ABIModule.get_instance()
    
    results = module.engine.services.triple_store.query(query)
    return len(list(results)) > 0

def get_files_to_process(graph_name: str, mime_type: str, processor_iri: str) -> list[str]:
    module = ABIModule.get_instance()
    query = f"""
    PREFIX doc: <http://ontology.naas.ai/abi/document/>
    SELECT ?fileIRI WHERE {{
        GRAPH <{str(graph_name)}> {{
            ?fileIRI doc:mime_type "{mime_type}" .
            FILTER NOT EXISTS {{ ?fileIRI doc:processedBy <{processor_iri}> }}
        }}
    }}
    """
    results = module.engine.services.triple_store.query(query)
    return [str(result["fileIRI"]) for result in results]
