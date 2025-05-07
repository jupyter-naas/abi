from dataclasses import dataclass
from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from abi.services.ontology.OntologyPorts import IOntologyService
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from rdflib import Graph
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from pydantic import BaseModel, Field


@dataclass
class OntologyNERPipelineConfiguration(PipelineConfiguration):
    """Configuration for Ontology NER pipeline.

    Attributes:
        ontology_service (IOntologyService): Service for performing ontology operations
        triple_store (ITripleStoreService): Store for persisting ontology data
    """

    ontology_service: IOntologyService
    triple_store: ITripleStoreService
    triple_store_name: str


class OntologyNERPipelineParameters(PipelineParameters):
    """Parameters for OntologyNERPipeline execution.

    Attributes:
        input_text (str): Text to perform Named Entity Recognition on
    """

    input_text: str


class OntologyNERPipeline(Pipeline):
    __configuration: OntologyNERPipelineConfiguration

    def __init__(self, configuration: OntologyNERPipelineConfiguration):
        self.__configuration = configuration

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline.

        Returns:
            list[StructuredTool]: List containing the pipeline tool
        """
        return [
            StructuredTool(
                name="perform_ontology_ner",
                description="Perform Named Entity Recognition using an ontology to extract structured information from text",
                func=self.run,
                args_schema=OntologyNERPipelineParameters,
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this pipeline to the given router.

        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """

        @router.post("/OntologyNERPipeline")
        def run(parameters: OntologyNERPipelineParameters):
            return self.run(parameters).serialize(format="turtle")

    def run(self, parameters: OntologyNERPipelineParameters) -> Graph:
        graph = Graph()

        graph += self.__configuration.ontology_service.named_entity_recognition(
            parameters.input_text
        )

        self.__configuration.triple_store.insert(
            self.__configuration.triple_store_name, graph
        )
        return graph


def main():
    from langchain_openai import ChatOpenAI
    from src import secret

    chat_model = ChatOpenAI(
        model="gpt-4o-mini", temperature=0, api_key=secret.get("OPENAI_API_KEY")
    )
    with open("src/ontologies/domain-level/task.ttl", "r") as f:
        ontology_str = f.read()

    configuration = OntologyNERPipelineConfiguration(
        input_text="""
Task 17 was created on January 25, 2024 for the W04-2024 scenario. The task "Review project progress" is due on January 27, 2024 and was sourced from Google Meet. It's assigned to Abi and is related to the Operations project for Naas organization. The task has an estimated duration of 3.00 hours with an actual time of 3.95 hours, resulting in a variance of -0.95 hours. This task is linked to conversation 11AUpFyUKOiBw1JhTZFl11Swl3q1g0Uny.

Another task (ID: 14) was also created on January 25, 2024 for W04-2024. This task titled "Brainstorm new ideas" is due on January 30, 2024 and originated from Google Meet. Abi is responsible for this task which is part of the Content project at Naas. The estimated time was 3.00 hours, but it actually took 3.95 hours, with a -0.95 hour variance. This task is associated with conversation 11AUpFyUKOiBw1JhTZFl11Swl3q1g0Uny.
""",
        ontology_str=ontology_str,
    )

    pipeline = OntologyNERPipeline(configuration)
    graph = pipeline.run()
    print(graph.serialize(format="turtle"))


if __name__ == "__main__":
    main()
