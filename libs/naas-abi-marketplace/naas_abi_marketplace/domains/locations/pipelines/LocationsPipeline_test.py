import pytest
from naas_abi_core.utils.Graph import ABI
from naas_abi_marketplace.domains.locations.integrations.GeoNamesIntegration import (
    GeoNamesIntegrationConfiguration,
)
from naas_abi_marketplace.domains.locations.pipelines.LocationsPipeline import (
    LocationSource,
    LocationsPipeline,
    LocationsPipelineConfiguration,
    LocationsPipelineParameters,
)
from rdflib import RDF, RDFS


@pytest.fixture
def geonames_pipeline(tmp_path) -> LocationsPipeline:
    configuration = LocationsPipelineConfiguration(
        source=LocationSource.GEONAMES,
        geonames_integration_config=GeoNamesIntegrationConfiguration(cache_dir=str(tmp_path)),
    )
    return LocationsPipeline(configuration)


@pytest.fixture
def pgeocode_pipeline() -> LocationsPipeline:
    configuration = LocationsPipelineConfiguration(source=LocationSource.PGEOCODE)
    return LocationsPipeline(configuration)


def test_geonames_single_postal_code(geonames_pipeline: LocationsPipeline):
    graph = geonames_pipeline.run(
        LocationsPipelineParameters(country_code="LU", postal_code="L-4970")
    )

    assert len(graph) > 0
    countries = list(graph.subjects(RDF.type, ABI.Country))
    cities = list(graph.subjects(RDF.type, ABI.City))
    postal_codes = list(graph.subjects(RDF.type, ABI.PostalCode))

    assert len(countries) == 1
    assert len(cities) > 0
    assert len(postal_codes) == 1
    assert (postal_codes[0], RDFS.label, None) in graph


def test_geonames_bulk_country(geonames_pipeline: LocationsPipeline):
    graph = geonames_pipeline.run(LocationsPipelineParameters(country_code="LU"))

    postal_codes = list(graph.subjects(RDF.type, ABI.PostalCode))
    assert len(postal_codes) > 100


def test_pgeocode_single_postal_code(pgeocode_pipeline: LocationsPipeline):
    graph = pgeocode_pipeline.run(
        LocationsPipelineParameters(country_code="FR", postal_code="75001")
    )

    countries = list(graph.subjects(RDF.type, ABI.Country))
    states = list(graph.subjects(RDF.type, ABI.State))
    cities = list(graph.subjects(RDF.type, ABI.City))

    assert len(countries) == 1
    assert len(states) == 1
    assert len(cities) == 1


def test_pgeocode_requires_postal_code(pgeocode_pipeline: LocationsPipeline):
    with pytest.raises(ValueError):
        pgeocode_pipeline.run(LocationsPipelineParameters(country_code="FR"))
