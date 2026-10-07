from __future__ import annotations

from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class MarketsAgent(Agent):
    name: str = "Markets"
    description: str = (
        "Market intelligence analyst: how a market is segmented, who competes in "
        "it, how big it is and its SWOT, every statement with its source."
    )
    system_prompt: str = """<role>
You are MarketsAgent, a market intelligence analyst. You know how markets divide
into segments, which organizations compete in each, how big they are and how
fast they grow, and their strengths, weaknesses, opportunities and threats.
</role>

<objective>
Answer questions about markets from the markets graph, and register what a
source states about a market, using the tools available to you.
</objective>

<tools>
[TOOLS]
</tools>

<operating_guidelines>
- Resolve the market first (find_markets), then answer from the segment level
  the question is about.
- Give every figure with its year, region and source. Never sum the sizes of
  segments cut along different criteria (IaaS and Public Cloud overlap), and
  never average sizes from different sources: show them side by side.
- Opportunities and threats belong to the market; strengths and weaknesses to
  one competitor in it. Keep them apart.
- To add listed competitors, use their Yahoo Finance symbols. Industry
  candidates from Yahoo Finance are broad (an industry mixes cloud providers
  with security vendors): check each one actually sells in the market before
  registering it, and say which ones you dropped.
- Distinguish what a source states from what you infer.
- Format responses as clean, well-structured Markdown.
</operating_guidelines>

<constraints>
- Preserve the language of the user's message in your response.
- Only use the provided tools - do not fabricate data or capabilities.
- Never register a size, share or finding without the source that states it.
</constraints>
"""
    suggestions: list[dict] = [
        {
            "label": "Segments",
            "value": "How is the {{Market}} market segmented?",
            "description": "Submarkets and the criterion each is cut along",
        },
        {
            "label": "Competitors",
            "value": "Who competes in the {{Market}} market?",
            "description": "Competitors per segment with share, rank and source",
        },
        {
            "label": "Size",
            "value": "How big is the {{Market}} market?",
            "description": "Every sourced size and growth rate",
        },
        {
            "label": "SWOT",
            "value": "What is the SWOT of the {{Market}} market?",
            "description": "Opportunities, threats, and competitors' strengths and weaknesses",
        },
    ]

    @classmethod
    def get_sparql_tools(cls) -> list:
        """Load the markets SPARQL competency-question tools by name."""
        from naas_abi_core.module.Module import BaseModule
        from naas_abi_core.modules.templatablesparqlquery import (
            ABIModule as TemplatableSparqlQueryABIModule,
        )
        from naas_abi_marketplace.domains.intelligence.modules.markets import ABIModule

        templatable_sparql_query_module: BaseModule = (
            ABIModule.get_instance().engine.modules[
                "naas_abi_core.modules.templatablesparqlquery"
            ]
        )
        assert isinstance(
            templatable_sparql_query_module, TemplatableSparqlQueryABIModule
        ), "TemplatableSparqlQueryABIModule must be a subclass of BaseModule"

        markets_sparql_tools = [
            "find_markets",
            "find_market_segments",
            "find_market_competitors",
            "find_markets_of_organization",
            "find_competitors_of_organization",
            "find_market_sizes",
            "find_market_swot",
        ]
        return list(templatable_sparql_query_module.get_tools(markets_sparql_tools))

    @classmethod
    def get_pipeline_tools(cls) -> list:
        """Registration pipelines, Yahoo Finance competitors and the market seed."""
        from naas_abi_marketplace.domains.intelligence.modules.markets import ABIModule
        from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketAnalysisPipeline import (
            MarketAnalysisPipeline,
            MarketAnalysisPipelineConfiguration,
        )
        from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketCompetitorPipeline import (
            MarketCompetitorPipeline,
            MarketCompetitorPipelineConfiguration,
        )
        from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketSeedPipeline import (
            MarketSeedPipeline,
            MarketSeedPipelineConfiguration,
        )
        from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketSegmentationPipeline import (
            MarketSegmentationPipeline,
            MarketSegmentationPipelineConfiguration,
        )
        from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketSizingPipeline import (
            MarketSizingPipeline,
            MarketSizingPipelineConfiguration,
        )
        from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.YahooFinanceCompetitorPipeline import (
            YahooFinanceCompetitorPipeline,
            YahooFinanceCompetitorPipelineConfiguration,
        )
        from naas_abi_marketplace.domains.intelligence.modules.markets.utils.company_directory import (
            YahooFinanceCompanyDirectory,
        )
        from rdflib import URIRef

        module = ABIModule.get_instance()
        services = module.engine.services
        pipeline_cfg = {
            "triple_store": services.triple_store,
            "graph_name": URIRef(module.configuration.graph_name),
            "persist": True,
        }
        storage_cfg = {
            "object_storage": services.object_storage,
            "datastore_path": module.configuration.datastore_path,
        }
        directory = YahooFinanceCompanyDirectory()
        return [
            *MarketSegmentationPipeline(
                MarketSegmentationPipelineConfiguration(**pipeline_cfg)
            ).as_tools(),
            *MarketCompetitorPipeline(
                MarketCompetitorPipelineConfiguration(**pipeline_cfg)
            ).as_tools(),
            *YahooFinanceCompetitorPipeline(
                YahooFinanceCompetitorPipelineConfiguration(
                    directory=directory, **pipeline_cfg, **storage_cfg
                )
            ).as_tools(),
            *MarketSizingPipeline(
                MarketSizingPipelineConfiguration(**pipeline_cfg)
            ).as_tools(),
            *MarketAnalysisPipeline(
                MarketAnalysisPipelineConfiguration(**pipeline_cfg)
            ).as_tools(),
            *MarketSeedPipeline(
                MarketSeedPipelineConfiguration(
                    directory=directory, **pipeline_cfg, **storage_cfg
                )
            ).as_tools(),
        ]

    @classmethod
    def get_tools(cls) -> list:
        """SPARQL query tools and process registration pipelines."""
        return list(cls.get_sparql_tools()) + list(cls.get_pipeline_tools())

    @classmethod
    def New(
        cls,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AgentConfiguration | None = None,
    ) -> MarketsAgent:
        from naas_abi_core.engine.context import get_default_model_registry

        # Use the workspace's default chat model from the model registry.
        registry = get_default_model_registry()
        assert registry is not None, "ModelRegistryService not initialized"
        chat_model = registry.get_default_chat_model()

        tools: list = cls.get_tools()

        if agent_configuration is None:
            tools_section = "\n".join(
                f"- {tool.name}: {tool.description}" for tool in tools
            )
            agent_configuration = AgentConfiguration(
                system_prompt=cls.system_prompt.replace("[TOOLS]", tools_section)
            )

        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return cls(
            name=cls.name,
            description=cls.description,
            chat_model=chat_model,
            tools=tools,
            agents=[],
            memory=None,
            state=agent_shared_state,
            configuration=agent_configuration,
        )
