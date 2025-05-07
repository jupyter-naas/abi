from abc import ABC, abstractmethod
from rdflib import Graph
from langchain_core.language_models import BaseChatModel


class IOntologyNERPort(ABC):
    __chat_model: BaseChatModel

    @abstractmethod
    def named_entity_recognition(self, input: str, ontology_str: str) -> Graph:
        """Apply Named Entity Recognition (NER) on input text to map entities to ontology concepts.

        Args:
            input (str): The unstructured text to process with NER
            ontology_str (str): The ontology in Turtle format to map entities against

        Returns:
            Graph: An RDFLib Graph containing the mapped entities and their relationships from the input text
        """
        pass


class IOntologyService(ABC):
    __ner_adaptor: IOntologyNERPort

    @abstractmethod
    def named_entity_recognition(self, input: str) -> Graph:
        """Apply Named Entity Recognition (NER) on input text to map entities to ontology concepts.

        Args:
            input (str): The input text to process with NER

        Returns:
            Graph: An RDFLib Graph containing the mapped entities and their relationships
        """
        pass
