"""Market seed pipeline: one curated market file -> the market's graph.

    <datastore_path>/<MarketFolder>/<MarketFolder>.yaml
      market:        label, key, definition
      segmentation:  analyst, period, source, segments[label, key, criterion, parents, definition]
      competitors:   [market (key), source, items[organization, region, period, share_percent, rank, ...]]
      yahoofinance:  [market (key), tickers[symbol, organization, region, period]]
      sizes:         [market (key), value, currency, year, region, growth..., analyst, source]
      swot:          [market (key), analyst, region, period, source, opportunities, threats,
                      strengths[organization, statement], weaknesses[...]]
      -> every process pipeline, in one MarketGraphContext
      -> <datastore_path>/<MarketFolder>/<MarketFolder>.ttl, and the triple store

Sections name the market they are about by key; without one they are about the
root market. Each section is optional except ``market``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.pipeline import Pipeline, PipelineParameters
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketAnalysisPipeline import (
    MarketAnalysisPipeline,
    MarketAnalysisPipelineParameters,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketCompetitorPipeline import (
    MarketCompetitorPipeline,
    MarketCompetitorPipelineParameters,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketSegmentationPipeline import (
    MarketSegmentationPipeline,
    MarketSegmentationPipelineParameters,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketSizingPipeline import (
    MarketSizingPipeline,
    MarketSizingPipelineParameters,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.utils.base import (
    MarketPipelineConfiguration,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.utils.graph_builders import (
    MarketGraphContext,
    MarketParameters,
    slug,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.YahooFinanceCompetitorPipeline import (
    YahooFinanceCompetitorPipeline,
    YahooFinanceCompetitorPipelineConfiguration,
    YahooFinanceCompetitorPipelineParameters,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.utils.company_directory import (
    CompanyDirectoryPort,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.utils.market_storage import (
    read_market_spec,
    write_market_graph,
)
from pydantic import Field
from rdflib import Graph


@dataclass
class MarketSeedPipelineConfiguration(MarketPipelineConfiguration):
    object_storage: ObjectStorageService | None = None
    datastore_path: str = "intelligence/markets"
    # Without a directory the ``yahoofinance`` section is skipped.
    directory: CompanyDirectoryPort | None = None
    creator: str = "MarketSeedPipeline"


class MarketSeedPipelineParameters(PipelineParameters):
    folder: str | None = Field(
        default=None,
        description="Market folder in the datastore, e.g. 'CloudComputing' (reads <folder>/<folder>.yaml)",
    )
    spec: dict[str, Any] | None = Field(
        default=None,
        description="The market spec itself, instead of reading it from a folder",
    )


class MarketSeedPipeline(Pipeline):
    __configuration: MarketSeedPipelineConfiguration

    def __init__(self, configuration: MarketSeedPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def _spec(self, parameters: MarketSeedPipelineParameters) -> dict[str, Any]:
        if parameters.spec is not None:
            return parameters.spec
        config = self.__configuration
        if parameters.folder is None or config.object_storage is None:
            raise ValueError(
                "give a spec, or a folder and an object storage to read it from"
            )
        return read_market_spec(
            config.object_storage, config.datastore_path, parameters.folder
        )

    def run(self, parameters: MarketSeedPipelineParameters) -> Graph:
        config = self.__configuration
        spec = self._spec(parameters)
        context = config.context or MarketGraphContext(creator=config.creator)

        root = MarketParameters.model_validate(spec["market"])
        segmentation = spec.get("segmentation") or {}
        markets: dict[str, MarketParameters] = {slug(root.key or root.label): root}
        for segment in segmentation.get("segments", []):
            market = MarketParameters.model_validate(
                {k: segment[k] for k in ("label", "key", "definition") if k in segment}
            )
            markets[slug(market.key or market.label)] = market

        def market_of(section: dict[str, Any]) -> MarketParameters:
            key = section.get("market")
            if key is None:
                return root
            if slug(key) not in markets:
                raise ValueError(f"unknown market '{key}' in {spec['market']['label']}")
            return markets[slug(key)]

        if segmentation:
            MarketSegmentationPipeline.build(
                context,
                MarketSegmentationPipelineParameters.model_validate(
                    {**segmentation, "market": root}
                ),
            )
        else:
            context.ensure_market(root)

        for section in spec.get("competitors", []):
            MarketCompetitorPipeline.build(
                context,
                MarketCompetitorPipelineParameters(
                    market=market_of(section),
                    source=section.get("source"),
                    competitors=section["items"],
                ),
            )

        if config.directory is not None:
            yahoo = YahooFinanceCompetitorPipeline(
                YahooFinanceCompetitorPipelineConfiguration(
                    directory=config.directory,
                    object_storage=config.object_storage,
                    datastore_path=config.datastore_path,
                    persist=False,
                )
            )
            for section in spec.get("yahoofinance", []):
                params = YahooFinanceCompetitorPipelineParameters(
                    market=market_of(section), tickers=section["tickers"]
                )
                # Files the quotes under the root market's folder, whichever segment they are for.
                folder_params = params.model_copy(update={"market": root})
                profiles = yahoo.profiles(folder_params)
                YahooFinanceCompetitorPipeline.build(context, params, profiles)

        for section in spec.get("sizes", []):
            MarketSizingPipeline.build(
                context,
                MarketSizingPipelineParameters.model_validate(
                    {**section, "market": market_of(section)}
                ),
            )

        for section in spec.get("swot", []):
            MarketAnalysisPipeline.build(
                context,
                MarketAnalysisPipelineParameters.model_validate(
                    {**section, "market": market_of(section)}
                ),
            )

        graph = context.graph
        if config.object_storage is not None:
            write_market_graph(
                config.object_storage, config.datastore_path, root.label, graph
            )
        if config.persist and config.triple_store is not None:
            config.triple_store.insert(graph, graph_name=config.graph_name)
        return graph

    def as_tools(self) -> list[BaseTool]:
        def _run(folder: str) -> str:
            graph = self.run(MarketSeedPipelineParameters(folder=folder))
            return f"Loaded market '{folder}' ({len(graph)} triples)."

        return [
            StructuredTool.from_function(
                func=_run,
                name="load_market_from_datastore",
                description=(
                    "Build a market's graph from its curated file in the datastore "
                    "(intelligence/markets/<Folder>/<Folder>.yaml), e.g. folder 'CloudComputing'."
                ),
            )
        ]

    def as_api(self) -> None:
        pass
