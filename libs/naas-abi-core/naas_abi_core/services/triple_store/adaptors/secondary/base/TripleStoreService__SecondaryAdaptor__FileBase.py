import hashlib

from rdflib import Graph, Node, URIRef


class TripleStoreService__SecondaryAdaptor__FileBase:
    def iri_hash(self, iri: URIRef) -> str:
        return hashlib.sha256(iri.encode("utf-8")).hexdigest()

    def triples_by_subject(self, triples: Graph) -> dict[Node, list[tuple[Node, Node]]]:
        triples_by_subject: dict[Node, list[tuple[Node, Node]]] = {}

        for s, p, o in triples.triples((None, None, None)):
            if s not in triples_by_subject:
                triples_by_subject[s] = []
            triples_by_subject[s].append((p, o))

        return triples_by_subject
