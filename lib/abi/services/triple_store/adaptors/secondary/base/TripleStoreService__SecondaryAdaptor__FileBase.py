import hashlib
from rdflib import Graph
from typing import Dict, List, Tuple, Any


class TripleStoreService__SecondaryAdaptor__FileBase:
    def iri_hash(self, iri: str) -> str:
        return hashlib.sha256(iri.encode("utf-8")).hexdigest()

    def triples_by_subject(self, triples: Graph) -> Dict[Any, List[Tuple[Any, Any]]]:
        triples_by_subject: Dict[Any, List[Tuple[Any, Any]]] = {}

        for s, p, o in triples.triples((None, None, None)):
            if s not in triples_by_subject:
                triples_by_subject[s] = []
            triples_by_subject[s].append((p, o))

        return triples_by_subject
