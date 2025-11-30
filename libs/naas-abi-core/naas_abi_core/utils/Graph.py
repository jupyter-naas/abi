from datetime import date, datetime
from urllib.parse import quote

import pytz
from rdflib import Graph as rdfgraph
from rdflib import Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from naas_abi_core import logger

BFO = Namespace("http://purl.obolibrary.org/obo/")
ABI = Namespace("http://ontology.naas.ai/abi/")
TEST = Namespace("http://ontology.naas.ai/test/")
TIME = Namespace("http://www.w3.org/2006/time#")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")
CCO = Namespace("https://www.commoncoreontologies.org/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
URI_REGEX = r"http:\/\/ontology\.naas\.ai\/.+\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


class ABIGraph(rdfgraph):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.bind("bfo", BFO)
        self.bind("skos", SKOS)
        self.bind("abi", ABI)
        self.bind("cco", CCO)
        self.bind("xsd", XSD)
        self.bind("time", TIME)

    def add_data_properties(self, uri: URIRef, lang="en", **data_properties):
        for x in data_properties:
            value = data_properties.get(x)
            if value is not None:
                if type(value) is str:
                    self.add((uri, ABI[x], Literal(value.strip(), lang=lang)))
                elif type(value) in [int, float]:
                    self.add((uri, ABI[x], Literal(value, datatype=XSD.integer)))
                elif isinstance(value, datetime):
                    if value.tzinfo is None:
                        value = value.replace(
                            tzinfo=pytz.utc
                        )  # Apply UTC timezone if none
                    self.add(
                        (
                            uri,
                            ABI[x],
                            Literal(
                                value.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                datatype=XSD.dateTime,
                            ),
                        )
                    )
                elif isinstance(value, date):
                    self.add(
                        (
                            uri,
                            ABI[x],
                            Literal(value.strftime("%Y-%m-%d"), datatype=XSD.date),
                        )
                    )
        self.add(
            (
                uri,
                DCTERMS.modified,
                Literal(
                    str(datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")),
                    datatype=XSD.dateTime,
                ),
            )
        )

    # Add OWL NamedIndividual to Graph
    def add_individual(
        self,
        uri: URIRef,
        label,
        is_a,
        lang="en",
        skip_if_exists=True,
        **data_properties,
    ) -> URIRef:
        if (uri, RDF.type, is_a) in self and skip_if_exists:
            logger.debug(f"🟡 '{label}' ({str(uri)}) already exists in ontology.")
        else:
            # Add NamedIndividual to ontology
            self.add((uri, RDF.type, OWL.NamedIndividual))
            self.add((uri, RDF.type, URIRef(is_a)))
            self.add((uri, RDFS.label, Literal(str(label), lang=lang)))
            self.add(
                (
                    uri,
                    DCTERMS.created,
                    Literal(
                        str(datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")),
                        datatype=XSD.dateTime,
                    ),
                )
            )
            logger.debug(f"🟢 '{label}' ({str(uri)}) successfully added to ontology.")

        # Add data properties to NamedIndividual
        self.add_data_properties(uri, lang, **data_properties)
        return uri

    def add_individual_to_prefix(
        self,
        prefix: Namespace,
        uid: str,
        label: str,
        is_a: URIRef,
        lang="en",
        skip_if_exists=True,
        **data_properties,
    ) -> URIRef:
        uid = str(uid).split(":")[-1]
        type_name = str(is_a).split("/")[-1]
        uri = URIRef(quote(f"{str(prefix)}{type_name}#{uid}", safe=":/#"))
        return self.add_individual(
            uri, label, is_a, lang, skip_if_exists, **data_properties
        )

    def add_process(
        self,
        prefix: Namespace,
        uid: str,
        label: str,
        is_a: URIRef,
        lang="en",
        participants=[],
        participants_oprop=BFO.BFO_0000057,
        participants_oprop_inverse=BFO.BFO_0000056,
        realizes=[],
        realizes_oprop=BFO.BFO_0000055,
        realizes_oprop_inverse=BFO.BFO_0000054,
        occurs_in=[],
        occurs_in_oprop=BFO.BFO_0000066,
        occurs_in_oprop_inverse=BFO.BFO_0000183,
        concretizes=[],
        concretizes_oprop=BFO.BFO_0000058,
        concretizes_oprop_inverse=BFO.BFO_0000059,
        temporal_region=None,
        temporal_region_oprop=BFO.BFO_0000199,
        spatiotemporal_region=None,
        spatiotemporal_region_oprop=BFO.BFO_0000200,
        skip_if_exists=True,
        **data_properties,
    ):
        # Init
        uri = self.add_individual_to_prefix(
            prefix, uid, label, is_a, lang, skip_if_exists, **data_properties
        )

        # Add participants
        for participant in participants:
            self.add((uri, participants_oprop, participant))
            self.add((participant, participants_oprop_inverse, uri))

        # Add realizable entities
        for realize in realizes:
            self.add((uri, realizes_oprop, realize))
            self.add((realize, realizes_oprop_inverse, uri))

        # Add occurs_in
        for oi in occurs_in:
            self.add((uri, occurs_in_oprop, oi))
            self.add((oi, occurs_in_oprop_inverse, uri))

        # Add concretizes
        for concretize in concretizes:
            self.add((uri, concretizes_oprop, concretize))
            self.add((concretize, concretizes_oprop_inverse, uri))

        # Add occupies_temporal_region
        if temporal_region:
            self.add((uri, temporal_region_oprop, temporal_region))

        # Add occupies_spatiotemporal_region
        if spatiotemporal_region:
            self.add((uri, spatiotemporal_region_oprop, spatiotemporal_region))
        return uri
