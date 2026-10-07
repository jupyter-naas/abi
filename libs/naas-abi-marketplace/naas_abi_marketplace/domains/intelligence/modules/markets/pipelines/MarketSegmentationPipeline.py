"""Act of Market Segmentation pipeline: a market and the segments it divides into.

    market + segments (each with the criterion it is cut along and its parents)
      -> abi:Market, abi:MarketSegment  (abi:hasMarketSegment / abi:isMarketSegmentOf)
      -> one abi:ActOfMarketSegmentation per (parent, criterion)
         abi:segmentsMarket parent, abi:yieldsMarketSegment segment,
         abi:appliesSegmentationCriterion criterion, abi:hasMarketSource source

A segment names its parents by key or label; with none it belongs to the market
itself. Naming a parent that is another segment builds a deeper tree (GPU cloud
under IaaS), and naming several makes the overlap explicit (GPU cloud is also
Public Cloud).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.pipeline import Pipeline, PipelineParameters
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.utils.base import (
    MarketPipelineConfiguration,
    run_in_context,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.utils.graph_builders import (
    ABI,
    MarketGraphContext,
    MarketParameters,
    SourceParameters,
    individual_uri,
    slug,
)
from pydantic import Field, model_validator
from rdflib import RDFS, Graph, URIRef


class SegmentParameters(MarketParameters):
    criterion: str = Field(
        ...,
        min_length=1,
        description="What the segment is cut along: 'Service model', 'Deployment model', 'Workload', 'Value chain layer'...",
    )
    parents: list[str] = Field(
        default_factory=list,
        description="Keys or labels of the broader markets it belongs to (default: the market)",
    )


@dataclass
class MarketSegmentationPipelineConfiguration(MarketPipelineConfiguration):
    pass


class MarketSegmentationPipelineParameters(PipelineParameters):
    market: MarketParameters
    segments: list[SegmentParameters] = Field(default_factory=list)
    analyst: str | None = Field(
        default=None, description="Organization that made the segmentation"
    )
    period: str | None = Field(
        default=None, description="When it was made, e.g. '2026'"
    )
    source: SourceParameters

    @model_validator(mode="after")
    def parents_are_known(self) -> MarketSegmentationPipelineParameters:
        known = {slug(self.market.key or self.market.label), slug(self.market.label)}
        for segment in self.segments:
            known |= {slug(segment.key or segment.label), slug(segment.label)}
        for segment in self.segments:
            for parent in segment.parents:
                if slug(parent) not in known:
                    raise ValueError(
                        f"segment '{segment.label}' names unknown parent '{parent}'"
                    )
        return self


class MarketSegmentationPipeline(Pipeline):
    __configuration: MarketSegmentationPipelineConfiguration

    def __init__(self, configuration: MarketSegmentationPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: MarketSegmentationPipelineParameters) -> Graph:
        return run_in_context(self.__configuration, lambda c: self.build(c, parameters))

    @staticmethod
    def build(
        context: MarketGraphContext, parameters: MarketSegmentationPipelineParameters
    ) -> None:
        g = context.graph
        market = context.ensure_market(parameters.market)
        uris: dict[str, URIRef] = {
            slug(parameters.market.key or parameters.market.label): market,
            slug(parameters.market.label): market,
        }
        for segment in parameters.segments:
            uri = context.ensure_market(segment, segment=True)
            uris[slug(segment.key or segment.label)] = uri
            uris[slug(segment.label)] = uri

        # One act per (parent, criterion): one analyst dividing one market one way.
        acts: dict[tuple[URIRef, str], list[URIRef]] = defaultdict(list)
        for segment in parameters.segments:
            uri = segment.uri
            criterion = context._individual(
                individual_uri("SegmentationCriterion", slug(segment.criterion)),
                ABI.SegmentationCriterion,
                segment.criterion,
            )
            g.add((uri, ABI.hasSegmentationCriterion, criterion))
            g.add((criterion, ABI.isSegmentationCriterionOf, uri))
            for parent in [uris[slug(p)] for p in segment.parents] or [market]:
                g.add((parent, ABI.hasMarketSegment, uri))
                g.add((uri, ABI.isMarketSegmentOf, parent))
                acts[(parent, segment.criterion)].append(uri)

        for (parent, criterion_label), segments in acts.items():
            parent_key = str(parent).rsplit("/", 1)[-1]
            act = context.act(
                "ActOfMarketSegmentation",
                slug(parent_key, criterion_label),
                f"Segmentation of {g.value(parent, RDFS.label)} by {criterion_label.lower()}",
            )
            criterion = individual_uri("SegmentationCriterion", slug(criterion_label))
            g.add((act, ABI.segmentsMarket, parent))
            g.add((parent, ABI.isMarketSegmentedBy, act))
            g.add((act, ABI.appliesSegmentationCriterion, criterion))
            g.add((criterion, ABI.isSegmentationCriterionAppliedIn, act))
            for segment in segments:
                g.add((act, ABI.yieldsMarketSegment, segment))
                g.add((segment, ABI.isMarketSegmentYieldedBy, act))
            context.add_analyst(act, parameters.analyst)
            context.place(act, None, parameters.period)
            context.cite(act, parameters.source)

    def as_tools(self) -> list[BaseTool]:
        def _run(**kwargs: object) -> str:
            graph = self.run(
                MarketSegmentationPipelineParameters.model_validate(kwargs)
            )
            return f"Registered market segmentation ({len(graph)} triples)."

        return [
            StructuredTool.from_function(
                func=_run,
                name="register_market_segmentation",
                description=(
                    "Register a market and its segments (submarkets). Give each segment the "
                    "criterion it is cut along (service model, deployment model, workload, "
                    "value chain layer) and its parent markets, and cite the source."
                ),
                args_schema=MarketSegmentationPipelineParameters,
            )
        ]

    def as_api(self) -> None:
        pass
