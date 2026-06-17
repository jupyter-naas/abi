from fastapi import FastAPI
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.event.EventService import EventService
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.triple_store.TripleStoreService import (
    TripleStoreService,
)
from pydantic import BaseModel, Field


class XTweetSearchWorkflowConfiguration(BaseModel):
    """One configured X v2 search filter that the XOrchestration polls on a
    schedule via :class:`XSearchRecentTweetsWorkflow`.

    The workflow recovers each query's ``since_id`` from the persisted JSON
    envelopes in object storage and writes the mapped graph to a ``.ttl`` next
    to the source envelope. Each entry produces its own Dagster job + sensor
    pair; the sensor wakes every ``interval_seconds`` and triggers a run that
    fetches only tweets newer than the last persisted ``newest_id`` for the
    same ``query``.
    """

    name: str = Field(
        description=(
            "Short identifier (letters/digits/underscores) used to name "
            "the generated Dagster job and sensor — must be unique across "
            "the module's tweet_search_workflow_pipelines."
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
    max_pages: int | None = Field(
        default=1,
        ge=1,
        description=(
            "Maximum pages to fetch per run. Set null to exhaust every new "
            "tweet since the last run; combined with the since_id cursor this "
            "caps the amount of work done per tick."
        ),
    )
    sort_order: str = Field(
        default="recency",
        description="Order results are returned in: 'recency' or 'relevancy'.",
    )
    persist: bool = Field(
        default=True,
        description=(
            "Whether the workflow inserts the mapped tweet graph into the "
            "configured triple store. Set false to fetch and persist the JSON "
            "envelopes (and write the .ttl) without writing to the triple store."
        ),
    )


class XTweetFileIngestionConfiguration(BaseModel):
    """One configured drop-folder that the XOrchestration polls for tweet
    dataset files. Each entry produces its own Dagster job + sensor pair:
    the sensor lists *input_prefix* in object storage every
    ``interval_seconds``, and any object that hasn't already been ingested
    (sha256-based dedupe in the graph) triggers a run that streams the
    file through :class:`XFileIngestionPipeline`.

    Designed for large datasets — the pipeline never buffers the whole
    file in memory; NDJSON is read line by line and JSON arrays are
    incrementally parsed via ijson, so a 12 GB dump uses constant memory.
    """

    name: str = Field(
        description=(
            "Short identifier (letters/digits/underscores) used to name "
            "the generated Dagster job and sensor."
        )
    )
    input_prefix: str = Field(
        default="x/uploads",
        description=(
            "Object-storage prefix to watch. Drop tweet dump files under "
            "this prefix and the sensor will pick them up on its next "
            "tick. Accepted shapes (auto-detected): "
            "(a) one big JSON array of bare tweet dicts — same as the "
            "files that XIntegration.search_recent_tweets's cache writes "
            "to ``<datastore_path>/search_recent_tweets/<hash>.json``, so "
            "point this at that directory to back-fill from the cache; "
            "(b) one X v2 ``{data:[...], meta:{...}}`` response — what "
            "you'd get if you piped the API output to a file; "
            "(c) JSONL of either shape — one tweet per line, or one "
            "response envelope per line. ``.gz`` variants also work."
        ),
    )
    interval_seconds: int = Field(
        default=60,
        ge=30,
        description="Minimum delay between two sensor evaluations.",
    )
    batch_size: int = Field(
        default=500,
        ge=10,
        le=10_000,
        description=(
            "Number of tweet records to accumulate before flushing as one "
            "SPARQL INSERT into the named graph. Larger = fewer round "
            "trips but more memory; smaller = lower memory ceiling."
        ),
    )
    recursive: bool = Field(
        default=False,
        description=(
            "If True, also pick up files in sub-prefixes under "
            "input_prefix. Default off to mirror DocumentOrchestration."
        ),
    )
    delete_after_ingest: bool = Field(
        default=False,
        description=(
            "If True, delete the source object once ingestion succeeds. "
            "Off by default so re-running stays a no-op (sha256 dedupe) "
            "and the operator can inspect the original."
        ),
    )


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            "naas_abi_core.modules.templatablesparqlquery",
        ],
        services=[ObjectStorageService, Secret, TripleStoreService, EventService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.applications.x
        enabled: true
        config:
            bearer_token: "{{ secret.X_BEARER_TOKEN }}"

            # ----- Search-workflow pipelines -------------------------------
            # One sensor per entry. Every `interval_seconds` the sensor runs
            # XSearchRecentTweetsWorkflow for `query` (incrementally, from the
            # last seen tweet id), then maps each persisted envelope into the
            # graph via XSearchRecentTweetsPipeline.
            tweet_search_workflow_pipelines:
              - name: ai_llms
                query: "(openai OR anthropic OR \"llm\" OR \"large language model\") lang:en -is:retweet"
                interval_seconds: 60
                max_results: 100
                max_pages: 1
                sort_order: recency      # 'recency' or 'relevancy'
                persist: true
        """

        bearer_token: str | None = None
        datastore_path: str = "x"
        ontology_namespace: str = "http://ontology.naas.ai/x/"
        graph_name: str = "http://ontology.naas.ai/graph/x"
        search_recent_tweets_workflow: list[XTweetSearchWorkflowConfiguration] = []
        file_ingestion_pipeline: list[XTweetFileIngestionConfiguration] = []

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
