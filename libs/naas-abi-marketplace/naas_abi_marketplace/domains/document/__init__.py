from fastapi import FastAPI
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService
from pydantic import BaseModel


class FileIngestionConfiguration(BaseModel):
    input_path: str = "documents/input"
    output_path: str = "documents/output"
    graph_name: str = "http://ontology.naas.ai/graph/document"
    recursive: bool = True
    delete_from_input: bool = False


class MarkdownToVectorConfiguration(BaseModel):
    """Configuration for a single MarkdownToVector pipeline instance."""

    collection_name: str = "documents"
    file_path: str = ""
    model_id: str = "text-embedding-3-small"
    dimension: int = 1536
    chunk_size: int = 1000
    chunk_overlap: int = 200
    api_key: str  # API Key to authenticate the model_id calls. Not optional


class PdfToHtmlImageDescriptionConfiguration(BaseModel):
    """Optional vision-LLM captioning configured on ``PdfToHtmlPipeline``.

    When set, docling calls an OpenAI-compatible vision endpoint for each
    image found in the PDF and injects the description as a ``<figcaption>``
    in the exported HTML. Same pipeline run; no separate enrichment step.

    Uses OpenRouter by default so any vision model exposed by the provider
    can be selected by changing ``model``.
    """

    api_key: str  # API key for the OpenAI-compatible vision endpoint
    base_url: str = "https://openrouter.ai/api/v1/chat/completions"
    model: str = "google/gemini-2.0-flash-001"
    prompt: str = (
        "Describe this image in one or two sentences, focusing on factual "
        "content that would be useful for document understanding (people, "
        "charts, tables, diagrams, scenes). Be concise and factual."
    )
    concurrency: int = 4
    timeout_seconds: float = 30.0
    picture_area_threshold: float = 0.05  # skip images < 5% of page area


class HtmlToVectorConfiguration(BaseModel):
    """Configuration for a single HtmlToVector pipeline instance."""

    collection_name: str = "documents"
    file_path: str = ""
    model_id: str = "text-embedding-3-small"
    dimension: int = 1536
    chunk_size: int = 1000
    chunk_overlap: int = 200
    api_key: str  # API Key to authenticate the model_id calls. Not optional


class DocumentAgentConfiguration(BaseModel):
    """Configuration for the DocumentAgent."""

    model_id: str = "text-embedding-3-small"
    dimension: int = 1536
    api_key: str  # API Key to authenticate the embeddings calls. Not optional


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[
            Secret,
            TripleStoreService,
            ObjectStorageService,
            VectorStoreService,
            BusService,
            KeyValueService,
        ],
    )

    class Configuration(ModuleConfiguration):
        file_ingestion_pipelines: list[FileIngestionConfiguration] = [
            FileIngestionConfiguration()
        ]
        pdftomarkdown_enabled: bool = True
        pdftohtml_enabled: bool = True
        docxtomarkdown_enabled: bool = True
        pptxtomarkdown_enabled: bool = True
        markdowntovector_pipelines: list[MarkdownToVectorConfiguration] = []
        htmltovector_pipelines: list[HtmlToVectorConfiguration] = []
        pdftohtml_image_description: PdfToHtmlImageDescriptionConfiguration | None = (
            None
        )
        document_agent: DocumentAgentConfiguration

    # on_initialized is called by the engine after all modules and services have been fully loaded.
    # At this point, you can safely access other modules and services through the engine's interfaces.
    # Override this method to implement any post-initialization logic your module requires.
    def on_initialized(self) -> None:
        super().on_initialized()

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
        # import glob
        # import os
        #
        # # Convert ontologies to Python classes.
        # from naas_abi_core import logger
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
        #     try:
        #         logger.debug(f"Converting {ttl_file} to Python")
        #         onto2py(ttl_file)
        #     except Exception as e:
        #         logger.error(
        #             f"Failed to convert {ttl_file} to Python: {e}", exc_info=True
        #         )

    # The on_load method is invoked during initial module loading by the engine.
    # At this point, avoid accessing services or other modules, as they have not been loaded yet.
    # Place any logic here that must occur right as the module is loaded, before initialization.
    # You can see it as the constructor of the module.
    def on_load(self):
        super().on_load()

    # Optional FastAPI integration hook.
    # This mirrors how `naas_abi` wires API settings and services into app.state.
    # Override and adapt to your module if you expose HTTP routes.
    def api(self, app: FastAPI) -> None:
        # Example: expose services to your API layer.
        # app.state.object_storage = self.engine.services.object_storage
        # app.state.secret_service = self.engine.services.secret
        # app.state.triple_store = self.engine.services.triple_store
        # app.state.vector_store = self.engine.services.vector_store
        # app.state.bus_service = self.engine.services.bus
        # app.state.key_value_service = self.engine.services.kv

        # Example: mount your FastAPI routes/app factory.
        # from your_module.apps.api.app.main import create_app
        # create_app(app)
        pass
