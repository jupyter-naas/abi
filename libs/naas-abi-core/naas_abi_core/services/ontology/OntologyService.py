from naas_abi_core.services.ontology.OntologyPorts import (
    IOntologyNERPort,
    IOntologyService,
)
from rdflib import Graph


class OntologyService(IOntologyService):
    __ontology_str: str
    __ner_adaptor: IOntologyNERPort

    def __init__(self, ner_adaptor: IOntologyNERPort, ontology_str: str):
        self.__ner_adaptor = ner_adaptor
        self.__ontology_str = ontology_str

    def named_entity_recognition(self, input: str) -> Graph:
        return self.__ner_adaptor.named_entity_recognition(input, self.__ontology_str)
