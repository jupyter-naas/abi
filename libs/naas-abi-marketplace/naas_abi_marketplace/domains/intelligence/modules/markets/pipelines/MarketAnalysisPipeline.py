"""Act of Market Analysis pipeline: the SWOT of a market.

market + opportunities, threats (about the market)
       + strengths, weaknesses (about one competitor in that market)
  -> abi:ActOfMarketAnalysis  abi:analyzesMarket market, abi:hasParticipant analyst,
                              abi:occursIn region, abi:occupiesTemporalRegion period,
                              abi:hasMarketSource source
  -> abi:MarketOpportunity / abi:MarketThreat         abi:isFindingAboutMarket market
  -> abi:CompetitiveStrength / abi:CompetitiveWeakness abi:isFindingAboutMarket market,
                                                     abi:isFindingAboutOrganization org
"""

from __future__ import annotations

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
    digest,
    slug,
)
from pydantic import BaseModel, Field, model_validator
from rdflib import RDF, RDFS, XSD, Graph, Literal, URIRef


class OrganizationFinding(BaseModel):
    organization: str = Field(
        ..., min_length=1, description="Competitor the finding is about"
    )
    statement: str = Field(..., min_length=1, description="The finding in one sentence")


@dataclass
class MarketAnalysisPipelineConfiguration(MarketPipelineConfiguration):
    pass


class MarketAnalysisPipelineParameters(PipelineParameters):
    market: MarketParameters
    opportunities: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)
    strengths: list[OrganizationFinding] = Field(default_factory=list)
    weaknesses: list[OrganizationFinding] = Field(default_factory=list)
    analyst: str | None = Field(
        default=None, description="Organization that made the analysis"
    )
    region: str = Field(default="Global", description="Geography assessed")
    period: str | None = Field(default=None, description="When, e.g. '2026'")
    source: SourceParameters

    @model_validator(mode="after")
    def has_findings(self) -> MarketAnalysisPipelineParameters:
        if not (
            self.opportunities or self.threats or self.strengths or self.weaknesses
        ):
            raise ValueError("a market analysis needs at least one finding")
        return self


class MarketAnalysisPipeline(Pipeline):
    __configuration: MarketAnalysisPipelineConfiguration

    def __init__(self, configuration: MarketAnalysisPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: MarketAnalysisPipelineParameters) -> Graph:
        return run_in_context(self.__configuration, lambda c: self.build(c, parameters))

    @staticmethod
    def build(
        context: MarketGraphContext, parameters: MarketAnalysisPipelineParameters
    ) -> None:
        g = context.graph
        market = context.ensure_market(parameters.market)
        market_key = parameters.market.key or parameters.market.label
        act = context.act(
            "ActOfMarketAnalysis",
            slug(market_key, parameters.region, parameters.period, parameters.analyst),
            f"SWOT of {g.value(market, RDFS.label)} ({parameters.region}"
            + (f", {parameters.period}" if parameters.period else "")
            + ")",
        )
        g.add((act, ABI.analyzesMarket, market))
        g.add((market, ABI.isMarketAnalyzedBy, act))
        context.add_analyst(act, parameters.analyst)
        context.place(act, parameters.region, parameters.period)
        context.cite(act, parameters.source)

        def finding(
            class_name: str, statement: str, organization: str | None = None
        ) -> URIRef:
            uri = context.act(
                class_name,
                digest(market_key, organization, class_name, statement),
                statement,
            )
            # The store runs no reasoner: state the parent class so one pattern finds them all.
            g.add((uri, RDF.type, ABI.SWOTFinding))
            g.set((uri, ABI.finding_statement, Literal(statement, datatype=XSD.string)))
            g.add((act, ABI.hasSWOTFinding, uri))
            g.add((uri, ABI.isSWOTFindingOf, act))
            g.add((uri, ABI.isFindingAboutMarket, market))
            g.add((market, ABI.hasMarketFinding, uri))
            if organization:
                org = context.ensure_organization(organization)
                g.add((uri, ABI.isFindingAboutOrganization, org))
                g.add((org, ABI.hasOrganizationFinding, uri))
            return uri

        for statement in parameters.opportunities:
            finding("MarketOpportunity", statement)
        for statement in parameters.threats:
            finding("MarketThreat", statement)
        for item in parameters.strengths:
            finding("CompetitiveStrength", item.statement, item.organization)
        for item in parameters.weaknesses:
            finding("CompetitiveWeakness", item.statement, item.organization)

    def as_tools(self) -> list[BaseTool]:
        def _run(**kwargs: object) -> str:
            graph = self.run(MarketAnalysisPipelineParameters.model_validate(kwargs))
            return f"Registered market SWOT ({len(graph)} triples)."

        return [
            StructuredTool.from_function(
                func=_run,
                name="register_market_swot",
                description=(
                    "Register a SWOT of a market: opportunities and threats of the market, "
                    "strengths and weaknesses of named competitors in it, with the analyst, "
                    "region, period and source."
                ),
                args_schema=MarketAnalysisPipelineParameters,
            )
        ]

    def as_api(self) -> None:
        pass
