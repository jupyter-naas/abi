from naas_abi_marketplace.domains.document import ABIModule

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