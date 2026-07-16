from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.utils.Graph import ABI, BFO, CCO, ABIGraph
from naas_abi_marketplace.domains.locations.integrations.GeoNamesIntegration import (
    GeoNamesIntegration,
    GeoNamesIntegrationConfiguration,
)
from naas_abi_marketplace.domains.locations.integrations.PgeocodeIntegration import (
    PgeocodeIntegration,
    PgeocodeIntegrationConfiguration,
)
from pydantic import Field
from rdflib import XSD, Graph, Literal


class LocationSource(str, Enum):
    GEONAMES = "geonames"
    PGEOCODE = "pgeocode"


@dataclass
class LocationsPipelineConfiguration(PipelineConfiguration):
    """Configuration for LocationsPipeline.

    Attributes:
        source: Which integration to fetch location records from. "geonames"
            covers every country that publishes postal codes and can also
            bulk-load a whole country. "pgeocode" is a faster offline lookup
            limited to ~83 countries and always requires a postal_code.
        geonames_integration_config: Configuration forwarded to GeoNamesIntegration.
        pgeocode_integration_config: Configuration forwarded to PgeocodeIntegration.
    """

    source: LocationSource = LocationSource.GEONAMES
    geonames_integration_config: GeoNamesIntegrationConfiguration = field(
        default_factory=GeoNamesIntegrationConfiguration
    )
    pgeocode_integration_config: PgeocodeIntegrationConfiguration = field(
        default_factory=PgeocodeIntegrationConfiguration
    )


class LocationsPipelineParameters(PipelineParameters):
    """Parameters for LocationsPipeline."""

    country_code: str = Field(..., description="ISO-3166 alpha-2 country code, e.g. 'FR'.")
    postal_code: Optional[str] = Field(
        default=None,
        description="Postal code to add to the knowledge graph. Required when source "
        "is 'pgeocode'. Omit with source 'geonames' to add every postal code of the country.",
    )


class LocationsPipeline(Pipeline):
    """Pipeline that adds city/region/state/country/postal_code location records to the ontology."""

    __configuration: LocationsPipelineConfiguration

    def __init__(self, configuration: LocationsPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__geonames = GeoNamesIntegration(configuration.geonames_integration_config)
        self.__pgeocode = PgeocodeIntegration(configuration.pgeocode_integration_config)

    def __fetch_records(self, country_code: str, postal_code: Optional[str]) -> list[dict]:
        if self.__configuration.source == LocationSource.PGEOCODE:
            if not postal_code:
                raise ValueError("postal_code is required when source is 'pgeocode'")
            return self.__pgeocode.query_postal_code(country_code, postal_code)

        if postal_code:
            return self.__geonames.search_postal_code(country_code, postal_code)
        return self.__geonames.get_postal_codes(country_code)

    def __add_record(self, graph: ABIGraph, record: dict) -> None:
        country_code = record["country_code"]

        location = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=country_code,
            label=country_code,
            is_a=ABI.Country,
            country_code=country_code,
        )

        if record.get("state"):
            state = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=f"{country_code}_{record['state']}",
                label=record["state"],
                is_a=ABI.State,
            )
            graph.add((state, BFO.BFO_0000171, location))
            location = state

        if record.get("region"):
            region = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=f"{country_code}_{record.get('state', '')}_{record['region']}",
                label=record["region"],
                is_a=ABI.Region,
            )
            graph.add((region, BFO.BFO_0000171, location))
            location = region

        city = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=f"{country_code}_{record['postal_code']}_{record['city']}",
            label=record["city"],
            is_a=ABI.City,
        )
        graph.add((city, BFO.BFO_0000171, location))
        if record.get("latitude") is not None:
            graph.add((city, CCO.ont00001766, Literal(record["latitude"], datatype=XSD.decimal)))
        if record.get("longitude") is not None:
            graph.add((city, CCO.ont00001764, Literal(record["longitude"], datatype=XSD.decimal)))

        postal_code_individual = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=f"{country_code}_{record['postal_code']}",
            label=record["postal_code"],
            is_a=ABI.PostalCode,
        )
        graph.add((postal_code_individual, BFO.BFO_0000171, city))

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, LocationsPipelineParameters):
            raise ValueError("Parameters must be of type LocationsPipelineParameters")

        records = self.__fetch_records(parameters.country_code, parameters.postal_code)
        if not records:
            raise ValueError(
                f"No location found for country_code={parameters.country_code!r} "
                f"postal_code={parameters.postal_code!r}"
            )

        graph = ABIGraph()
        for record in records:
            self.__add_record(graph, record)
        return graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="add_locations_to_graph",
                description="Add city/region/state/country/postal_code location records to the knowledge graph",
                func=lambda **kwargs: self.run(LocationsPipelineParameters(**kwargs)),
                args_schema=LocationsPipelineParameters,
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None
