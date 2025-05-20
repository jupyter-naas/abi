from rdflib import Graph, RDF, RDFS, URIRef, Literal
import rdflib
import re
import uuid
from typing import List, Dict, Tuple


class OntologyReasoner:
    def is_iri_uuid(self, iri: URIRef) -> bool:
        # Split by / and get last element then split by # and get last element
        last_element = iri.split("/")[-1].split("#")[-1]

        # Check if last element is a UUID
        return (
            re.match(
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                last_element,
            )
            is not None
        )

    def dedup_subject(self, class_label: tuple, graph: Graph) -> Graph:
        cls, label = class_label
        # Search all IRI in graph using SPARQL where p = rdf:type and o = cls and p = rdfs:label and o = label
        query = """
        SELECT ?s WHERE {
            ?s a <%s> .
            ?s rdfs:label "%s" .
            FILTER NOT EXISTS { ?other rdfs:subClassOf ?s }
            FILTER NOT EXISTS { ?s a owl:Class }
            FILTER NOT EXISTS { ?s a rdfs:Class }
        }
        """ % (cls, label)
        # print(query)
        results: rdflib.query.Result = graph.query(query)

        new_graph = Graph()

        def filter_func(x: rdflib.query.ResultRow) -> bool:
            return (
                self.is_iri_uuid(x[0])
                if isinstance(x, rdflib.query.ResultRow) and isinstance(x[0], URIRef)
                else False
            )

        main_node: List[rdflib.query.ResultRow] = list(
            filter(
                filter_func,
                [
                    result
                    for result in results
                    if isinstance(result, rdflib.query.ResultRow)
                ],
            )
        )

        main_node_uri: str = ""
        if len(main_node) == 0:
            # Create new IRI UUID
            main_node_uri = f"http://ontology.naas.ai/abi/{uuid.uuid4()}"

            # Add new node to graph
            new_graph.add((URIRef(main_node_uri), RDF.type, URIRef(cls)))
            new_graph.add((URIRef(main_node_uri), RDFS.label, Literal(label)))
        else:
            main_node_uri = str(main_node[0][0])

        excluded_iris = []

        def not_filter_func(x: rdflib.query.ResultRow) -> bool:
            return not filter_func(x)

        # For each result, we need to get all triples and add them to the new node then remove existing triples
        for result in list(
            filter(
                not_filter_func,
                [
                    result
                    for result in results
                    if isinstance(result, rdflib.query.ResultRow)
                ],
            )
        ):
            existing_iri = result[0]
            excluded_iris.append(existing_iri)
            for s, p, o in graph:
                # Add existing triples to the new node.
                if s == existing_iri and p != RDF.type:
                    new_graph.add((URIRef(main_node_uri), p, o))

                # Update existing references to the new node.
                elif o == existing_iri:
                    new_graph.add((s, p, URIRef(main_node_uri)))

        for s, p, o in graph:
            if s not in excluded_iris and o not in excluded_iris:
                new_graph.add((s, p, o))

        return new_graph

    def dedup_ttl(self, ttl: str) -> Tuple[str, Graph]:
        graph = Graph()
        graph.parse(data=ttl, format="turtle")

        types: Dict[URIRef, URIRef] = {}
        labels: Dict[URIRef, str] = {}
        types_label: Dict[Tuple[URIRef, str], List[URIRef]] = {}

        pn = graph.namespaces()

        # Look for triples that have same label and same type
        for s, p, o in graph:
            assert (
                isinstance(s, URIRef)
                and isinstance(p, URIRef)
                and isinstance(o, URIRef)
            )

            if p == RDF.type:
                types[s] = o
            if p == RDFS.label:
                labels[s] = str(o)

        for st in types:
            t = types[st]
            if st in labels:
                key = (t, labels[st])
                if key not in types_label:
                    types_label[key] = []
                types_label[key].append(st)

        for key in types_label:
            if len(types_label[key]) > 1:
                graph = self.dedup_subject(key, graph)

        for prefix, namespace in pn:
            graph.bind(prefix, namespace)

        return graph.serialize(
            format="turtle", namespace_manager=graph.namespace_manager
        ), graph
