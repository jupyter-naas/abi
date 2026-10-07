"""Competitors from Yahoo Finance: listed companies registered as acts of competing.

    market + tickers (symbol, optional organization label, region, period)
      -> CompanyDirectoryPort.company(symbol)         name, website, industry...
      -> <datastore_path>/<MarketFolder>/yahoofinance/<SYMBOL>.json   what was read
      -> MarketCompetitorPipeline                     abi:ActOfCompeting, cited to the
                                                       Yahoo Finance quote page, with
                                                       the organization's website and ticker

Which companies compete in a market is a curated decision: Yahoo does not file
companies by market, only by broad industry. ``industry_candidates`` lists the
industry peers of a company for review; nothing it returns is registered.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.pipeline import Pipeline, PipelineParameters
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketCompetitorPipeline import (
    CompetitorParameters,
    MarketCompetitorPipeline,
    MarketCompetitorPipelineParameters,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.utils.base import (
    MarketPipelineConfiguration,
    run_in_context,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.utils.graph_builders import (
    MarketGraphContext,
    MarketParameters,
    SourceParameters,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.utils.company_directory import (
    CompanyDirectoryPort,
    CompanyProfile,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.utils.market_storage import (
    market_folder,
)
from pydantic import BaseModel, Field
from rdflib import Graph


class TickerParameters(BaseModel):
    symbol: str = Field(
        ..., min_length=1, description="Yahoo Finance symbol, e.g. 'OVH.PA'"
    )
    organization: str | None = Field(
        default=None,
        description="Organization label to register under (default: Yahoo's company name)",
    )
    region: str = Field(default="Global", description="Geography it competes in")
    period: str | None = Field(default=None, description="When, e.g. '2026'")


@dataclass
class YahooFinanceCompetitorPipelineConfiguration(MarketPipelineConfiguration):
    directory: CompanyDirectoryPort | None = None
    object_storage: ObjectStorageService | None = None
    datastore_path: str = "intelligence/markets"


class YahooFinanceCompetitorPipelineParameters(PipelineParameters):
    market: MarketParameters
    tickers: list[TickerParameters] = Field(..., min_length=1)


def yahoo_source(
    profile: CompanyProfile, retrieved: date | None = None
) -> SourceParameters:
    return SourceParameters(
        title=f"{profile.name} ({profile.symbol}) - Yahoo Finance",
        url=profile.quote_url,
        publisher="Yahoo Finance",
        date=retrieved or datetime.now(UTC).date(),
    )


class YahooFinanceCompetitorPipeline(Pipeline):
    __configuration: YahooFinanceCompetitorPipelineConfiguration

    def __init__(self, configuration: YahooFinanceCompetitorPipelineConfiguration):
        super().__init__(configuration)
        assert configuration.directory is not None, "a CompanyDirectoryPort is required"
        self.__configuration = configuration

    def profiles(
        self, parameters: YahooFinanceCompetitorPipelineParameters
    ) -> list[CompanyProfile]:
        config = self.__configuration
        assert config.directory is not None
        profiles = [config.directory.company(t.symbol) for t in parameters.tickers]
        if config.object_storage is not None:
            prefix = f"{config.datastore_path}/{market_folder(parameters.market.label)}/yahoofinance"
            for profile in profiles:
                config.object_storage.put_object(
                    prefix,
                    f"{re.sub(r'[^A-Za-z0-9._-]', '_', profile.symbol)}.json",
                    json.dumps(profile.raw, indent=2, default=str).encode(),
                )
        return profiles

    def run(self, parameters: YahooFinanceCompetitorPipelineParameters) -> Graph:
        profiles = self.profiles(parameters)
        return run_in_context(
            self.__configuration, lambda c: self.build(c, parameters, profiles)
        )

    @staticmethod
    def build(
        context: MarketGraphContext,
        parameters: YahooFinanceCompetitorPipelineParameters,
        profiles: list[CompanyProfile],
    ) -> None:
        MarketCompetitorPipeline.build(
            context,
            MarketCompetitorPipelineParameters(
                market=parameters.market,
                competitors=[
                    CompetitorParameters(
                        organization=ticker.organization or profile.name,
                        region=ticker.region,
                        period=ticker.period,
                        website=profile.website,
                        ticker=profile.symbol,
                        source=yahoo_source(profile),
                    )
                    for ticker, profile in zip(
                        parameters.tickers, profiles, strict=True
                    )
                ],
            ),
        )

    def industry_candidates(self, symbol: str) -> list[dict]:
        """Industry peers of a listed company, for a human or the agent to review."""
        directory = self.__configuration.directory
        assert directory is not None
        profile = directory.company(symbol)
        if not profile.industry_key:
            return []
        return [
            {
                "symbol": peer.symbol,
                "name": peer.name,
                "market_weight": peer.market_weight,
                "industry": profile.industry,
            }
            for peer in directory.industry_peers(profile.industry_key)
        ]

    def as_tools(self) -> list[BaseTool]:
        def _run(**kwargs: object) -> str:
            graph = self.run(
                YahooFinanceCompetitorPipelineParameters.model_validate(kwargs)
            )
            return f"Registered competitors from Yahoo Finance ({len(graph)} triples)."

        class _Symbol(BaseModel):
            symbol: str = Field(..., description="Yahoo Finance symbol, e.g. 'OVH.PA'")

        return [
            StructuredTool.from_function(
                func=_run,
                name="register_market_competitors_from_yahoo_finance",
                description=(
                    "Register listed companies as competitors in a market from their Yahoo "
                    "Finance symbols: reads name, website and ticker, and cites the quote page."
                ),
                args_schema=YahooFinanceCompetitorPipelineParameters,
            ),
            StructuredTool.from_function(
                func=self.industry_candidates,
                name="find_yahoo_finance_industry_candidates",
                description=(
                    "List the companies Yahoo Finance files in the same industry as a listed "
                    "company. Candidates only: check each one actually sells in the market "
                    "before registering it."
                ),
                args_schema=_Symbol,
            ),
        ]

    def as_api(self) -> None:
        pass
