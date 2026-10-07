"""Tests for OrganizationLogoPipeline and the logo storage it writes through."""

from __future__ import annotations

from pathlib import Path

import pytest
from naas_abi_core.services.object_storage.ObjectStorageFactory import (
    ObjectStorageFactory,
)
from naas_abi_marketplace.domains.intelligence.modules.organizations.pipelines.OrganizationLogoPipeline import (
    ABI,
    OrganizationLogoPipeline,
    OrganizationLogoPipelineConfiguration,
    OrganizationLogoPipelineParameters,
    organization_uri,
)
from naas_abi_marketplace.domains.intelligence.modules.organizations.utils.logo_storage import (
    InvalidLogoError,
    read_logo,
)
from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.utils.graph_builders import (
    PeopleGraphContext,
)
from pydantic import ValidationError
from rdflib import RDF, URIRef

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture
def storage(tmp_path: Path):
    return ObjectStorageFactory.ObjectStorageServiceFS(str(tmp_path / "datastore"))


def pipeline(storage) -> OrganizationLogoPipeline:
    return OrganizationLogoPipeline(
        OrganizationLogoPipelineConfiguration(object_storage=storage, persist=False)
    )


def logo_file(tmp_path: Path, name: str, content: bytes = PNG) -> str:
    path = tmp_path / name
    path.write_bytes(content)
    return str(path)


def test_logo_is_stored_under_the_organization_and_registered(
    storage, tmp_path: Path
) -> None:
    graph = pipeline(storage).run(
        OrganizationLogoPipelineParameters(
            organization="Accor",
            organization_key="Accor",
            source_path=logo_file(tmp_path, "accor.png"),
        )
    )

    assert read_logo(storage, "intelligence/organizations", "Accor", "Accor.png") == (
        PNG,
        "image/png",
    )
    logo = URIRef(f"{ABI}Logo/Accor")
    assert (logo, RDF.type, ABI.Logo) in graph
    assert (organization_uri("Accor"), ABI.hasLogo, logo) in graph
    assert str(graph.value(logo, ABI.logo_url)) == "/api/organizations/logos/Accor/Accor.png"
    assert (
        str(graph.value(logo, ABI.logo_storage_path))
        == "intelligence/organizations/Accor/logos/Accor.png"
    )


def test_a_new_format_replaces_the_previous_logo(storage, tmp_path: Path) -> None:
    run = pipeline(storage).run
    run(
        OrganizationLogoPipelineParameters(
            organization="EDF", organization_key="EDF", source_path=logo_file(tmp_path, "a.png")
        )
    )
    run(
        OrganizationLogoPipelineParameters(
            organization="EDF",
            organization_key="EDF",
            source_path=logo_file(tmp_path, "b.svg", b"<svg/>"),
        )
    )

    assert storage.list_objects("intelligence/organizations/EDF/logos") == [
        "intelligence/organizations/EDF/logos/EDF.svg"
    ]
    assert read_logo(storage, "intelligence/organizations", "EDF", "EDF.png") is None


def test_content_that_is_not_an_image_is_refused(storage, tmp_path: Path) -> None:
    with pytest.raises(InvalidLogoError):
        pipeline(storage).run(
            OrganizationLogoPipelineParameters(
                organization="EDF", source_path=logo_file(tmp_path, "page.html", b"<html>")
            )
        )


def test_exactly_one_source_is_required() -> None:
    with pytest.raises(ValidationError):
        OrganizationLogoPipelineParameters(organization="EDF")


def test_organization_is_the_one_the_people_pipelines_mint() -> None:
    for label in ("Accor", "Crédit Mutuel Alliance Fédérale", "L'Oréal"):
        assert organization_uri(label) == URIRef(PeopleGraphContext().ensure_org(label)._uri)


def test_read_logo_refuses_names_outside_the_organization(storage) -> None:
    assert read_logo(storage, "intelligence/organizations", "Accor", "../x.png") is None
    assert read_logo(storage, "intelligence/organizations", "..", "...png") is None


def test_the_api_serves_a_stored_logo(storage, tmp_path: Path) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from naas_abi_marketplace.domains.intelligence.modules.organizations.utils.logo_routes import (
        mount_logo_route,
    )

    graph = pipeline(storage).run(
        OrganizationLogoPipelineParameters(
            organization="Wolters Kluwer",
            organization_key="Wolters Kluwer",
            source_path=logo_file(tmp_path, "wk.png"),
        )
    )
    app = FastAPI()
    mount_logo_route(app, lambda: storage, "intelligence/organizations")
    client = TestClient(app)

    url = str(graph.value(URIRef(f"{ABI}Logo/Wolters_Kluwer"), ABI.logo_url))
    response = client.get(url)
    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["content-type"] == "image/png"
    assert client.get("/api/organizations/logos/Accor/Accor.png").status_code == 404
