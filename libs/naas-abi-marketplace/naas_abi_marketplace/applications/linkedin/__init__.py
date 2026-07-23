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
            "naas_abi_marketplace.applications.google_search",
            "naas_abi_marketplace.applications.naas",
            "naas_abi_core.modules.templatablesparqlquery",
        ],
        services=[ObjectStorageService, TripleStoreService, Secret, VectorStoreService],
    )

    def on_initialized(self):
        super().on_initialized()

        from naas_abi_core import logger
        from naas_abi_marketplace.applications.linkedin.workflows.CreateClassEmbeddingsWorkflow import (
            CreateClassEmbeddingsWorkflow,
            CreateClassEmbeddingsWorkflowConfiguration,
            CreateClassEmbeddingsWorkflowParameters,
        )

        # Ontology -> Python codegen is deliberately not run at boot.
        #
        # `on_initialized` fires on every `Engine.load()`: every API start, every
        # uvicorn reload after a file is saved, every `abi chat`, every dagster
        # boot. `onto2py()` is expensive on all of them. It runs BFO static
        # validation and resolves `owl:imports`, which walks every project root
        # and rdflib-parses every `.ttl` beneath it — 439 files and ~7s on the
        # checkout this was measured on — then fetches any IRI it could not
        # resolve locally over HTTP, with a 10s timeout per import and no
        # caching. Behind a proxy or a slow resolver that turns a ~30s engine
        # load into minutes, and the reload child pays it again on every save.
        #
        # The generated modules are committed, so boot has nothing to
        # regenerate. Run the generator when a .ttl actually changes:
        #     python -m naas_abi_core.utils.onto2py <ttl_file>
        #
        # Note: the commented-out block below ended with an early `return` when
        # no .ttl was found, which also skipped the embeddings workflow that
        # follows. This module ships a .ttl, so that path never ran in practice.
        #
        # import glob
        # import os
        #
        # from naas_abi_core.utils.onto2py import onto2py
        #
        # ontologies_dir = os.path.join(os.path.dirname(__file__), "ontologies")
        # ttl_files = glob.glob(
        #     os.path.join(ontologies_dir, "modules", "*.ttl"), recursive=True
        # )
        #
        # if not ttl_files:
        #     logger.warning(f"No TTL files found in {ontologies_dir}")
        #     return
        #
        # for ttl_file in ttl_files:
        #     if "Queries.ttl" in ttl_file:
        #         continue
        #     try:
        #         logger.debug(f"Converting {ttl_file} to Python")
        #         onto2py(ttl_file)
        #     except Exception as e:
        #         logger.error(
        #             f"Failed to convert {ttl_file} to Python: {e}", exc_info=True
        #         )

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
