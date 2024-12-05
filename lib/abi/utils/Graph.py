from rdflib import Namespace, URIRef, Literal, Graph as rdfgraph
from rdflib.namespace import RDF, RDFS, OWL, DC, XSD, SKOS
from urllib.parse import quote
from typing import Union
from typing import overload
from datetime import datetime
import pytz
from abi import logger

BFO = Namespace("http://purl.obolibrary.org/obo/")
ABI = Namespace("http://ontology.naas.ai/abi/")
TIME = Namespace("http://www.w3.org/2006/time#")
XSD = Namespace("http://www.w3.org/2001/XMLSchema#")
CCO = Namespace("https://www.commoncoreontologies.org/")

class ABIGraph(rdfgraph):
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.bind("bfo", BFO)
        self.bind("skos", SKOS)
        self.bind("abi", ABI)
        self.bind("cco", CCO)
    
    # Add OWL NamedIndividual to Graph
    def add_individual(
        self,
        uri : URIRef,
        label,
        is_a,
        lang="en",
        skip_if_exists=True,
        **data_properties
    ) -> URIRef:
        if (uri, RDF.type, is_a) in self and skip_if_exists:
            return uri

        # Add NamedIndividual to ontology
        self.add((uri, RDF.type, OWL.NamedIndividual))
        self.add((uri, RDF.type, URIRef(is_a)))
        self.add((uri, RDFS.label, Literal(str(label), lang=lang)))
        for x in data_properties:
            value = data_properties.get(x)
            if value is not None:
                if type(value) is str:
                    self.add((uri, ABI[x], Literal(value.strip(), lang=lang)))
                elif type(value) in [int, float]:
                    self.add((uri, ABI[x], Literal(value, datatype=XSD.integer)))
                elif isinstance(value, datetime):
                    if value.tzinfo is None:
                        value = value.replace(tzinfo=pytz.utc)  # Apply UTC timezone if none
                    self.add((uri, ABI[x], Literal(value.strftime("%Y-%m-%dT%H:%M:%S%z"), datatype=XSD.dateTime)))

        logger.debug(f"✅ '{label}' successfully added to ontology ({str(uri)})")
        return uri
    
    def add_individual_to_prefix(
        self,
        prefix: Namespace,
        uid: str,
        label: str,
        is_a: URIRef,
        lang="en",
        skip_if_exists=True,
        **data_properties
    ) -> URIRef:
        uid = str(uid).split(":")[-1]
        type_name = str(is_a).split("/")[-1]
        uri = URIRef(quote(f"{str(prefix)}{type_name}#{uid}", safe=":/#"))
        return self.add_individual(uri, label, is_a, lang, skip_if_exists, **data_properties)