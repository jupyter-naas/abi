from fastapi import FastAPI
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.triple_store.TripleStoreService import (
    TripleStoreService,
)
from pydantic import BaseModel, Field

X_NAMESPACE = "http://ontology.naas.ai/x/"


class XTweetIngestionConfiguration(BaseModel):
    """One configured X v2 search filter that the XOrchestration polls on a
    schedule. Each entry produces its own Dagster job + sensor pair; the
    sensor wakes every ``interval_seconds`` and triggers a run that fetches
    tweets since the last ingested tweet id for the same ``query``.
    """

    name: str = Field(
        description=(
            "Short identifier (letters/digits/underscores) used to name "
            "the generated Dagster job and sensor — must be unique across "
            "the module's tweet_ingestion_pipelines."
        )
    )
    query: str = Field(
        description=(
            "X v2 search query (1-4096 chars). See "
            "https://developer.twitter.com/en/docs/twitter-api/tweets/search/integrate/build-a-query"
        )
    )
    interval_seconds: int = Field(
        default=60,
        ge=30,
        description="Minimum delay between two sensor evaluations.",
    )
    max_results: int = Field(
        default=100,
        ge=10,
        le=100,
        description="Page size forwarded to X v2 search_recent_tweets.",
    )
    max_pages: int = Field(
        default=1,
        ge=1,
        description=(
            "Maximum pages to fetch per run. Combined with the since_id "
            "cursor this caps the amount of work done per minute."
        ),
    )


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            "naas_abi_marketplace.ai.chatgpt",
            "naas_abi_core.modules.templatablesparqlquery",
        ],
        services=[ObjectStorageService, Secret, TripleStoreService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.applications.x
        enabled: true
        config:
            bearer_token: "{{ secret.X_BEARER_TOKEN }}"
            tweet_ingestion_pipelines:
              - name: python_lang_en
                query: "python lang:en -is:retweet"
                interval_seconds: 60
                max_results: 100
              - name: from_twitterdev
                query: "from:TwitterDev"
                interval_seconds: 300
        """

        bearer_token: str
        datastore_path: str = "x"
        ontology_namespace: str = X_NAMESPACE
        graph_name: str = f"{X_NAMESPACE}graph"
        tweet_ingestion_pipelines: list[XTweetIngestionConfiguration] = []

    # on_initialized is called by the engine after all modules and services have been fully loaded.
    # At this point, you can safely access other modules and services through the engine's interfaces.
    # Override this method to implement any post-initialization logic your module requires.
    def on_initialized(self):
        super().on_initialized()

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
