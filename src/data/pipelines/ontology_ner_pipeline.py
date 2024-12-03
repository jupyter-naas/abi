from dataclasses import dataclass
from abi.pipeline import Pipeline, PipelineConfiguration
from rdflib import Graph
from abi.services.ontology_processor.OntologyService import OntologyService
from abi.services.ontology_processor.adaptors.secondary.OntologyService_SecondaryAdaptor_NERPort import OntologyService_SecondaryAdaptor_NERPort
@dataclass
class OntologyNERPipelineConfiguration(PipelineConfiguration):
    """Configuration for Ontology NER pipeline.
    
    Attributes:
        input_text (str): Text to perform Named Entity Recognition on
    """
    input_text: str

class OntologyNERPipeline(Pipeline):
    __ontology_service: OntologyService
    __configuration: OntologyNERPipelineConfiguration
    
    def __init__(self, ontology_service: OntologyService, configuration: OntologyNERPipelineConfiguration):
        super().__init__([], configuration)
        
        self.__ontology_service = ontology_service
        self.__configuration = configuration

    def run(self) -> Graph:
        return self.__ontology_service.named_entity_recognition(self.__configuration.input_text)

# def as_tools(ontology_service: OntologyService):
#     from langchain_core.tools import StructuredTool
#     from pydantic import BaseModel, Field
    
#     class OntologyNERSchema(BaseModel):
#         input_text: str = Field(..., description="Text to perform Named Entity Recognition on")
    
#     def perform_ontology_ner(input_text: str) -> Graph:
#         configuration = OntologyNERPipelineConfiguration(input_text=input_text)
#         pipeline = OntologyNERPipeline(ontology_service, configuration)
#         return pipeline.run()
    
#     return [
#         StructuredTool(
#             name="perform_ontology_ner",
#             description="Perform Named Entity Recognition using an ontology to extract structured information from text",
#             func=perform_ontology_ner,
#             args_schema=OntologyNERSchema
#         )
#     ]

def main():
    from langchain_openai import ChatOpenAI
    from src import secret
    
    chat_model = ChatOpenAI(model="gpt-4o-mini", temperature=0, api_key=secret.get("OPENAI_API_KEY"))
    with open("src/ontologies/domain-level/task.ttl", "r") as f:
        ontology_str = f.read()
    
    ontology_ner_adaptor = OntologyService_SecondaryAdaptor_NERPort(chat_model)
    ontology_service = OntologyService(ontology_ner_adaptor, ontology_str)
    
    configuration = OntologyNERPipelineConfiguration(input_text="""
Task 17 was created on January 25, 2024 for the W04-2024 scenario. The task "Review project progress" is due on January 27, 2024 and was sourced from Google Meet. It's assigned to Abi and is related to the Operations project for Naas organization. The task has an estimated duration of 3.00 hours with an actual time of 3.95 hours, resulting in a variance of -0.95 hours. This task is linked to conversation 11AUpFyUKOiBw1JhTZFl11Swl3q1g0Uny.

Another task (ID: 14) was also created on January 25, 2024 for W04-2024. This task titled "Brainstorm new ideas" is due on January 30, 2024 and originated from Google Meet. Abi is responsible for this task which is part of the Content project at Naas. The estimated time was 3.00 hours, but it actually took 3.95 hours, with a -0.95 hour variance. This task is associated with conversation 11AUpFyUKOiBw1JhTZFl11Swl3q1g0Uny.
""")
    
    pipeline = OntologyNERPipeline(ontology_service, configuration)
    graph = pipeline.run()
    print(graph.serialize(format="turtle"))

if __name__ == "__main__":
    main()