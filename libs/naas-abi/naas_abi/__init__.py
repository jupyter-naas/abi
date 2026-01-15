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


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            "naas_abi_core.modules.templatablesparqlquery",
            "naas_abi_marketplace.ai.chatgpt",
            "naas_abi_marketplace.ai.claude#soft",
            "naas_abi_marketplace.ai.deepseek#soft",
            "naas_abi_marketplace.ai.gemini#soft",
            "naas_abi_marketplace.ai.gemma#soft",
            "naas_abi_marketplace.ai.grok#soft",
            "naas_abi_marketplace.ai.llama#soft",
            "naas_abi_marketplace.ai.mistral#soft",
            "naas_abi_marketplace.ai.perplexity#soft",
            "naas_abi_marketplace.ai.qwen#soft",
            "naas_abi_marketplace.applications.agicap#soft",
            "naas_abi_marketplace.applications.airtable#soft",
            "naas_abi_marketplace.applications.algolia#soft",
            "naas_abi_marketplace.applications.arxiv#soft",
            "naas_abi_marketplace.applications.aws#soft",
            "naas_abi_marketplace.applications.bodo#soft",
            "naas_abi_marketplace.applications.datagouv#soft",
            "naas_abi_marketplace.applications.exchangeratesapi#soft",
            "naas_abi_marketplace.applications.git#soft",
            "naas_abi_marketplace.applications.github#soft",
            "naas_abi_marketplace.applications.gmail#soft",
            "naas_abi_marketplace.applications.google_analytics#soft",
            "naas_abi_marketplace.applications.google_calendar#soft",
            "naas_abi_marketplace.applications.google_drive#soft",
            "naas_abi_marketplace.applications.google_maps#soft",
            "naas_abi_marketplace.applications.google_search#soft",
            "naas_abi_marketplace.applications.google_sheets#soft",
            "naas_abi_marketplace.applications.hubspot#soft",
            "naas_abi_marketplace.applications.instagram#soft",
            "naas_abi_marketplace.applications.linkedin#soft",
            "naas_abi_marketplace.applications.mercury#soft",
            "naas_abi_marketplace.applications.naas#soft",
            "naas_abi_marketplace.applications.nebari#soft",
            "naas_abi_marketplace.applications.newsapi#soft",
            "naas_abi_marketplace.applications.notion#soft",
            "naas_abi_marketplace.applications.openalex#soft",
            "naas_abi_marketplace.applications.openrouter#soft",
            "naas_abi_marketplace.applications.openweathermap#soft",
            "naas_abi_marketplace.applications.pennylane#soft",
            "naas_abi_marketplace.applications.postgres#soft",
            "naas_abi_marketplace.applications.powerpoint#soft",
            "naas_abi_marketplace.applications.pubmed#soft",
            "naas_abi_marketplace.applications.qonto#soft",
            "naas_abi_marketplace.applications.salesforce#soft",
            "naas_abi_marketplace.applications.sanax#soft",
            "naas_abi_marketplace.applications.sendgrid#soft",
            "naas_abi_marketplace.applications.sharepoint#soft",
            "naas_abi_marketplace.applications.slack#soft",
            "naas_abi_marketplace.applications.spotify#soft",
            "naas_abi_marketplace.applications.stripe#soft",
            "naas_abi_marketplace.applications.twilio#soft",
            "naas_abi_marketplace.applications.whatsapp_business#soft",
            "naas_abi_marketplace.applications.worldbank#soft",
            "naas_abi_marketplace.applications.yahoofinance#soft",
            "naas_abi_marketplace.applications.youtube#soft",
            "naas_abi_marketplace.applications.zoho#soft",
            "naas_abi_marketplace.domains.support#soft",
        ],
        services=[Secret, TripleStoreService, ObjectStorageService],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi
        enabled: true
        config:
            datastore_path: "abi"
            workspace_id: "{{ secret.WORKSPACE_ID }}"
            storage_name: "{{ secret.STORAGE_NAME }}"
        """

        datastore_path: str = "abi"
        workspace_id: str | None = None
        storage_name: str | None = None

    # def on_initialized(self):
    #     if (
    #         self.configuration.anthropic_api_key is not None
    #         and "naas_abi_marketplace.ai.claude" not in self.engine.modules
    #     ):
    #         raise ValueError(
    #             "anthropic_api_key is provided but naas_abi_marketplace.ai.claude is not available"
    #         )
