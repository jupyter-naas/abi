from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[TripleStoreService, VectorStoreService],
    )

    class Configuration(ModuleConfiguration):
        pass

    def on_load(self):
        super().on_load()
        from langchain_openai import OpenAIEmbeddings
        from naas_abi_core.modules.triplestore_embeddings.workflows.CreateTripleEmbeddingsWorkflow import (
            CreateTripleEmbeddingsWorkflow,
            CreateTripleEmbeddingsWorkflowConfiguration,
            CreateTripleEmbeddingsWorkflowParameters,
        )
        from naas_abi_core.modules.triplestore_embeddings.workflows.DeleteTripleEmbeddingsWorkflow import (
            DeleteTripleEmbeddingsWorkflow,
            DeleteTripleEmbeddingsWorkflowConfiguration,
            DeleteTripleEmbeddingsWorkflowParameters,
        )
        from naas_abi_core.services.triple_store.TripleStorePorts import OntologyEvent
        from rdflib import RDFS

        # Init configuration
        collection_name = "triple_embeddings_test"
        embeddings_dimension = 3072
        embeddings_model = OpenAIEmbeddings(
            model="text-embedding-3-large",
            dimensions=embeddings_dimension,
        )

        # Init create triple embeddings workflow
        create_triple_embeddings_configuration = (
            CreateTripleEmbeddingsWorkflowConfiguration(
                vector_store=self.engine.services.vector_store,
                triple_store=self.engine.services.triple_store,
                embeddings_model=embeddings_model,
                embeddings_dimension=embeddings_dimension,
                collection_name=collection_name,
            )
        )
        create_triple_embeddings_workflow = CreateTripleEmbeddingsWorkflow(
            create_triple_embeddings_configuration
        )

        self.engine.services.triple_store.subscribe(
            (None, RDFS.label, None),
            lambda triple: create_triple_embeddings_workflow.create_triple_embeddings(
                CreateTripleEmbeddingsWorkflowParameters(
                    s=str(triple[0]), p=str(triple[1]), o=str(triple[2])
                )
            ),
            OntologyEvent.INSERT,
        )

        # Init delete triple embeddings workflow
        delete_triple_embeddings_configuration = (
            DeleteTripleEmbeddingsWorkflowConfiguration(
                vector_store=self.engine.services.vector_store,
                embeddings_model=embeddings_model,
                embeddings_dimension=embeddings_dimension,
                collection_name=collection_name,
            )
        )
        delete_triple_embeddings_workflow = DeleteTripleEmbeddingsWorkflow(
            delete_triple_embeddings_configuration
        )

        self.engine.services.triple_store.subscribe(
            (None, RDFS.label, None),
            lambda triple: delete_triple_embeddings_workflow.delete_triple_embeddings(
                DeleteTripleEmbeddingsWorkflowParameters(
                    s=str(triple[0]), p=str(triple[1]), o=str(triple[2])
                )
            ),
            OntologyEvent.DELETE,
        )
