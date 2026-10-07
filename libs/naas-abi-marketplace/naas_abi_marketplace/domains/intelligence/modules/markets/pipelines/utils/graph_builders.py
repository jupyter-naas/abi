"""Shared RDF builders for the markets process pipelines.

Every individual gets a deterministic IRI, so running a pipeline twice on the
same input writes the same triples and the triple store holds them once.
Organizations are minted exactly as the people and organizations modules mint
them (``abi:Organization/<slug of the label>``): a competitor lands on the same
individual as the employer in someone's act of working and the owner of a logo.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from rdflib import OWL, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS

ABI = Namespace("http://ontology.naas.ai/abi/")
DEFAULT_GRAPH_NAME = "http://ontology.naas.ai/graph/markets"


def slug(*parts: str | None) -> str:
    """Same rule as the people and organizations pipelines' ``slug``."""
    joined = "-".join(p.strip().lower() for p in parts if p and str(p).strip())
    return re.sub(r"[^a-z0-9_\-]+", "-", joined).strip("-") or "unknown"


def individual_uri(class_name: str, key: str) -> URIRef:
    return URIRef(f"{ABI}{class_name}/{re.sub(r'[^A-Za-z0-9_-]', '_', key)}")


def organization_uri(label: str) -> URIRef:
    return individual_uri("Organization", slug(label))


def market_uri(key_or_label: str) -> URIRef:
    return individual_uri("Market", slug(key_or_label))


def digest(*parts: str | None) -> str:
    return hashlib.sha1("|".join(p or "" for p in parts).encode()).hexdigest()[:12]


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class SourceParameters(BaseModel):
    """Where a market statement was read from."""

    title: str = Field(..., min_length=1, description="Title of the document")
    url: str | None = Field(default=None, description="Address of the document")
    publisher: str | None = Field(default=None, description="Who published it")
    date: dt.date | None = Field(
        default=None, description="Publication or retrieval date"
    )


class MarketParameters(BaseModel):
    """A market, addressed by its key (default: slug of its label)."""

    label: str = Field(
        ..., min_length=1, description="Market name, e.g. 'Cloud Computing'"
    )
    key: str | None = Field(
        default=None, description="Stable key (default: slug of the label)"
    )
    definition: str | None = Field(default=None, description="What the market covers")

    @property
    def uri(self) -> URIRef:
        return market_uri(self.key or self.label)


@dataclass
class MarketGraphContext:
    """Builder state shared by the pipelines of one batch."""

    graph: Graph = field(default_factory=Graph)
    creator: str = "markets_pipeline"
    _seen: set[URIRef] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.graph.bind("abi", ABI)

    def _individual(self, uri: URIRef, class_uri: URIRef, label: str) -> URIRef:
        self.graph.add((uri, RDF.type, OWL.NamedIndividual))
        self.graph.add((uri, RDF.type, class_uri))
        if uri not in self._seen:
            self._seen.add(uri)
            self.graph.set((uri, RDFS.label, Literal(label)))
            self.graph.set((uri, DCTERMS.creator, Literal(self.creator)))
            self.graph.set(
                (uri, DCTERMS.created, Literal(utc_now(), datatype=XSD.dateTime))
            )
        return uri

    # --- WHO -------------------------------------------------------------

    def ensure_organization(self, label: str) -> URIRef:
        return self._individual(organization_uri(label), ABI.Organization, label)

    def set_website(self, organization: URIRef, label: str, url: str) -> URIRef:
        website = self._individual(
            individual_uri("Website", slug(label)), ABI.Website, f"Website - {label}"
        )
        self.graph.set((website, ABI.website_url, Literal(url, datatype=XSD.string)))
        self.graph.add((organization, ABI.hasWebsite, website))
        self.graph.add((website, ABI.isWebsiteOf, organization))
        return website

    def set_ticker(self, organization: URIRef, symbol: str) -> URIRef:
        ticker = self._individual(individual_uri("Ticker", symbol), ABI.Ticker, symbol)
        self.graph.set(
            (ticker, ABI.ticker_symbol, Literal(symbol, datatype=XSD.string))
        )
        self.graph.add((organization, ABI.hasTickerSymbol, ticker))
        self.graph.add((ticker, ABI.isTickerSymbolOf, organization))
        return ticker

    # --- WHERE / WHEN ----------------------------------------------------

    def ensure_region(self, label: str) -> URIRef:
        return self._individual(
            individual_uri("GeospatialRegion", slug(label)), ABI.GeospatialRegion, label
        )

    def ensure_period(self, label: str) -> URIRef:
        return self._individual(
            individual_uri("TemporalRegion", slug(label)), ABI.TemporalRegion, label
        )

    # --- WHY -------------------------------------------------------------

    def ensure_analyst_role(self, organization_label: str) -> URIRef:
        org = self.ensure_organization(organization_label)
        role = self._individual(
            individual_uri("MarketAnalystRole", slug(organization_label)),
            ABI.MarketAnalystRole,
            f"Market analyst role of {organization_label}",
        )
        self.graph.add((role, ABI.inheresIn, org))
        self.graph.add((org, ABI.bearerOf, role))
        return role

    def add_analyst(self, act: URIRef, organization_label: str | None) -> None:
        """WHO + WHY of an act an analyst performs (segmenting, sizing, assessing)."""
        if not organization_label:
            return
        org = self.ensure_organization(organization_label)
        role = self.ensure_analyst_role(organization_label)
        self.graph.add((act, ABI.hasParticipant, org))
        self.graph.add((org, ABI.participatesIn, act))
        self.graph.add((act, ABI.realizes, role))
        self.graph.add((role, ABI.hasRealization, act))

    # --- HOW WE KNOW -----------------------------------------------------

    def ensure_market(
        self, market: MarketParameters, *, segment: bool = False
    ) -> URIRef:
        uri = self._individual(
            market.uri, ABI.MarketSegment if segment else ABI.Market, market.label
        )
        if segment:
            self.graph.add((uri, RDF.type, ABI.Market))
        if market.definition:
            self.graph.set(
                (
                    uri,
                    ABI.market_definition,
                    Literal(market.definition, datatype=XSD.string),
                )
            )
        return uri

    def ensure_source(self, source: SourceParameters) -> URIRef:
        uri = self._individual(
            individual_uri("MarketSource", digest(source.url or source.title)),
            ABI.MarketSource,
            source.title,
        )
        if source.url:
            self.graph.set(
                (uri, ABI.market_source_url, Literal(source.url, datatype=XSD.anyURI))
            )
        if source.publisher:
            self.graph.set(
                (
                    uri,
                    ABI.market_source_publisher,
                    Literal(source.publisher, datatype=XSD.string),
                )
            )
        if source.date:
            self.graph.set(
                (uri, ABI.market_source_date, Literal(source.date, datatype=XSD.date))
            )
        return uri

    def cite(self, act: URIRef, source: SourceParameters) -> URIRef:
        uri = self.ensure_source(source)
        self.graph.add((act, ABI.hasMarketSource, uri))
        self.graph.add((uri, ABI.isMarketSourceOf, act))
        return uri

    def act(self, class_name: str, key: str, label: str) -> URIRef:
        return self._individual(individual_uri(class_name, key), ABI[class_name], label)

    def place(self, act: URIRef, region: str | None, period: str | None) -> None:
        """WHERE + WHEN of an act."""
        if region:
            self.graph.add((act, ABI.occursIn, self.ensure_region(region)))
        if period:
            self.graph.add(
                (act, ABI.occupiesTemporalRegion, self.ensure_period(period))
            )
