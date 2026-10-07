from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService


class ABIModule(BaseModule):
    """Market intelligence: what is true about a market.

    How a market divides into segments, which organizations compete in each,
    how big it is and how fast it grows, and its SWOT: opportunities and
    threats for the market, strengths and weaknesses for each competitor.
    Competitors are the organizations of the organizations module, addressed
    by the same IRIs; Yahoo Finance enriches the listed ones.
    """

    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[
            # MarketsAgent.get_tools() resolves its SPARQL tools through this
            # module, so it must be loaded before the agent is built.
            "naas_abi_core.modules.templatablesparqlquery",
            "naas_abi_marketplace.domains.intelligence.modules.organizations#soft",
            "naas_abi_marketplace.applications.yahoofinance#soft",
        ],
        services=[
            TripleStoreService,
            ObjectStorageService,
        ],
    )

    class Configuration(ModuleConfiguration):
        """
        module: naas_abi_marketplace.domains.intelligence.modules.markets
        enabled: true
        """

        # Each market's files: <datastore_path>/<Key>/<Key>.yaml (the market as
        # curated), <Key>/<Key>.ttl (the graph built from it) and
        # <Key>/yahoofinance/<SYMBOL>.json (the quotes its competitors were read from).
        datastore_path: str = "intelligence/markets"
        graph_name: str = "http://ontology.naas.ai/graph/markets"
