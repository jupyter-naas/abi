from src import services
from rdflib import URIRef
from abi import logger

consolidated = services.triple_store_service.get_schema_graph()
# schema_graph = Graph()

# # Filter for desired types
# desired_types = {
#     OWL.Class,
#     OWL.DatatypeProperty,
#     OWL.ObjectProperty,
#     OWL.AnnotationProperty
# }

# # Add all triples where subject is of desired type
# for s, p, o in consolidated.triples((None, RDF.type, None)):
#     if o in desired_types:
#         # Add the type triple
#         schema_graph.add((s, p, o))
#         # Add all triples where this subject is involved
#         for s2, p2, o2 in consolidated.triples((s, None, None)):
#             schema_graph.add((s2, p2, o2))
#         for s2, p2, o2 in consolidated.triples((None, None, s)):
#             schema_graph.add((s2, p2, o2))

onto_tuples = {}
for s, p, o in consolidated.triples((URIRef('http://purl.obolibrary.org/obo/BFO_0000057'), None, None)):
    logger.info(f"{s} {p} {o}")
    if str(p) == 'http://www.w3.org/2000/01/rdf-schema#range' and not str(o).startswith('http'):
        logger.info(f"🔍 Looking for {o} triples")
        for s2, p2, o2 in consolidated.triples((o, None, None)):
            logger.info(f"{s2} {p2} {o2}")
            if str(p2) in ['http://www.w3.org/2002/07/owl#unionOf', 'http://www.w3.org/2002/07/owl#intersectionOf', 'http://www.w3.org/2002/07/owl#complementOf'] and not str(o2).startswith('http'):
                logger.info(f"🔍 Looking for {o2} triples")
                for s3, p3, o3 in consolidated.triples((o2, None, None)):
                    logger.info(f"{s3} {p3} {o3}")
                logger.info(f"🔍 End of {o2} triples")
        logger.info(f"🔍 End of {o} triples")
