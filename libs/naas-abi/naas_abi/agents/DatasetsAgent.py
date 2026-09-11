from naas_abi.agents.feature import (
    FEATURE_RECURSION_LIMIT,
    build_feature_agent,
    configured_feature_model,
    feature_handoff_intents,
    feature_system_prompt,
)
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
)

_WEB = "naas_abi/apps/nexus/apps/web/src"
_API = "naas_abi/apps/nexus/apps/api/app"

DATASETS_CODE_MAP = f"""Web:
- {_WEB}/app/workspace/[workspaceId]/datasets/datasets.tsx: datasets catalog page.
- {_WEB}/app/workspace/[workspaceId]/datasets/[namespace]/[name]/table.tsx: one dataset (schema, preview grid, SQL).
- {_WEB}/app/workspace/[workspaceId]/datasets/lib/datasets-route.ts and components/datasets-section.tsx: routes and sidebar.
- {_WEB}/stores/datasets.ts: fetches to /api/datasets.
API:
- {_API}/services/datasets/adapters/primary/datasets__primary_adapter__FastAPI.py: GET /api/datasets/, GET /api/datasets/{{namespace}}/{{name}}, GET .../preview, POST /api/datasets/{{namespace}}/query.
- {_API}/services/datasets/service.py: DatasetsService (read-only catalog, preview, query with limits).
- {_API}/services/datasets/sql_safe.py (and sql_safe_test.py): assert_read_only_sql, clamp_limit, preview_sql.
- {_API}/services/datasets/datasets__schema.py: dataset dataclasses and errors.
Engine: naas_abi_core/services/dataset/ (DatasetPort, DatasetService, DuckLake adapter; see its AGENTS.md).
Agent: naas_abi/agents/DatasetsAgent.py and naas_abi/agents/tools/datasets_tools.py."""

DATASETS_CAPABILITIES = """- Browse structured datasets by namespace: columns and types, partitions, primary key, snapshot, storage location.
- Preview rows and run read-only SQL (SELECT) over a namespace; results are row-capped and time-limited. Writes and DDL are rejected.
- Pick a snapshot to time-travel a dataset.
- Datasets are produced by pipelines and modules (the engine dataset service); the UI is read-only.
- Feature flag `datasets` (on for every role by default)."""

_HANDOFF_PHRASES = (
    "list the datasets",
    "query a dataset",
    "show the dataset schema",
    "preview the dataset",
    "run sql on the dataset",
    "liste les datasets",
    "interroge le dataset",
    "schéma du dataset",
    "requête sql sur le dataset",
)


class DatasetsAgent(IntentAgent):
    """Office agent for Nexus Datasets (read-only catalog + SQL).

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi DatasetsAgent
    """

    name: str = "Datasets"
    description: str = (
        "Office agent for Nexus Datasets. Lists datasets, shows schemas, "
        "previews rows, runs read-only SQL, and explains how Datasets is "
        "built, from the code."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    recursion_limit: int = FEATURE_RECURSION_LIMIT
    system_prompt: str = feature_system_prompt(
        name="Datasets",
        class_name="DatasetsAgent",
        feature="Datasets",
        role="You query the workspace's structured datasets and explain the Datasets UI.",
        context=(
            "On a dataset page you receive an open-feature block (feature: "
            "datasets, and open_dataset_id as namespace/name when one is open). "
            "Tools default to it."
        ),
        tasks="""1. "What can I do here?": answer from <capabilities>, tied to real datasets (list_datasets).
2. "How is it built?": read <code_map> files first, then explain with paths.
3. Data questions: describe_dataset first, then preview_dataset or query_datasets with a SELECT that uses real column names.
4. Report the rows you got; say when results were truncated.""",
        capabilities=DATASETS_CAPABILITIES,
        code_map=DATASETS_CODE_MAP,
        constraints="- Only write SELECT queries; never try to modify a dataset.",
    )
    suggestions: list[dict] = [
        {"label": "What can you do?", "value": "What can I do with Datasets?"},
        {
            "label": "How is it built?",
            "value": "How is SQL kept read-only in Datasets? Read the code and cite files.",
        },
        {"label": "This dataset", "value": "Describe the open dataset and preview it."},
    ]

    @staticmethod
    def handoff_intents() -> list[Intent]:
        return feature_handoff_intents("Datasets", _HANDOFF_PHRASES)

    @staticmethod
    def get_tools() -> list:
        from naas_abi.agents.tools.datasets_tools import datasets_tools
        from naas_abi.agents.tools.nexus_source_tools import nexus_source_tools

        return datasets_tools() + nexus_source_tools()

    @classmethod
    def get_chat_model_id(cls) -> str:
        return configured_feature_model()

    @classmethod
    def get_chat_model_ids(cls) -> list[str]:
        return [configured_feature_model()]

    @classmethod
    def New(
        cls,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AgentConfiguration | None = None,
        model_id: str | None = None,
    ) -> "DatasetsAgent":
        return build_feature_agent(
            cls,
            tools=cls.get_tools(),
            intents=cls.handoff_intents(),
            agent_shared_state=agent_shared_state,
            agent_configuration=agent_configuration,
            model_id=model_id,
        )
