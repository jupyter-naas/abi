"""Act of Competing pipeline: the organizations that compete in a market.

    market + competitors (organization, region, period, share, rank, source)
      -> abi:ActOfCompeting   abi:hasCompetitor org, abi:isInMarket market,
                              abi:occursIn region, abi:occupiesTemporalRegion period,
                              abi:realizes abi:CompetitorRole, abi:hasMarketSource source
      -> abi:MarketShareMeasurement when a share or a rank is stated
      -> abi:Organization abi:hasMarket market (the one-hop shortcut)

Competitors are never linked to each other: two organizations compete when they
have acts of competing in the same market. One act per (organization, market,
region): registering it again with a newer source adds the source, it does not
duplicate the act.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

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
    digest,
    individual_uri,
    slug,
)
from pydantic import BaseModel, Field
from rdflib import RDFS, XSD, Graph, Literal, URIRef


class CompetitorParameters(BaseModel):
    organization: str = Field(
        ..., min_length=1, description="Organization label, e.g. 'OVHcloud'"
    )
    region: str = Field(default="Global", description="Geography it competes in")
    period: str | None = Field(
        default=None, description="When, e.g. '2026' or 'Q3 2025'"
    )
    share_percent: Decimal | None = Field(
        default=None, ge=0, le=100, description="Market share, %"
    )
    rank: int | None = Field(default=None, ge=1, description="Rank by market share")
    website: str | None = Field(default=None, description="Organization website URL")
    ticker: str | None = Field(default=None, description="Stock ticker, e.g. 'OVH.PA'")
    source: SourceParameters | None = Field(
        default=None, description="Where this is stated (default: the batch source)"
    )


@dataclass
class MarketCompetitorPipelineConfiguration(MarketPipelineConfiguration):
    pass


class MarketCompetitorPipelineParameters(PipelineParameters):
    market: MarketParameters
    competitors: list[CompetitorParameters] = Field(..., min_length=1)
    source: SourceParameters | None = Field(
        default=None,
        description="Source for every competitor that does not cite its own",
    )


def act_of_competing_uri(organization: str, market_key: str, region: str) -> URIRef:
    return individual_uri("ActOfCompeting", slug(organization, market_key, region))


class MarketCompetitorPipeline(Pipeline):
    __configuration: MarketCompetitorPipelineConfiguration

    def __init__(self, configuration: MarketCompetitorPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: MarketCompetitorPipelineParameters) -> Graph:
        for competitor in parameters.competitors:
            if competitor.source is None and parameters.source is None:
                raise ValueError(
                    f"no source for competitor '{competitor.organization}'"
                )
        return run_in_context(self.__configuration, lambda c: self.build(c, parameters))

    @staticmethod
    def build(
        context: MarketGraphContext, parameters: MarketCompetitorPipelineParameters
    ) -> None:
        g = context.graph
        market = context.ensure_market(parameters.market)
        market_key = parameters.market.key or parameters.market.label
        market_label = g.value(market, RDFS.label)
        for competitor in parameters.competitors:
            source = competitor.source or parameters.source
            assert source is not None
            org = context.ensure_organization(competitor.organization)
            if competitor.website:
                context.set_website(org, competitor.organization, competitor.website)
            if competitor.ticker:
                context.set_ticker(org, competitor.ticker)

            act = context.act(
                "ActOfCompeting",
                slug(competitor.organization, market_key, competitor.region),
                f"{competitor.organization} competing in {market_label} ({competitor.region})",
            )
            g.add((act, ABI.hasCompetitor, org))
            g.add((org, ABI.isCompetitorIn, act))
            g.add((act, ABI.isInMarket, market))
            g.add((market, ABI.hasActOfCompeting, act))
            g.add((org, ABI.hasMarket, market))
            g.add((market, ABI.isMarketOf, org))

            role = context._individual(
                individual_uri(
                    "CompetitorRole", slug(competitor.organization, market_key)
                ),
                ABI.CompetitorRole,
                f"Competitor role of {competitor.organization} in {market_label}",
            )
            g.add((role, ABI.inheresIn, org))
            g.add((org, ABI.bearerOf, role))
            g.add((act, ABI.realizes, role))
            g.add((role, ABI.hasRealization, act))

            context.place(act, competitor.region, competitor.period)
            context.cite(act, source)

            if competitor.share_percent is not None or competitor.rank is not None:
                measurement = context._individual(
                    individual_uri(
                        "MarketShareMeasurement",
                        slug(competitor.organization, market_key, competitor.region)
                        + "-"
                        + digest(competitor.period, source.url or source.title),
                    ),
                    ABI.MarketShareMeasurement,
                    f"Market share of {competitor.organization} in {market_label}"
                    + (f" ({competitor.period})" if competitor.period else ""),
                )
                g.add((act, ABI.hasMarketShareMeasurement, measurement))
                g.add((measurement, ABI.isMarketShareMeasurementOf, act))
                if competitor.share_percent is not None:
                    g.set(
                        (
                            measurement,
                            ABI.market_share_percent,
                            Literal(competitor.share_percent, datatype=XSD.decimal),
                        )
                    )
                if competitor.rank is not None:
                    g.set(
                        (
                            measurement,
                            ABI.market_rank,
                            Literal(competitor.rank, datatype=XSD.integer),
                        )
                    )

    def as_tools(self) -> list[BaseTool]:
        def _run(**kwargs: object) -> str:
            graph = self.run(MarketCompetitorPipelineParameters.model_validate(kwargs))
            return f"Registered market competitors ({len(graph)} triples)."

        return [
            StructuredTool.from_function(
                func=_run,
                name="register_market_competitors",
                description=(
                    "Register organizations competing in a market or market segment, with "
                    "the region and period, optional market share and rank, and the source "
                    "that states it."
                ),
                args_schema=MarketCompetitorPipelineParameters,
            )
        ]

    def as_api(self) -> None:
        pass
