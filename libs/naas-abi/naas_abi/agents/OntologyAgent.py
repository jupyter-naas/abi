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

ONTOLOGY_CODE_MAP = f"""Web:
- {_WEB}/app/workspace/[workspaceId]/ontology/page.tsx: Ontology page. View modes network, overview, classes, relations, editor, create-entity, create-relationship (?view=), open ontology via ?ontology=<path>.
- {_WEB}/app/workspace/[workspaceId]/ontology/import/page.tsx and export/page.tsx: import a reference ontology (.ttl), export one file.
- {_WEB}/stores/ontology.ts: items, selection, fetches to /api/ontology/classes, /relationships, /import, /cache/clear.
- {_WEB}/components/shell/sidebar/ontology-section.tsx: Ontology sidebar (catalog tree).
API:
- {_API}/services/ontology/adapters/primary/ontology__primary_adapter__FastAPI.py: /api/ontology routes; ontology_catalog_scope applies the workspace seed.
- {_API}/services/ontology/service.py: OntologyService (list_ontology_files, list_classes, list_relations, overview stats and graph, subclass hierarchy, import, export).
- {_API}/services/ontology/ontology__schema.py: OntologyItemData, OntologyFileItemData, stats dataclasses.
- {_API}/core/workspace_catalog_seed.py: workspace `ontologies:` seed (module:filename.ttl refs, exclusive when set).
Ontology files: naas_abi/ontologies/ (BFO-aligned TTL; imports under naas_abi/ontologies/imports/).
Engine: naas_abi_core/services/triple_store/ (TripleStoreService and adapters).
Related: naas_abi/agents/OntologyEngineerAgent.py (BFO 7 Buckets modeling rules, exposed here as get_bfo_modeling_guidelines).
Agent: naas_abi/agents/OntologyAgent.py and naas_abi/agents/tools/ontology_tools.py."""

ONTOLOGY_CAPABILITIES = """- Browse the workspace's ontology catalog (TTL files from loaded modules, limited to the workspace seed's ontologies: list when it declares one).
- Explore one ontology: network view, overview counts (classes, object and data properties, individuals, imports), class and relation lists, subclass hierarchy.
- Create a class or relationship in the editor (create-entity, create-relationship views), import a reference ontology (.ttl), export an ontology file.
- Get BFO 7 Buckets modeling guidance for a new class or property, with Turtle that follows the house rules.
- Feature flag `ontology` (owners and admins by default)."""

_HANDOFF_PHRASES = (
    "list the ontologies",
    "which classes are in the ontology",
    "explain this ontology",
    "import an ontology",
    "export an ontology",
    "liste les ontologies",
    "quelles classes dans l'ontologie",
    "explique cette ontologie",
    "importer une ontologie",
)


class OntologyAgent(IntentAgent):
    """Office agent for the Nexus Ontology UI (distinct from Ontology Engineer).

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi OntologyAgent
    """

    name: str = "Ontology"
    description: str = (
        "Office agent for Nexus Ontology. Lists the workspace's ontologies, "
        "their classes and relations and counts, explains import/export and "
        "the editor, gives BFO modeling guidance, and explains how the "
        "Ontology feature is built, from the code."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    recursion_limit: int = FEATURE_RECURSION_LIMIT
    system_prompt: str = feature_system_prompt(
        name="Ontology",
        class_name="OntologyAgent",
        feature="Ontology",
        role="You explore the workspace's ontology catalog and explain the Ontology UI.",
        context=(
            "On the Ontology page you receive an open-feature block (feature: "
            "ontology, and open_ontology_id with the ontology file path when one "
            "is open). Tools default to that ontology."
        ),
        tasks="""1. "What can I do here?": answer from <capabilities>, tied to the real catalog (list_workspace_ontologies).
2. "How is it built?": read <code_map> files first, then explain with paths.
3. Content questions: get_ontology_overview, list_ontology_classes, list_ontology_relations.
4. Modeling a new class or property: get_bfo_modeling_guidelines, then propose Turtle. Say the user adds it in the editor or by importing a .ttl; you do not write ontologies.""",
        capabilities=ONTOLOGY_CAPABILITIES,
        code_map=ONTOLOGY_CODE_MAP,
        constraints="- Never claim you created, imported, or deleted an ontology item: you have no write tools.",
    )
    suggestions: list[dict] = [
        {"label": "What can you do?", "value": "What can I do in Ontology?"},
        {
            "label": "How is it built?",
            "value": "How is the Ontology feature implemented? Read the code and cite files.",
        },
        {"label": "This ontology", "value": "Summarize the open ontology."},
    ]

    @staticmethod
    def handoff_intents() -> list[Intent]:
        return feature_handoff_intents("Ontology", _HANDOFF_PHRASES)

    @staticmethod
    def get_tools() -> list:
        from naas_abi.agents.tools.nexus_source_tools import nexus_source_tools
        from naas_abi.agents.tools.ontology_tools import ontology_tools

        return ontology_tools() + nexus_source_tools()

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
    ) -> "OntologyAgent":
        return build_feature_agent(
            cls,
            tools=cls.get_tools(),
            intents=cls.handoff_intents(),
            agent_shared_state=agent_shared_state,
            agent_configuration=agent_configuration,
            model_id=model_id,
        )
