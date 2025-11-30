from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from naas_abi_core.services.ontology.OntologyPorts import IOntologyNERPort
from rdflib import Graph


class OntologyService_SecondaryAdaptor_NERPort(IOntologyNERPort):
    __chat_model: BaseChatModel

    def __init__(self, chat_model: BaseChatModel):
        self.__chat_model = chat_model

    def named_entity_recognition(self, input: str, ontology_str: str) -> Graph:
        messages = [
            SystemMessage(
                content=f"""
You are an expert in Named Entity Recognition (NER).
You are given a string of unstructured text and an ontology in Turtle format.
Your task is to map the entities in the text to the ontology concepts.

Here is the ontology in Turtle format:
{ontology_str}


Only output the Turtle formated file ready to be stored in a file. You must add all prefixes.
"""
            ),
            HumanMessage(content=input),
        ]
        response = self.__chat_model.invoke(messages)
        assert isinstance(response.content, str)
        sanitized_response = response.content.replace("```turtle", "").replace(
            "```", ""
        )
        g = Graph()
        g.parse(data=sanitized_response, format="turtle")
        return g
