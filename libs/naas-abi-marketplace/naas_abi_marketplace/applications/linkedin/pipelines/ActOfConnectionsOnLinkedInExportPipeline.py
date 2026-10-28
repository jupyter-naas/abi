"""The acts of connection stated by one LinkedIn ``Connections.csv``.

One row is one connection of the export owner. It becomes:

- the connection, an ``abi:Person`` keyed on their LinkedIn profile URL, so the
  same profile in a re-import, a newer export or a colleague's export is the
  same node; a URL already known to the people graphs reuses that person;
- one ``linkedin:ActOfConnection`` between the owner and the connection, dated
  from ``Connected On`` and sourced from the export file;
- one ``abi:ActOfWorking`` from ``Company`` and ``Position``, built by the people
  module exactly as the corporate-website import builds its acts of working.

The pipeline builds a graph and does not decide where it goes: it writes to the
triple store only when the configuration names both a store and a graph, and
never to the default graph.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Annotated
from urllib.parse import unquote, urlsplit

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_marketplace.applications.linkedin.ontologies.modules.ActOfConnectionsOnLinkedIn import (
    ActOfConnection,
    ConnectionRole,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.export_people_from_graph import (
    PrivacyError,
    check_privacy,
)
from naas_abi_marketplace.domains.intelligence.modules.people.ontologies.modules.PeopleOntology import (
    ProfileDocument,
)
from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.utils.graph_builders import (
    ABI,
    PeopleGraphContext,
    bind_graph_prefixes,
    individual_uri,
    utc_now,
)
from pydantic import BaseModel, Field
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

LINKEDIN = Namespace("http://ontology.naas.ai/abi/linkedin/")
CREATOR = "linkedin_connections_export"

# The People app addresses a person by profile_slug, which must match
# ^[a-z0-9][a-z0-9_-]{0,63}$ (people app, scripts/profile_payload.py).
_SLUG_MAX = 64
_VANITY = re.compile(r"^/(?:in|pub)/([^/?#]+)", re.IGNORECASE)
# The shape the People app holds person.email to (export_people_from_graph,
# CONTACT_SHAPES): an address it would refuse is left out here instead.
_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$")
_DATE_FORMATS = ("%d %b %Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%y")


def normalize_linkedin_url(url: str | None) -> str | None:
    """The canonical form of a LinkedIn profile URL, or ``None`` if it is not one.

    ``http://www.linkedin.com/in/Jane-Doe/?trk=x`` and
    ``https://linkedin.com/in/jane-doe`` are the same profile; both become
    ``https://www.linkedin.com/in/jane-doe``. Keyed on this, an export, a
    newer export and a colleague's export all name the same person.
    """
    if not url or not url.strip():
        return None
    raw = url.strip()
    if "://" not in raw:
        raw = f"https://{raw}"
    parts = urlsplit(raw)
    host = parts.netloc.lower().split(":")[0]
    if not (host == "linkedin.com" or host.endswith(".linkedin.com")):
        return None
    match = _VANITY.match(parts.path)
    if not match:
        return None
    vanity = unquote(match.group(1)).strip().lower()
    if not vanity:
        return None
    return f"https://www.linkedin.com/in/{vanity}"


def linkedin_vanity(normalized_url: str) -> str:
    return normalized_url.rsplit("/", 1)[-1]


def linkedin_key(normalized_url: str) -> str:
    """An ASCII key for a profile, stable and unique per normalized URL.

    A vanity name that is already ``[a-z0-9-]`` and short enough is used as is;
    anything else (accents, percent-encoded scripts, very long names) keeps what
    it can and adds a short hash of the URL, so two profiles never share a key.
    """
    vanity = linkedin_vanity(normalized_url)
    ascii_part = re.sub(r"[^a-z0-9]+", "-", vanity).strip("-")
    limit = _SLUG_MAX - len("li-")
    if ascii_part == vanity and len(ascii_part) <= limit:
        return ascii_part
    digest = hashlib.sha1(normalized_url.encode("utf-8")).hexdigest()[:10]
    return f"{ascii_part[: limit - len(digest) - 1].strip('-')}-{digest}".strip("-")


def linkedin_person_uri(normalized_url: str) -> str:
    return individual_uri(
        str(ABI), "Person", f"linkedin-{linkedin_key(normalized_url)}"
    )


def linkedin_profile_slug(normalized_url: str) -> str:
    # Underscores, not hyphens: the profile query runner takes a person_slug
    # of [a-z][a-z0-9_]*. The key has no underscore, so this stays unique.
    return f"li_{linkedin_key(normalized_url).replace('-', '_')}"


def parse_connected_on(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _publishable(value: str | None, stats: ConnectionsImportStats | None = None) -> str:
    """*value*, or "" when the People app's privacy gate would refuse it.

    The gate refuses a whole dataset for one bad value, so a position that
    reads like a phone number costs that position, not the import.
    """
    text = (value or "").strip()
    if not text:
        return ""
    try:
        check_privacy(text, where="Connections.csv", config={})
    except PrivacyError:
        if stats is not None:
            stats.redacted += 1
        return ""
    return text


class KnownPerson(BaseModel):
    """A person already in a people graph, found by their LinkedIn URL."""

    uri: str
    slug: str | None = None


@dataclass
class ConnectionsImportStats:
    rows: int = 0
    created: int = 0
    matched: int = 0
    skipped: int = 0
    skipped_reasons: dict[str, int] = field(default_factory=dict)
    # Values left out because they read as contact details (privacy gate).
    redacted: int = 0

    def skip(self, reason: str) -> None:
        self.skipped += 1
        self.skipped_reasons[reason] = self.skipped_reasons.get(reason, 0) + 1

    def as_dict(self) -> dict[str, object]:
        return {
            "rows": self.rows,
            "created": self.created,
            "matched": self.matched,
            "skipped": self.skipped,
            "skipped_reasons": dict(self.skipped_reasons),
            "redacted": self.redacted,
        }


@dataclass
class ActOfConnectionsOnLinkedInExportPipelineConfiguration(PipelineConfiguration):
    """Where the graph goes, if anywhere.

    Both or neither: with a store and a graph name, ``run`` inserts the graph
    there; otherwise it only returns it. There is no default graph.
    """

    triple_store: ITripleStoreService | None = None
    graph_name: str | None = None


class ActOfConnectionsOnLinkedInExportPipelineParameters(PipelineParameters):
    owner_uri: Annotated[
        str, Field(description="IRI of the abi:Person who owns the export")
    ]
    owner_name: Annotated[
        str, Field(min_length=1, description="Full name of the export owner")
    ]
    owner_slug: Annotated[
        str | None,
        Field(description="profile_slug of the owner, when they have one already"),
    ] = None
    rows: Annotated[
        list[dict[str, str]],
        Field(
            description="Rows of Connections.csv, as read_connections_csv returns them"
        ),
    ]
    source_path: Annotated[
        str, Field(description="Where the Connections.csv the rows come from is kept")
    ]
    known_people: Annotated[
        dict[str, KnownPerson],
        Field(
            description="People already in the people graphs, keyed on their normalized LinkedIn URL"
        ),
    ] = {}


class ActOfConnectionsOnLinkedInExportPipeline(Pipeline):
    __configuration: ActOfConnectionsOnLinkedInExportPipelineConfiguration

    def __init__(
        self, configuration: ActOfConnectionsOnLinkedInExportPipelineConfiguration
    ):
        super().__init__(configuration)
        self.__configuration = configuration
        self.stats = ConnectionsImportStats()

    def build(
        self, parameters: ActOfConnectionsOnLinkedInExportPipelineParameters
    ) -> tuple[Graph, ConnectionsImportStats]:
        context = PeopleGraphContext(creator=CREATOR)
        stats = ConnectionsImportStats(rows=len(parameters.rows))

        first, _, last = parameters.owner_name.strip().partition(" ")
        owner = context.ensure_person(first, last, uri=parameters.owner_uri)
        if parameters.owner_slug:
            context.set_profile_slug(owner, parameters.owner_slug)
        owner_key = parameters.owner_uri.rstrip("/").rsplit("/", 1)[-1]

        export_file = ProfileDocument(
            _uri=individual_uri(str(LINKEDIN), "ConnectionsExportFile", owner_key),
            label=f"LinkedIn connections export - {owner.label}",
            source_url=parameters.source_path,
            is_profile_document_of=[owner._uri],
            created=utc_now(),
            creator=CREATOR,
        )
        context.graph += export_file.rdf()
        context.graph.add(
            (URIRef(export_file._uri), RDF.type, LINKEDIN.ConnectionsExportFile)
        )
        context.graph.add(
            (URIRef(owner._uri), ABI.hasProfileDocument, URIRef(export_file._uri))
        )

        seen: set[str] = set()
        for row in parameters.rows:
            url = normalize_linkedin_url(row.get("URL"))
            if url is None:
                stats.skip("no_linkedin_url")
                continue
            if url in seen:
                stats.skip("duplicate_row")
                continue
            given = _publishable(row.get("First Name"))
            family = _publishable(row.get("Last Name"))
            if not (given or family):
                stats.skip("no_name")
                continue
            seen.add(url)

            known = parameters.known_people.get(url)
            if known is not None and known.uri == owner._uri:
                stats.skip("owner")
                continue
            uri = known.uri if known else linkedin_person_uri(url)
            person = context.ensure_person(given, family, uri=uri)
            person_key = f"li-{linkedin_key(url)}"
            if known:
                stats.matched += 1
                if known.slug:
                    context.set_profile_slug(person, known.slug)
            else:
                stats.created += 1
                context.set_profile_slug(person, linkedin_profile_slug(url))
            email = (row.get("Email Address") or "").strip()
            context.set_contact_details(
                person,
                email=email if _EMAIL.match(email) else None,
                linkedin_url=url,
            )

            self._add_connection(
                context,
                owner=owner,
                owner_key=owner_key,
                person=person,
                person_key=person_key,
                connected_on=parse_connected_on(row.get("Connected On")),
                export_file=export_file,
            )

            company = _publishable(row.get("Company"), stats)
            position = _publishable(row.get("Position"), stats)
            org = context.ensure_org(company) if company else None
            if not known:
                # What the export says about someone the graphs did not know:
                # their current position as the headline, their company as
                # where they work. A known person keeps what their own
                # source says.
                if position:
                    # Not sourced from the export file: the profile page would
                    # offer the export's path as the person's published profile.
                    context.add_profile_summary(
                        person, headline=position, key=person_key
                    )
                if org is not None:
                    context.graph.add(
                        (URIRef(person._uri), ABI.worksFor, URIRef(org._uri))
                    )
            if org is not None and position:
                context.add_working(
                    person=person,
                    org=org,
                    site=None,
                    skills=[],
                    profile=export_file,
                    title=position,
                    mission_label=position,
                    mission_content=position,
                    employment_type=None,
                    start=None,
                    end=None,
                    duration=None,
                    person_key=person_key,
                )

        bind_graph_prefixes(context.graph)
        context.graph.bind("linkedin", LINKEDIN)
        return context.graph, stats

    @staticmethod
    def _add_connection(
        context: PeopleGraphContext,
        *,
        owner,
        owner_key: str,
        person,
        person_key: str,
        connected_on: date | None,
        export_file: ProfileDocument,
    ) -> str:
        key = f"{owner_key}--{person_key}"
        act_uri = individual_uri(str(LINKEDIN), "ActOfConnection", key)
        temporal_uri = context.add_temporal_region(
            key=f"{key}-connection",
            label=f"Since {connected_on.strftime('%d %b %Y')}" if connected_on else "",
            start=connected_on,
            end=None,
        )
        roles = []
        for suffix, bearer in (("owner", owner), ("connection", person)):
            role = ConnectionRole(
                _uri=individual_uri(str(LINKEDIN), "ConnectionRole", f"{key}-{suffix}"),
                label=f"LinkedIn connection - {bearer.label}",
                is_connection_role_of=[bearer._uri],
                created=utc_now(),
                creator=CREATOR,
            )
            context.graph += role.rdf()
            context.graph.add(
                (URIRef(bearer._uri), LINKEDIN.hasConnectionRole, URIRef(role._uri))
            )
            roles.append(role._uri)
        act = ActOfConnection(
            _uri=act_uri,
            label=f"{owner.label} connected with {person.label}",
            hasParticipant=[owner._uri, person._uri],
            has_connection_owner=[owner._uri],
            has_connected_person=[person._uri],
            occupiesTemporalRegion=[temporal_uri] if temporal_uri else None,
            realizes=roles,
            hasSourceDocument=[export_file._uri],
            created=utc_now(),
            creator=CREATOR,
        )
        context.graph += act.rdf()
        context.graph.add(
            (URIRef(owner._uri), LINKEDIN.isConnectionOwnerIn, URIRef(act_uri))
        )
        context.graph.add(
            (URIRef(person._uri), LINKEDIN.isConnectedPersonIn, URIRef(act_uri))
        )
        return act_uri

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(
            parameters, ActOfConnectionsOnLinkedInExportPipelineParameters
        ):
            raise TypeError(
                "ActOfConnectionsOnLinkedInExportPipeline.run expects "
                "ActOfConnectionsOnLinkedInExportPipelineParameters"
            )
        graph, self.stats = self.build(parameters)
        store = self.__configuration.triple_store
        graph_name = self.__configuration.graph_name
        if store is not None and graph_name and len(graph) > 0:
            store.insert(graph, graph_name=URIRef(graph_name))
        return graph

    def as_tools(self) -> list[BaseTool]:
        def _run(**kwargs: object) -> str:
            params = ActOfConnectionsOnLinkedInExportPipelineParameters.model_validate(
                kwargs
            )
            graph = self.run(params)
            return f"Built {len(graph)} triples: {self.stats.as_dict()}"

        return [
            StructuredTool.from_function(
                func=_run,
                name="linkedin_export_connections_import_csv",
                description=(
                    "Register the connections of a LinkedIn Connections.csv as acts "
                    "of connection between the export owner and each connection."
                ),
                args_schema=ActOfConnectionsOnLinkedInExportPipelineParameters,
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
        # The import is driven by the app that receives the upload: a generic
        # route here could not know whose export it is.
        return None
