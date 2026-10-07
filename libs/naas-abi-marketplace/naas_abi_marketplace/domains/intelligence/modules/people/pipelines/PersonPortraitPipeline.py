"""Person portrait pipeline: an image -> object storage -> abi:Portrait in the graph.

    source (URL or local file)
      -> validated as an image (jpeg, png, webp, gif)
      -> <datastore_path>/<slug>/portraits/<slug>.<ext>       (utils/portrait_storage.py)
      -> abi:Portrait  abi:portrait_path, abi:portrait_url    (served by the module API)
         abi:Person abi:hasPortrait

The person counterpart of the organizations module's OrganizationLogoPipeline. The
Portrait individual is the one PersonProfilePipeline mints (``ensure_portrait``),
so a portrait registered here and a profile registered there describe one person.
"""

from __future__ import annotations

import mimetypes
import re
import unicodedata
from dataclasses import dataclass
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
from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.utils.graph_builders import (
    PeopleGraphContext,
)
from naas_abi_marketplace.domains.intelligence.modules.people.utils.paths import (
    module_graph_name,
)
from naas_abi_marketplace.domains.intelligence.modules.people.utils.portrait_storage import (
    extension_for,
    write_portrait,
)
from pydantic import Field, model_validator
from rdflib import Graph, URIRef

def profile_slug(first_name: str, last_name: str) -> str:
    """'Sébastien Bazin' -> 'sebastien_bazin': the form profile slugs and portrait names take."""
    folded = unicodedata.normalize("NFKD", f"{first_name} {last_name}")
    ascii_name = folded.encode("ascii", "ignore").decode().lower()
    return "_".join(re.findall(r"[a-z0-9]+", ascii_name))


HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}


@dataclass
class PersonPortraitPipelineConfiguration(PipelineConfiguration):
    object_storage: ObjectStorageService
    triple_store: TripleStoreService | None = None
    graph_name: URIRef = URIRef(module_graph_name())
    persist: bool = True
    context: PeopleGraphContext | None = None
    datastore_path: str = "intelligence/people"
    # Where the module API serves a stored portrait: <prefix>/<slug>.<ext>.
    portrait_url_prefix: str = "/api/people/portraits"
    # Prepended to the object-storage path in abi:portrait_path, e.g. "storage/datastore/"
    # for an instance that records repo-relative paths.
    portrait_path_prefix: str = ""


class PersonPortraitPipelineParameters(PipelineParameters):
    first_name: Annotated[str, Field(min_length=1)]
    last_name: Annotated[str, Field(min_length=1)]
    slug: str | None = Field(
        default=None, description="Profile slug, e.g. 'alice_dupont' (default: from the name)"
    )
    source_url: str | None = Field(default=None, description="URL to download the portrait from")
    source_path: str | None = Field(default=None, description="Local portrait file")

    @model_validator(mode="after")
    def one_source(self) -> PersonPortraitPipelineParameters:
        if (self.source_url is None) == (self.source_path is None):
            raise ValueError("give exactly one of source_url or source_path")
        return self


class PersonPortraitPipeline(Pipeline):
    __configuration: PersonPortraitPipelineConfiguration

    def __init__(self, configuration: PersonPortraitPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    @staticmethod
    def fetch(parameters: PersonPortraitPipelineParameters) -> tuple[bytes, str]:
        """``(content, extension)`` of the source, refusing anything that is not an image."""
        if parameters.source_path is not None:
            path = Path(parameters.source_path)
            media_type = mimetypes.guess_type(path.name)[0] or ""
            return path.read_bytes(), extension_for(media_type)
        assert parameters.source_url is not None
        response = requests.get(parameters.source_url, headers=HEADERS, timeout=60)
        response.raise_for_status()
        return response.content, extension_for(response.headers.get("Content-Type", ""))

    def run(self, parameters: PersonPortraitPipelineParameters) -> Graph:
        config = self.__configuration
        content, extension = self.fetch(parameters)
        person_slug = parameters.slug or profile_slug(
            parameters.first_name, parameters.last_name
        )
        storage_path = write_portrait(
            config.object_storage, config.datastore_path, person_slug, content, extension
        )
        name = storage_path.rsplit("/", 1)[-1]

        owned_context = config.context is None
        context = config.context or PeopleGraphContext()
        before = len(context.graph)
        person = context.ensure_person(parameters.first_name, parameters.last_name)
        context.ensure_portrait(
            person,
            url=f"{config.portrait_url_prefix}/{quote(name)}",
            path=f"{config.portrait_path_prefix}{storage_path}",
        )
        delta = Graph()
        for triple in list(context.graph)[before:]:
            delta.add(triple)
        if config.persist and config.triple_store is not None and len(delta) > 0:
            config.triple_store.insert(delta, graph_name=config.graph_name)
        return context.graph if owned_context else delta

    def as_tools(self) -> list[BaseTool]:
        def _run(**kwargs: object) -> str:
            graph = self.run(PersonPortraitPipelineParameters.model_validate(kwargs))
            return f"Registered person portrait ({len(graph)} triples)."

        return [
            StructuredTool.from_function(
                func=_run,
                name="register_person_portrait",
                description=(
                    "Store a person's portrait (from a URL or a local file) and "
                    "register it in the graph."
                ),
                args_schema=PersonPortraitPipelineParameters,
            )
        ]

    def as_api(self) -> None:
        pass
