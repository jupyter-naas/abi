import pytest
from langchain_openai import OpenAIEmbeddings
from naas_abi_core.engine.Engine import Engine
from naas_abi_core.modules.triplestore_embeddings import ABIModule
from naas_abi_core.modules.triplestore_embeddings.workflows.CreateSearchToolWorkflow import (
    CreateSearchToolWorkflow,
    CreateSearchToolWorkflowConfiguration,
    CreateSearchToolWorkflowParameters,
)

engine = Engine()
engine.load(module_names=["naas_abi_core.modules.triplestore_embeddings"])

module: ABIModule = ABIModule.get_instance()


@pytest.fixture
def workflow() -> CreateSearchToolWorkflow:
    configuration = CreateSearchToolWorkflowConfiguration(
        vector_store=module.engine.services.vector_store,
        embeddings_model=OpenAIEmbeddings(
            model="text-embedding-3-large",
        ),
    )
    workflow = CreateSearchToolWorkflow(configuration)
    return workflow


def test_create_search_tool(workflow):
    from langchain_core.tools import StructuredTool
    from langchain_openai import ChatOpenAI
    from naas_abi_core.services.agent.Agent import (
        Agent,
        AgentConfiguration,
    )

    result = workflow.create_search_tool(
        CreateSearchToolWorkflowParameters(
            collection_name="triple_embeddings_test",
            search_param_name="person_name",
            tool_name="search_person",
            tool_description="Search for a person by name",
            entity_type_label="person",
            filter={"type_label": "Person"},
        )
    )

    assert result is not None, result
    assert result.name == "search_person", result.name
    assert isinstance(result, StructuredTool), result

    agent = Agent(
        name="Embeddings Workflow",
        description="Embeddings Workflow",
        chat_model=ChatOpenAI(model="gpt-4.1"),
        tools=[result],
        configuration=AgentConfiguration(),
    )

    response = agent.invoke("list tools")
    assert response is not None, response
    assert "search_person" in response, response
