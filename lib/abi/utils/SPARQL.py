from src import services
from abi import logger
from rdflib import URIRef, query
from typing import Union


# Transform SPARQL results to list of dictionaries using the labels as keys
def results_to_list(results: query.Result) -> list[dict]:
    data = []
    for row in results:
        assert isinstance(row, query.ResultRow)
        logger.debug(f"==> Row: {row}")
        data_dict = {}
        for key in row.labels:
            data_dict[key] = str(row[key]) if row[key] else None
        data.append(data_dict)
    return data


# Get the class URI for a given URI from the triple store
def get_class_uri_from_individual_uri(uri: str) -> Union[str, None]:
    """
    Get the class URI for a given URI from the triple store.

    Args:
        uri (str): The URI to look up

    Returns:
        str: The class URI if found, None otherwise
    """
    if not str(uri).startswith("http://ontology.naas.ai/abi/"):
        return None

    # Init
    g = services.triple_store_service.get_subject_graph(uri)

    # Get all objects for the subject and predicate
    subj = URIRef(uri)
    pred = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")

    # Get all objects for the subject and predicate
    objects = list(g.objects(subject=subj, predicate=pred))
    for obj in objects:
        if str(obj) != "http://www.w3.org/2002/07/owl#NamedIndividual":
            return str(obj)

    return None
