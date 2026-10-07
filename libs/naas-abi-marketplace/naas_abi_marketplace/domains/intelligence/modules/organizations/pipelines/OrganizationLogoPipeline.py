"""Organization logo pipeline: an image -> object storage -> abi:Logo in the graph.

    source (URL or local file)
      -> validated as an image
      -> <datastore_path>/<key>/logos/<key>.<ext>            (utils/logo_storage.py)
      -> abi:Logo  abi:logo_storage_path, abi:logo_url        (served by the module API)
         abi:Organization abi:hasLogo / abi:isLogoOf

The organization counterpart of a person's portrait. The organization is addressed
the way the people pipelines mint it (``abi:Organization/<slug of its label>``), so a
logo lands on the same individual the acts of working point at; pass
``organization_uri`` to attach it to another one.
"""

from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

import requests
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService
from naas_abi_marketplace.domains.intelligence.modules.organizations.utils.logo_storage import (
    extension_for,
    write_logo,
)
from pydantic import Field, model_validator
from rdflib import OWL, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS

ABI = Namespace("http://ontology.naas.ai/abi/")
# Several logo hosts refuse requests that do not look like a browser.
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}


def slug(label: str) -> str:
    """Same rule as the people pipelines' ``slug``: their organizations and ours meet."""
    return re.sub(r"[^a-z0-9_\-]+", "-", label.strip().lower()).strip("-") or "unknown"


def organization_uri(label: str) -> URIRef:
    return URIRef(f"{ABI}Organization/{re.sub(r'[^A-Za-z0-9_-]', '_', slug(label))}")


@dataclass
class OrganizationLogoPipelineConfiguration(PipelineConfiguration):
    object_storage: ObjectStorageService
    triple_store: TripleStoreService | None = None
    graph_name: URIRef = URIRef("http://ontology.naas.ai/graph/organizations")
    persist: bool = True
    datastore_path: str = "intelligence/organizations"
    # Where the module API serves a stored logo: <prefix>/<key>/<key>.<ext>.
    logo_url_prefix: str = "/api/organizations/logos"
    creator: str = "OrganizationLogoPipeline"


class OrganizationLogoPipelineParameters(PipelineParameters):
    organization: Annotated[str, Field(min_length=1, description="Organization label")]
    organization_key: str | None = Field(
        default=None,
        description="Folder of the organization in the datastore (default: slug of the label)",
    )
    organization_uri: str | None = Field(
        default=None, description="Organization IRI (default: minted from the label)"
    )
    source_url: str | None = Field(default=None, description="URL to download the logo from")
    source_path: str | None = Field(default=None, description="Local logo file")

    @model_validator(mode="after")
    def one_source(self) -> OrganizationLogoPipelineParameters:
        if (self.source_url is None) == (self.source_path is None):
            raise ValueError("give exactly one of source_url or source_path")
        return self


class OrganizationLogoPipeline(Pipeline):
    __configuration: OrganizationLogoPipelineConfiguration

    def __init__(self, configuration: OrganizationLogoPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    @staticmethod
    def fetch(parameters: OrganizationLogoPipelineParameters) -> tuple[bytes, str]:
        """``(content, extension)`` of the source, refusing anything that is not an image."""
        if parameters.source_path is not None:
            path = Path(parameters.source_path)
            media_type = mimetypes.guess_type(path.name)[0] or ""
            return path.read_bytes(), extension_for(media_type)
        assert parameters.source_url is not None
        response = requests.get(parameters.source_url, headers=HEADERS, timeout=60)
        response.raise_for_status()
        return response.content, extension_for(response.headers.get("Content-Type", ""))

    def run(self, parameters: OrganizationLogoPipelineParameters) -> Graph:
        config = self.__configuration
        content, extension = self.fetch(parameters)
        key = parameters.organization_key or slug(parameters.organization)
        storage_path = write_logo(
            config.object_storage, config.datastore_path, key, content, extension
        )
        name = storage_path.rsplit("/", 1)[-1]

        org = (
            URIRef(parameters.organization_uri)
            if parameters.organization_uri
            else organization_uri(parameters.organization)
        )
        logo = URIRef(f"{ABI}Logo/{re.sub(r'[^A-Za-z0-9_-]', '_', key)}")
        graph = Graph()
        graph.bind("abi", ABI)
        graph.add((logo, RDF.type, OWL.NamedIndividual))
        graph.add((logo, RDF.type, ABI.Logo))
        graph.add((logo, RDFS.label, Literal(f"Logo - {parameters.organization}")))
        graph.add((logo, ABI.logo_storage_path, Literal(storage_path, datatype=XSD.string)))
        graph.add(
            (
                logo,
                ABI.logo_url,
                Literal(
                    f"{config.logo_url_prefix}/{quote(key)}/{quote(name)}",
                    datatype=XSD.anyURI,
                ),
            )
        )
        graph.add((logo, ABI.isLogoOf, org))
        graph.add((org, ABI.hasLogo, logo))
        graph.add(
            (
                logo,
                DCTERMS.created,
                Literal(datetime.now(UTC).replace(tzinfo=None), datatype=XSD.dateTime),
            )
        )
        graph.add((logo, DCTERMS.creator, Literal(config.creator)))

        if config.persist and config.triple_store is not None:
            config.triple_store.insert(graph, graph_name=config.graph_name)
        return graph

    def as_tools(self) -> list[BaseTool]:
        def _run(**kwargs: object) -> str:
            graph = self.run(OrganizationLogoPipelineParameters.model_validate(kwargs))
            return f"Registered organization logo ({len(graph)} triples)."

        return [
            StructuredTool.from_function(
                func=_run,
                name="register_organization_logo",
                description=(
                    "Store an organization's logo (from a URL or a local file) and "
                    "register it in the graph."
                ),
                args_schema=OrganizationLogoPipelineParameters,
            )
        ]

    def as_api(self) -> None:
        pass
