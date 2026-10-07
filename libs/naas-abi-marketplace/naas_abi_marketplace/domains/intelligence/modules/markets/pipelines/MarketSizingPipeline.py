"""Act of Market Sizing pipeline: how big a market is, according to one source.

    market + value, currency, year, region, growth, analyst, source
      -> abi:ActOfMarketSizing     abi:hasParticipant analyst, abi:realizes MarketAnalystRole,
                                   abi:occursIn region, abi:occupiesTemporalRegion year,
                                   abi:hasMarketSource source
      -> abi:MarketSizeMeasurement abi:measuresMarket market, value, currency, year, CAGR

Sources disagree because they draw the market's boundary differently; each
sizing stays its own act with its own source, and none overwrites another.
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
    slug,
)
from pydantic import Field
from rdflib import RDFS, XSD, Graph, Literal


@dataclass
class MarketSizingPipelineConfiguration(MarketPipelineConfiguration):
    pass


class MarketSizingPipelineParameters(PipelineParameters):
    market: MarketParameters
    value: Decimal = Field(
        ..., gt=0, description="Size in currency units (e.g. 723400000000, not 723.4)"
    )
    currency: str = Field(
        ..., pattern=r"^[A-Z]{3}$", description="ISO 4217 code, e.g. 'USD'"
    )
    year: int = Field(..., ge=1900, le=2100, description="Reference year of the size")
    region: str = Field(default="Global", description="Geography sized")
    growth_rate_percent: Decimal | None = Field(
        default=None, description="CAGR stated, %"
    )
    growth_period: str | None = Field(
        default=None, description="Years the CAGR covers, e.g. '2024-2030'"
    )
    analyst: str | None = Field(
        default=None, description="Organization that sized it, e.g. 'Gartner'"
    )
    source: SourceParameters


class MarketSizingPipeline(Pipeline):
    __configuration: MarketSizingPipelineConfiguration

    def __init__(self, configuration: MarketSizingPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: MarketSizingPipelineParameters) -> Graph:
        return run_in_context(self.__configuration, lambda c: self.build(c, parameters))

    @staticmethod
    def build(
        context: MarketGraphContext, parameters: MarketSizingPipelineParameters
    ) -> None:
        g = context.graph
        market = context.ensure_market(parameters.market)
        label = g.value(market, RDFS.label)
        key = (
            slug(
                parameters.market.key or parameters.market.label,
                parameters.region,
                str(parameters.year),
            )
            + "-"
            + digest(parameters.source.url or parameters.source.title)
        )

        act = context.act(
            "ActOfMarketSizing",
            key,
            f"Sizing of {label} ({parameters.region}, {parameters.year})"
            + (f" by {parameters.analyst}" if parameters.analyst else ""),
        )
        context.add_analyst(act, parameters.analyst)
        context.place(act, parameters.region, str(parameters.year))
        context.cite(act, parameters.source)

        measurement = context.act(
            "MarketSizeMeasurement",
            key,
            f"{label} size ({parameters.region}, {parameters.year}): "
            f"{parameters.currency} {parameters.value / Decimal(1_000_000_000):.1f}B",
        )
        g.add((act, ABI.hasMarketSizeMeasurement, measurement))
        g.add((measurement, ABI.isMarketSizeMeasurementOf, act))
        g.add((measurement, ABI.measuresMarket, market))
        g.add((market, ABI.isMarketMeasuredBy, measurement))
        g.set(
            (
                measurement,
                ABI.market_size_value,
                Literal(parameters.value, datatype=XSD.decimal),
            )
        )
        g.set(
            (
                measurement,
                ABI.market_size_currency,
                Literal(parameters.currency, datatype=XSD.string),
            )
        )
        g.set(
            (
                measurement,
                ABI.market_size_year,
                Literal(parameters.year, datatype=XSD.integer),
            )
        )
        if parameters.growth_rate_percent is not None:
            g.set(
                (
                    measurement,
                    ABI.market_growth_rate_percent,
                    Literal(parameters.growth_rate_percent, datatype=XSD.decimal),
                )
            )
        if parameters.growth_period:
            g.set(
                (
                    measurement,
                    ABI.market_growth_period,
                    Literal(parameters.growth_period, datatype=XSD.string),
                )
            )

    def as_tools(self) -> list[BaseTool]:
        def _run(**kwargs: object) -> str:
            graph = self.run(MarketSizingPipelineParameters.model_validate(kwargs))
            return f"Registered market size ({len(graph)} triples)."

        return [
            StructuredTool.from_function(
                func=_run,
                name="register_market_size",
                description=(
                    "Register the size of a market as one source states it: value in full "
                    "currency units, ISO currency, reference year, region, optional CAGR, "
                    "the analyst and the source."
                ),
                args_schema=MarketSizingPipelineParameters,
            )
        ]

    def as_api(self) -> None:
        pass
