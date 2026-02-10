from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService


class _Configuration(ModuleConfiguration):
    """
    Configuration example:

    module: naas_abi_marketplace.applications.linkedin
    enabled: true
    config:
        li_at: "{{ secret.li_at }}"
        JSESSIONID: "{{ secret.JSESSIONID }}"
        linkedin_profile_url: "https://www.linkedin.com/in/your-profile-id/"
    """

    li_at: str
    JSESSIONID: str
    linkedin_profile_url: str
    datastore_path: str = "linkedin"


class ABIModule(BaseModule[_Configuration]):
    Configuration = _Configuration
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            "naas_abi_marketplace.ai.chatgpt",
            "naas_abi_marketplace.applications.google_search",
            "naas_abi_marketplace.applications.naas",
            "naas_abi_core.modules.templatablesparqlquery",
        ],
        services=[ObjectStorageService, TripleStoreService, Secret, VectorStoreService],
    )

    def on_initialized(self):
        super().on_initialized()

        import glob
        import os

        from naas_abi_core import logger
        from naas_abi_core.utils.onto2py import onto2py
        from naas_abi_marketplace.applications.linkedin.workflows.CreateClassEmbeddingsWorkflow import (
            CreateClassEmbeddingsWorkflow,
            CreateClassEmbeddingsWorkflowConfiguration,
            CreateClassEmbeddingsWorkflowParameters,
        )

        ontologies_dir = os.path.join(os.path.dirname(__file__), "ontologies")
        ttl_files = glob.glob(
            os.path.join(ontologies_dir, "modules", "*.ttl"), recursive=True
        )

        if not ttl_files:
            logger.warning(f"No TTL files found in {ontologies_dir}")
            return

        for ttl_file in ttl_files:
            if "Queries.ttl" in ttl_file:
                continue
            try:
                logger.debug(f"Converting {ttl_file} to Python")
                onto2py(ttl_file)
            except Exception as e:
                logger.error(
                    f"Failed to convert {ttl_file} to Python: {e}", exc_info=True
                )

        # Initialize and execute workflow for creating embeddings
        try:
            embeddings_workflow = CreateClassEmbeddingsWorkflow(
                CreateClassEmbeddingsWorkflowConfiguration(
                    triple_store=self.engine.services.triple_store,
                    vector_store=self.engine.services.vector_store,
                )
            )

            # Create embeddings for persons
            logger.info("Creating embeddings for persons...")
            persons_result = embeddings_workflow.create_class_embeddings(
                CreateClassEmbeddingsWorkflowParameters(
                    class_uri="cco:ont00001262",
                    collection_name="linkedin_persons",
                    entity_variable_name="person",
                    entity_type_label="person",
                )
            )
            logger.info(
                f"Persons embeddings created: {persons_result.get('entities_processed', 0)} entities processed"
            )

            # Create embeddings for organizations/companies
            logger.info("Creating embeddings for organizations...")
            organizations_result = embeddings_workflow.create_class_embeddings(
                CreateClassEmbeddingsWorkflowParameters(
                    class_uri="cco:ont00001180",
                    collection_name="linkedin_companies",
                    entity_variable_name="company",
                    entity_type_label="company",
                )
            )
            logger.info(
                f"Organizations embeddings created: {organizations_result.get('entities_processed', 0)} entities processed"
            )
        except Exception as e:
            logger.error(
                f"Failed to create class embeddings on initialization: {e}",
                exc_info=True,
            )
