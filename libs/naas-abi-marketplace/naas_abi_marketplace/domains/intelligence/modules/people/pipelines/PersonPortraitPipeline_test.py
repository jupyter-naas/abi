"""Tests for PersonPortraitPipeline and the portrait storage it writes through."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi_core.services.object_storage.ObjectStorageFactory import (
    ObjectStorageFactory,
)
from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.PersonPortraitPipeline import (
    PersonPortraitPipeline,
    PersonPortraitPipelineConfiguration,
    PersonPortraitPipelineParameters,
    profile_slug,
)
from naas_abi_marketplace.domains.intelligence.modules.people.utils.portrait_routes import (
    mount_portrait_route,
)
from naas_abi_marketplace.domains.intelligence.modules.people.utils.portrait_storage import (
    InvalidPortraitError,
    read_portrait,
)
from rdflib import Namespace, URIRef

ABI = Namespace("http://ontology.naas.ai/abi/")
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16


@pytest.fixture
def storage(tmp_path: Path):
    return ObjectStorageFactory.ObjectStorageServiceFS(str(tmp_path / "datastore"))


def pipeline(storage, **overrides) -> PersonPortraitPipeline:
    return PersonPortraitPipeline(
        PersonPortraitPipelineConfiguration(object_storage=storage, persist=False, **overrides)
    )


def image(tmp_path: Path, name: str, content: bytes = JPEG) -> str:
    path = tmp_path / name
    path.write_bytes(content)
    return str(path)


def test_portrait_is_stored_under_the_person_and_registered(storage, tmp_path: Path) -> None:
    graph = pipeline(storage, portrait_path_prefix="storage/datastore/").run(
        PersonPortraitPipelineParameters(
            first_name="Sébastien", last_name="Bazin", source_path=image(tmp_path, "p.jpg")
        )
    )

    assert read_portrait(storage, "intelligence/people", "sebastien_bazin.jpeg") == (
        JPEG,
        "image/jpeg",
    )
    person = URIRef(f"{ABI}Person/s-bastien-bazin")
    portrait = graph.value(person, ABI.hasPortrait)
    assert portrait is not None
    assert str(graph.value(portrait, ABI.portrait_url)) == (
        "/api/people/portraits/sebastien_bazin.jpeg"
    )
    assert str(graph.value(portrait, ABI.portrait_path)) == (
        "storage/datastore/intelligence/people/sebastien_bazin/portraits/sebastien_bazin.jpeg"
    )


def test_profile_slug_folds_accents() -> None:
    assert profile_slug("Gilda", "Perez-Alvarado") == "gilda_perez_alvarado"
    assert profile_slug("Bénédicte", "de Bonnechose") == "benedicte_de_bonnechose"


def test_a_new_format_replaces_the_previous_portrait(storage, tmp_path: Path) -> None:
    run = pipeline(storage).run
    for name in ("a.jpg", "b.png"):
        run(
            PersonPortraitPipelineParameters(
                first_name="Alice", last_name="Dupont", source_path=image(tmp_path, name)
            )
        )

    assert storage.list_objects("intelligence/people/alice_dupont/portraits") == [
        "intelligence/people/alice_dupont/portraits/alice_dupont.png"
    ]


def test_content_that_is_not_an_image_is_refused(storage, tmp_path: Path) -> None:
    with pytest.raises(InvalidPortraitError):
        pipeline(storage).run(
            PersonPortraitPipelineParameters(
                first_name="Alice",
                last_name="Dupont",
                source_path=image(tmp_path, "page.html", b"<html>"),
            )
        )


def test_the_api_serves_a_stored_portrait(storage, tmp_path: Path) -> None:
    pipeline(storage).run(
        PersonPortraitPipelineParameters(
            first_name="Alice", last_name="Dupont", source_path=image(tmp_path, "a.jpg")
        )
    )
    app = FastAPI()
    mount_portrait_route(app, lambda: storage, "intelligence/people")
    client = TestClient(app)

    response = client.get("/api/people/portraits/alice_dupont.jpeg")
    assert response.status_code == 200
    assert response.content == JPEG
    assert client.get("/api/people/portraits/bob_martin.jpeg").status_code == 404
    assert client.get("/api/people/portraits/..%2Fx.jpeg").status_code == 404
