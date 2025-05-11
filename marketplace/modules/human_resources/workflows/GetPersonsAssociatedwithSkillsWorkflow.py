from abi.workflow import Workflow, WorkflowConfiguration
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from dataclasses import dataclass
from pydantic import Field
from abi.workflow.workflow import WorkflowParameters
from fastapi import APIRouter
from langchain_core.tools import StructuredTool
from abi.utils.SPARQL import results_to_list


@dataclass
class GetPersonsAssociatedwithSkillsConfigurationWorkflow(WorkflowConfiguration):
    """Configuration for GetPersonsAssociatedwithSkills workflow.

    Attributes:
        triple_store (ITripleStoreService): Ontology store service
    """

    triple_store: ITripleStoreService


class GetPersonsAssociatedwithSkillsWorkflowParameters(WorkflowParameters):
    """Parameters for GetPersonsAssociatedwithSkills workflow.

    Attributes:
        skill_label (str): Skill label
    """

    skill_label: str = Field(
        ..., description="Label of the skill to search persons having it"
    )


class GetPersonsAssociatedwithSkillsWorkflow(Workflow):
    """Workflow for getting person skills from the ontology."""

    __configuration: GetPersonsAssociatedwithSkillsConfigurationWorkflow

    def __init__(
        self, configuration: GetPersonsAssociatedwithSkillsConfigurationWorkflow
    ):
        super().__init__(configuration)
        self.__configuration = configuration

    def get_persons_associated_with_skills(
        self, parameters: GetPersonsAssociatedwithSkillsWorkflowParameters
    ) -> dict:
        query = f"""
        PREFIX abi: <http://ontology.naas.ai/abi/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX cco: <https://www.commoncoreontologies.org/>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>

        SELECT DISTINCT ?person_label
        WHERE {{
            ?skill a owl:NamedIndividual ;
                    rdfs:label "{parameters.skill_label}" ;
                    abi:isSkillOf ?person .
            ?person rdfs:label ?person_label .
        }}
        """
        results = self.__configuration.triple_store.query(query)
        return results_to_list(results)

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.

        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [
            StructuredTool(
                name="get_persons_associated_with_skills",
                description="Get persons associated with a skill from the ontology.",
                func=lambda skill_label: self.get_persons_associated_with_skills(
                    GetPersonsAssociatedwithSkillsWorkflowParameters(
                        skill_label=skill_label
                    )
                ),
                args_schema=GetPersonsAssociatedwithSkillsWorkflowParameters,
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass
