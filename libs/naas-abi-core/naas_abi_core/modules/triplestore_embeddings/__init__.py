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

        import os

        from langchain_openai import OpenAIEmbeddings
        from naas_abi_core.modules.triplestore_embeddings.pipelines.MergeIndividualsPipeline import (
            MergeIndividualsPipelineConfiguration,
        )
        from naas_abi_core.modules.triplestore_embeddings.utils.Triples import (
            TriplesUtils,
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
        from rdflib import RDFS, URIRef

        # Init configurations
        datastore_path = self.configuration.datastore_path
        triple_store_service = self.engine.services.triple_store
        vector_store_service = self.engine.services.vector_store
        object_storage_service = self.engine.services.object_storage
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

        # Create test graph if TEST environment variable is set to true
        graph_name = None
        env = os.getenv("TEST")
        if env == "true":
            graph_name = "http://ontology.naas.ai/abi/test/"
            collection_name = collection_name + "_test"
            datastore_path = self.configuration.datastore_path + "_test"

            current_dir = os.path.dirname(os.path.abspath(__file__))
            ontologies_path = os.path.join(current_dir, "ontologies")

            TriplesUtils(triple_store=triple_store_service).load_schemas(
                graph_name=graph_name, dir_path=ontologies_path
            )

        # Init create triple embeddings workflow
        create_triple_embeddings_configuration = (
            CreateTripleEmbeddingsWorkflowConfiguration(
                vector_store=vector_store_service,
                triple_store=triple_store_service,
                embeddings_model=embeddings_model,
                embeddings_dimensions=embeddings_dimensions,
                collection_name=collection_name,
                graph_name=graph_name,
            )
        )
        merge_individuals_pipeline_configuration = (
            MergeIndividualsPipelineConfiguration(
                triple_store=triple_store_service,
                object_storage=object_storage_service,
                graph_name=URIRef(graph_name),
                datastore_path=datastore_path,
            )
        )

        entity_resolution_workflow_configuration = EntityResolutionWorkflowConfiguration(
            merge_pipeline_configuration=merge_individuals_pipeline_configuration,
            create_embeddings_workflow_configuration=create_triple_embeddings_configuration,
            vector_store=vector_store_service,
            triple_store=triple_store_service,
            embeddings_model=embeddings_model,
            embeddings_dimensions=embeddings_dimensions,
            collection_name=collection_name,
            graph_name=graph_name,
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
            graph_name,
        )

        # Init delete triple embeddings workflow
        delete_triple_embeddings_configuration = (
            DeleteTripleEmbeddingsWorkflowConfiguration(
                vector_store=vector_store_service,
                embeddings_model=embeddings_model,
                embeddings_dimensions=embeddings_dimensions,
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
            graph_name,
        )
