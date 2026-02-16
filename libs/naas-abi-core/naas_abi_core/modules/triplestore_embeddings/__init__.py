from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=["naas_abi_marketplace.ai.chatgpt#soft"],
        services=[TripleStoreService, VectorStoreService, ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """Configuration for TriplestoreEmbeddings module.

        Configuration example:

        module: naas_abi_core.modules.triplestore_embeddings
        enabled: true
        config:
            datastore_path: "triples"
            collection_name: "triple_embeddings"
            embeddings_dimensions: 3072
            embeddings_model_name: "text-embedding-3-large"
            embeddings_model_provider: "openai"

        """

        datastore_path: str = "triples"
        collection_name: str = "triple_embeddings"
        embeddings_dimensions: int = 3072
        embeddings_model_name: str = "text-embedding-3-large"
        embeddings_model_provider: str = "openai"

    def on_load(self):
        super().on_load()

        from langchain_openai import OpenAIEmbeddings
        from naas_abi_core.modules.triplestore_embeddings.pipelines.MergeIndividualsPipeline import (
            MergeIndividualsPipelineConfiguration,
        )
        from naas_abi_core.modules.triplestore_embeddings.workflows.CreateTripleEmbeddingsWorkflow import (
            CreateTripleEmbeddingsWorkflowConfiguration,
        )
        from naas_abi_core.modules.triplestore_embeddings.workflows.DeleteTripleEmbeddingsWorkflow import (
            DeleteTripleEmbeddingsWorkflow,
            DeleteTripleEmbeddingsWorkflowConfiguration,
            DeleteTripleEmbeddingsWorkflowParameters,
        )
        from naas_abi_core.modules.triplestore_embeddings.workflows.EntityResolutionWorkflow import (
            EntityResolutionWorkflow,
            EntityResolutionWorkflowConfiguration,
            EntityResolutionWorkflowParameters,
        )
        from naas_abi_core.services.triple_store.TripleStorePorts import OntologyEvent
        from rdflib import RDFS

        # Init configurations
        collection_name = self.configuration.collection_name
        embeddings_dimensions = self.configuration.embeddings_dimensions
        if self.configuration.embeddings_model_provider == "openai":
            embeddings_model = OpenAIEmbeddings(
                model=self.configuration.embeddings_model_name,
                dimensions=embeddings_dimensions,
            )
        else:
            raise ValueError(
                f"Embeddings model provider {self.configuration.embeddings_model_provider} not supported"
            )

        # Init create triple embeddings workflow
        create_triple_embeddings_configuration = (
            CreateTripleEmbeddingsWorkflowConfiguration(
                vector_store=self.engine.services.vector_store,
                triple_store=self.engine.services.triple_store,
                embeddings_model=embeddings_model,
                embeddings_dimension=embeddings_dimensions,
                collection_name=collection_name,
            )
        )
        merge_individuals_pipeline_configuration = (
            MergeIndividualsPipelineConfiguration(
                triple_store=self.engine.services.triple_store,
                object_storage=self.engine.services.object_storage,
                datastore_path=self.configuration.datastore_path,
            )
        )

        entity_resolution_workflow_configuration = EntityResolutionWorkflowConfiguration(
            merge_pipeline_configuration=merge_individuals_pipeline_configuration,
            create_embeddings_workflow_configuration=create_triple_embeddings_configuration,
            vector_store=self.engine.services.vector_store,
            triple_store=self.engine.services.triple_store,
            embeddings_model=embeddings_model,
            embeddings_dimension=embeddings_dimensions,
            collection_name=collection_name,
        )
        entity_resolution_workflow = EntityResolutionWorkflow(
            entity_resolution_workflow_configuration
        )

        self.engine.services.triple_store.subscribe(
            (None, RDFS.label, None),
            lambda triple: entity_resolution_workflow.resolve_entity(
                EntityResolutionWorkflowParameters(
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
                embeddings_dimension=embeddings_dimensions,
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
