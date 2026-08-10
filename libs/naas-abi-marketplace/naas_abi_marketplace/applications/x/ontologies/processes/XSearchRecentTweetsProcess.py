from __future__ import annotations

import datetime
import uuid
from collections.abc import Callable, Iterable
from typing import (
    Annotated,
    Any,
    ClassVar,
    Union,
    get_args,
    get_origin,
)

from naas_abi.ontologies.modules.ABIOntology import (
    Disposition,
    GenericallyDependentContinuant,
    MaterialEntity,
    Process,
    Quality,
    Role,
    Site,
    TemporalInstant,
    TemporalRegion,
)
from naas_abi_marketplace.applications.x.ontologies.modules.XOntology import (
    Media,
    ReferencedTweet,
    Tweet,
    XPlatform,
    XUser,
)
from pydantic import BaseModel, Field, ValidationError
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

BFO = Namespace("http://purl.obolibrary.org/obo/")
ABI = Namespace("http://ontology.naas.ai/abi/")
CCO = Namespace("https://www.commoncoreontologies.org/")


# Base class for all RDF entities
class RDFEntity(BaseModel):
    """Base class for all RDF entities with URI and namespace management"""

    _namespace: ClassVar[str] = "http://ontology.naas.ai/abi/"
    _uri: str = ""
    _object_properties: ClassVar[set[str]] = set()
    _query_executor: ClassVar[Callable[[str], Iterable[object]] | None] = None

    model_config = {"arbitrary_types_allowed": True, "extra": "forbid"}

    def __init__(self, **kwargs):
        uri = kwargs.pop("_uri", None)
        super().__init__(**kwargs)
        if uri is not None:
            self._uri = uri
        elif not self._uri:
            self._uri = f"{self._namespace}{uuid.uuid4()}"

    @classmethod
    def set_namespace(cls, namespace: str):
        """Set the namespace for generating URIs"""
        cls._namespace = namespace

    @classmethod
    def set_query_executor(
        cls, query_executor: Callable[[str], Iterable[object]] | None
    ):
        """Set the SPARQL query executor used by from_iri()."""
        cls._query_executor = query_executor

    @staticmethod
    def _extract_result_value(row: object, key: str) -> object | None:
        """Extract a SPARQL binding value from a ResultRow-like object."""
        if hasattr(row, key):
            return getattr(row, key)
        try:
            return row[key]  # type: ignore[index]
        except Exception:
            pass

        labels = getattr(row, "labels", None)
        if labels and key in labels:
            try:
                return row[key]  # type: ignore[index]
            except Exception:
                pass

        if isinstance(row, (list, tuple)):
            idx = 0 if key == "p" else 1
            if len(row) > idx:
                return row[idx]

        return None

    @staticmethod
    def _coerce_rdf_value(value: object, is_object_property: bool) -> object:
        """Convert RDFLib values to python values used by generated models."""
        if value is None:
            return None
        if is_object_property:
            return str(value)
        if isinstance(value, Literal):
            return value.toPython()
        return str(value)

    @staticmethod
    def _field_expects_list(field_annotation: object) -> bool:
        """Return True when a field annotation contains a list type."""
        origin = get_origin(field_annotation)
        if origin in (list, list):
            return True
        if origin is Annotated:
            args = get_args(field_annotation)
            if args:
                return RDFEntity._field_expects_list(args[0])
            return False
        if origin is Union:
            return any(
                RDFEntity._field_expects_list(arg)
                for arg in get_args(field_annotation)
                if arg is not type(None)
            )
        return False

    @staticmethod
    def _fallback_label_from_iri(iri: str) -> str:
        """Build a best-effort label from an IRI."""
        trimmed = iri.rstrip("/")
        if "#" in trimmed:
            return trimmed.split("#")[-1] or trimmed
        return trimmed.split("/")[-1] or trimmed

    @classmethod
    def from_iri(
        cls,
        iri: str,
        query_executor: Callable[[str], Iterable[object]] | None = None,
        graph_name: str | None = None,
    ):
        """Load a class instance from an IRI using SPARQL query results."""
        iri = str(iri).strip()
        if not iri:
            raise ValueError("iri must be a non-empty string")
        if "<" in iri or ">" in iri:
            raise ValueError("iri must not contain angle brackets")
        if graph_name is not None:
            graph_name = str(graph_name).strip()
            if not graph_name:
                graph_name = None
            elif "<" in graph_name or ">" in graph_name:
                raise ValueError("graph_name must not contain angle brackets")

        executor = query_executor or cls._query_executor
        if executor is None:
            raise ValueError(
                "No query executor configured. Pass query_executor to from_iri() "
                "or set it with set_query_executor()."
            )

        if graph_name:
            sparql_query = f"""
                SELECT ?p ?o
                WHERE {{
                    GRAPH <{graph_name}> {{
                        <{iri}> ?p ?o .
                        FILTER(?p != <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>)
                    }}
                }}
            """
        else:
            sparql_query = f"""
                SELECT ?p ?o
                WHERE {{
                    <{iri}> ?p ?o .
                    FILTER(?p != <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>)
                }}
            """

        results = executor(sparql_query)
        reverse_property_uris = {
            prop_uri: prop_name
            for prop_name, prop_uri in getattr(cls, "_property_uris", {}).items()
        }
        object_props: set[str] = getattr(cls, "_object_properties", set())
        model_fields = getattr(cls, "model_fields", {})
        values: dict[str, Any] = {}

        for row in results:  # type: ignore[assignment]
            predicate = cls._extract_result_value(row, "p")
            obj = cls._extract_result_value(row, "o")
            if predicate is None:
                continue
            prop_name = reverse_property_uris.get(str(predicate))
            if not prop_name:
                continue

            coerced = cls._coerce_rdf_value(
                obj,
                is_object_property=prop_name in object_props,
            )
            field_info = model_fields.get(prop_name)
            expects_list = False
            if field_info is not None:
                expects_list = cls._field_expects_list(field_info.annotation)

            if prop_name not in values:
                if expects_list:
                    values[prop_name] = [coerced]
                else:
                    values[prop_name] = coerced
            else:
                existing = values[prop_name]
                if isinstance(existing, list):
                    existing.append(coerced)
                elif expects_list:
                    values[prop_name] = [existing, coerced]
                else:
                    values[prop_name] = existing

        if "label" in model_fields and "label" not in values:
            values["label"] = cls._fallback_label_from_iri(iri)

        for field_name, field_info in model_fields.items():
            if field_name in values:
                continue
            if field_info.is_required():
                if cls._field_expects_list(field_info.annotation):
                    values[field_name] = []
                else:
                    values[field_name] = None

        try:
            return cls(_uri=iri, **values)
        except ValidationError:
            # Keep loading permissive for partially populated RDF resources.
            return cls.model_construct(
                _fields_set=set(values.keys()), _uri=iri, **values
            )

    def rdf(
        self, subject_uri: str | None = None, visited: set[str] | None = None
    ) -> Graph:
        """Generate RDF triples for this instance

        Args:
            subject_uri: Optional URI to use as subject (defaults to self._uri)
            visited: Set of URIs that have already been processed (for cycle detection)
        """
        # Initialize visited set if not provided
        if visited is None:
            visited = set()

        g = Graph()
        g.bind("cco", CCO)
        g.bind("bfo", BFO)
        g.bind("abi", ABI)
        g.bind("rdfs", RDFS)
        g.bind("rdf", RDF)
        g.bind("owl", OWL)
        g.bind("xsd", XSD)

        # Use stored URI or provided subject_uri
        if subject_uri is None:
            subject_uri = self._uri
        subject = URIRef(subject_uri)

        # Check if we've already processed this entity (cycle detection)
        if subject_uri in visited:
            # Already processed, just return empty graph to avoid infinite recursion
            # The relationship triple will be added by the caller
            return g

        # Mark this entity as visited before processing
        visited.add(subject_uri)

        # Add class type
        if hasattr(self, "_class_uri"):
            g.add((subject, RDF.type, URIRef(self._class_uri)))

        # Add owl:NamedIndividual type
        g.add((subject, RDF.type, OWL.NamedIndividual))

        # Add label if it exists
        if hasattr(self, "label"):
            g.add((subject, RDFS.label, Literal(self.label)))

        object_props: set[str] = getattr(self, "_object_properties", set())

        # Add properties
        if hasattr(self, "_property_uris"):
            for prop_name, prop_uri in self._property_uris.items():
                is_object_prop = prop_name in object_props
                prop_value = getattr(self, prop_name, None)
                if prop_value is not None:
                    if isinstance(prop_value, list):
                        for item in prop_value:
                            if hasattr(item, "rdf") and hasattr(item, "_uri"):
                                # Check if this entity was already visited to prevent cycles
                                if item._uri not in visited:
                                    # Add triples from related object
                                    g += item.rdf(visited=visited)
                                # Always add the triple, even if already visited
                                g.add((subject, URIRef(prop_uri), URIRef(item._uri)))
                            elif is_object_prop and isinstance(item, (str, URIRef)):
                                g.add((subject, URIRef(prop_uri), URIRef(str(item))))
                            else:
                                g.add((subject, URIRef(prop_uri), Literal(item)))
                    elif hasattr(prop_value, "rdf") and hasattr(prop_value, "_uri"):
                        # Check if this entity was already visited to prevent cycles
                        if prop_value._uri not in visited:
                            # Add triples from related object
                            g += prop_value.rdf(visited=visited)
                        # Always add the triple, even if already visited
                        g.add((subject, URIRef(prop_uri), URIRef(prop_value._uri)))
                    elif is_object_prop and isinstance(prop_value, (str, URIRef)):
                        g.add((subject, URIRef(prop_uri), URIRef(str(prop_value))))
                    else:
                        g.add((subject, URIRef(prop_uri), Literal(prop_value)))

        return g


class SearchQuery(GenericallyDependentContinuant, RDFEntity):
    """
    Search Query
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/SearchQuery"
    _name: ClassVar[str] = "Search Query"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "end_time": "http://ontology.naas.ai/x/end_time",
        "expansions": "http://ontology.naas.ai/x/expansions",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_search_query_role": "http://ontology.naas.ai/x/hasSearchQueryRole",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_search_query_of": "http://ontology.naas.ai/x/isSearchQueryOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "max_pages": "http://ontology.naas.ai/x/max_pages",
        "max_results": "http://ontology.naas.ai/x/max_results",
        "media_fields": "http://ontology.naas.ai/x/media_fields",
        "place_fields": "http://ontology.naas.ai/x/place_fields",
        "poll_fields": "http://ontology.naas.ai/x/poll_fields",
        "query_string": "http://ontology.naas.ai/x/query_string",
        "since_id": "http://ontology.naas.ai/x/since_id",
        "sort_order": "http://ontology.naas.ai/x/sort_order",
        "start_time": "http://ontology.naas.ai/x/start_time",
        "tweet_fields": "http://ontology.naas.ai/x/tweet_fields",
        "until_id": "http://ontology.naas.ai/x/until_id",
        "user_fields": "http://ontology.naas.ai/x/user_fields",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_search_query_role",
        "is_concretized_by",
        "is_search_query_of",
    }

    # Data properties
    query_string: (
        Annotated[
            str,
            Field(
                description="The X v2 search query expression (1-4096 chars) submitted as the `query` parameter to GET /2/tweets/search/recent."
            ),
        ]
        | None
    ) = None
    start_time: (
        Annotated[
            datetime.datetime,
            Field(
                description="The oldest UTC timestamp (inclusive) bounding the search window, sent as the `start_time` parameter."
            ),
        ]
        | None
    ) = None
    end_time: (
        Annotated[
            datetime.datetime,
            Field(
                description="The newest UTC timestamp (exclusive) bounding the search window, sent as the `end_time` parameter."
            ),
        ]
        | None
    ) = None
    since_id: (
        Annotated[
            str,
            Field(
                description="Lower-exclusive tweet-id bound: only tweets with an id greater than this value are returned."
            ),
        ]
        | None
    ) = None
    until_id: (
        Annotated[
            str,
            Field(
                description="Upper-exclusive tweet-id bound: only tweets with an id less than this value are returned."
            ),
        ]
        | None
    ) = None
    max_results: (
        Annotated[
            int,
            Field(
                description="Maximum number of tweets to return per page (10-100) when querying GET /2/tweets/search/recent."
            ),
        ]
        | None
    ) = None
    sort_order: (
        Annotated[
            str,
            Field(
                description="Sort order requested for returned tweets: either 'recency' or 'relevancy'."
            ),
        ]
        | None
    ) = None
    max_pages: (
        Annotated[
            int,
            Field(
                description="Maximum number of result pages to fetch from the X v2 endpoint during a single search process."
            ),
        ]
        | None
    ) = None
    tweet_fields: (
        Annotated[
            str,
            Field(
                description="Comma-joined list of fields to include on each Tweet object, sent as the `tweet.fields` parameter."
            ),
        ]
        | None
    ) = None
    expansions: (
        Annotated[
            str,
            Field(
                description="Comma-joined list of object expansions to apply, sent as the `expansions` parameter. `referenced_tweets.id` is what causes the response to carry ReferencedTweet individuals alongside the matches."
            ),
        ]
        | None
    ) = None
    media_fields: (
        Annotated[
            str,
            Field(
                description="Comma-joined list of fields on expanded Media objects, sent as the `media.fields` parameter."
            ),
        ]
        | None
    ) = None
    poll_fields: (
        Annotated[
            str,
            Field(
                description="Comma-joined list of fields on expanded Poll objects, sent as the `poll.fields` parameter."
            ),
        ]
        | None
    ) = None
    user_fields: (
        Annotated[
            str,
            Field(
                description="Comma-joined list of fields on expanded User objects, sent as the `user.fields` parameter."
            ),
        ]
        | None
    ) = None
    place_fields: (
        Annotated[
            str,
            Field(
                description="Comma-joined list of fields on expanded Place objects, sent as the `place.fields` parameter."
            ),
        ]
        | None
    ) = None
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    generically_depends_on: (
        Annotated[
            list[MaterialEntity | URIRef | str],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
        | None
    ) = None
    has_search_query_role: (
        Annotated[
            list[SearchQueryRole | URIRef | str],
            Field(
                description="Relates a search query artifact to a search query role that concretizes it during search execution."
            ),
        ]
        | None
    ) = None
    is_concretized_by: (
        Annotated[
            list[Disposition | Process | Quality | Role | URIRef | str],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
        | None
    ) = None
    is_search_query_of: (
        Annotated[
            list[SearchRecentTweets | URIRef | str],
            Field(
                description="Relates a search query artifact to the recent-tweet search process that executes it."
            ),
        ]
        | None
    ) = None


class SearchResultSet(GenericallyDependentContinuant, RDFEntity):
    """
    Search Result Set
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/SearchResultSet"
    _name: ClassVar[str] = "Search Result Set"
    _property_uris: ClassVar[dict] = {
        "contains_referenced_tweet": "http://ontology.naas.ai/x/containsReferencedTweet",
        "contains_tweet": "http://ontology.naas.ai/x/containsTweet",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "file_path": "http://ontology.naas.ai/x/file_path",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_produced_by": "http://ontology.naas.ai/x/isProducedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "newest_id": "http://ontology.naas.ai/x/newest_id",
        "next_token": "http://ontology.naas.ai/x/next_token",
        "oldest_id": "http://ontology.naas.ai/x/oldest_id",
        "referenced_count": "http://ontology.naas.ai/x/referenced_count",
        "result_count": "http://ontology.naas.ai/x/result_count",
        "result_set_id": "http://ontology.naas.ai/x/result_set_id",
    }
    _object_properties: ClassVar[set[str]] = {
        "contains_referenced_tweet",
        "contains_tweet",
        "generically_depends_on",
        "is_concretized_by",
        "is_produced_by",
    }

    # Data properties
    result_set_id: (
        Annotated[
            str,
            Field(
                description="Short hash identifying the search result set in the local datastore; an 8-character hex digest of the sorted parameter dictionary used as the cache key and filename."
            ),
        ]
        | None
    ) = None
    result_count: (
        Annotated[
            int,
            Field(
                description="Number of tweets that matched the query in this search result set, as exposed by the X v2 `meta.result_count` field. Counts only the `data` array — referenced tweets carried for context are counted by referenced_count instead."
            ),
        ]
        | None
    ) = None
    referenced_count: (
        Annotated[
            int,
            Field(
                description="Number of referenced tweets carried by this search result set as expansion context — the entries of the X v2 `includes.tweets` array that are absent from `data`. These did not match the query and are excluded from result_count."
            ),
        ]
        | None
    ) = None
    file_path: (
        Annotated[
            str,
            Field(
                description="Path to the JSON envelope file in object storage that persists the query, options and merged results backing this search result set."
            ),
        ]
        | None
    ) = None
    newest_id: (
        Annotated[
            str,
            Field(
                description="Id of the most recent tweet in the result set, as exposed by the X v2 `meta.newest_id` field."
            ),
        ]
        | None
    ) = None
    oldest_id: (
        Annotated[
            str,
            Field(
                description="Id of the oldest tweet in the result set, as exposed by the X v2 `meta.oldest_id` field."
            ),
        ]
        | None
    ) = None
    next_token: (
        Annotated[
            str,
            Field(
                description="Pagination token to retrieve the next page of results, as exposed by the X v2 `meta.next_token` field."
            ),
        ]
        | None
    ) = None
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    contains_referenced_tweet: (
        Annotated[
            list[ReferencedTweet | URIRef | str],
            Field(
                description="Relates a search result set to a referenced tweet returned alongside its matches — an entry of the X v2 `includes.tweets` array that is absent from `data`. The referenced tweet is present only as conversational context for a matched tweet that replies to, quotes or retweets it, and must not be counted as a search result."
            ),
        ]
        | None
    ) = None
    contains_tweet: (
        Annotated[
            list[Tweet | URIRef | str],
            Field(
                description="Relates a search result set to a tweet that matched its query — an entry of the X v2 `data` array. This relation is the definition of 'was a search result': tweets reachable only through x:containsReferencedTweet did not match the query and are excluded."
            ),
        ]
        | None
    ) = None
    generically_depends_on: (
        Annotated[
            list[MaterialEntity | URIRef | str],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
        | None
    ) = None
    is_concretized_by: (
        Annotated[
            list[Disposition | Process | Quality | Role | URIRef | str],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
        | None
    ) = None
    is_produced_by: (
        Annotated[
            list[Process | SearchRecentTweets | URIRef | str],
            Field(
                description="Relates a search result set to the process that produced it."
            ),
        ]
        | None
    ) = None


class SearchQueryRole(Role, RDFEntity):
    """
    Search Query Role
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/SearchQueryRole"
    _name: ClassVar[str] = "Search Query Role"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_realization": "http://ontology.naas.ai/abi/hasRealization",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "is_search_query_role_of": "http://ontology.naas.ai/x/isSearchQueryRoleOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_realization",
        "inheres_in",
        "is_search_query_role_of",
    }

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    concretizes: (
        Annotated[
            list[GenericallyDependentContinuant | URIRef | str],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
        | None
    ) = None
    has_realization: (
        Annotated[
            list[Process | URIRef | str],
            Field(description="b has realization c =Def c realizes b"),
        ]
        | None
    ) = None
    inheres_in: (
        Annotated[
            list[MaterialEntity | URIRef | str],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
        | None
    ) = None
    is_search_query_role_of: (
        Annotated[
            list[SearchQuery | URIRef | str],
            Field(
                description="Relates a search query role to the search query artifact in which it inheres."
            ),
        ]
        | None
    ) = None


class SearchRecentTweets(Process, RDFEntity):
    """
    Search Recent Tweets
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/SearchRecentTweets"
    _name: ClassVar[str] = "Search Recent Tweets"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "executed_at": "http://ontology.naas.ai/x/executedAt",
        "executed_by": "http://ontology.naas.ai/x/executedBy",
        "has_participant": "http://ontology.naas.ai/abi/hasParticipant",
        "has_search_interval": "http://ontology.naas.ai/x/hasSearchInterval",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "occupies_temporal_region": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "occursIn": "http://ontology.naas.ai/abi/occursIn",
        "occurs_in": "http://ontology.naas.ai/abi/occursIn",
        "produces_search_result": "http://ontology.naas.ai/x/producesSearchResult",
        "realizes": "http://ontology.naas.ai/abi/realizes",
        "retrieves_media": "http://ontology.naas.ai/x/retrievesMedia",
        "retrieves_referenced_tweet": "http://ontology.naas.ai/x/retrievesReferencedTweet",
        "retrieves_tweet": "http://ontology.naas.ai/x/retrievesTweet",
        "retrieves_user": "http://ontology.naas.ai/x/retrievesUser",
        "uses_search_query": "http://ontology.naas.ai/x/usesSearchQuery",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "executed_at",
        "executed_by",
        "has_participant",
        "has_search_interval",
        "occupies_temporal_region",
        "occursIn",
        "occurs_in",
        "produces_search_result",
        "realizes",
        "retrieves_media",
        "retrieves_referenced_tweet",
        "retrieves_tweet",
        "retrieves_user",
        "uses_search_query",
    }

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    concretizes: (
        Annotated[
            list[GenericallyDependentContinuant | URIRef | str],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
        | None
    ) = None
    executed_at: (
        Annotated[
            list[TemporalInstant | URIRef | str],
            Field(
                description="Relates a recent-tweet search process to the temporal instant at which the API call was issued."
            ),
        ]
        | None
    ) = None
    executed_by: (
        Annotated[
            list[URIRef | XUser | str],
            Field(
                description="Relates a recent-tweet search process to the X user account on whose behalf the API call was made."
            ),
        ]
        | None
    ) = None
    has_participant: (
        Annotated[
            list[MaterialEntity | Quality | URIRef | str],
            Field(description="p has participant c =Def c participates in p"),
        ]
        | None
    ) = None
    has_search_interval: (
        Annotated[
            list[SearchInterval | URIRef | str],
            Field(
                description="Relates an X process to the temporal interval that bounds its execution, carrying a first instant (searchStartedAt) and a last instant (searchEndedAt)."
            ),
        ]
        | None
    ) = None
    occupies_temporal_region: (
        Annotated[
            list[TemporalRegion | URIRef | str],
            Field(
                description="p occupies temporal region t =Def p is a process or process boundary & the spatiotemporal region occupied by p temporally projects onto t"
            ),
        ]
        | None
    ) = None
    occursIn: Annotated[list[URIRef | XPlatform | str], Field()] | None = None
    occurs_in: (
        Annotated[
            list[Site | URIRef | str],
            Field(
                description="b occurs in c =Def b is a process or a process boundary & c is a material entity or site & there exists a spatiotemporal region r & b occupies spatiotemporal region r & for all time t, if b exists at t then c exists at t & there exist spatial regions s and s' where b spatially projects onto s at t & c occupies spatial region s' at t & s is a continuant part of s' at t"
            ),
        ]
        | None
    ) = None
    produces_search_result: (
        Annotated[
            list[SearchResultSet | URIRef | str],
            Field(
                description="Relates a tweet-ingestion process to the search result set it produces."
            ),
        ]
        | None
    ) = None
    realizes: (
        Annotated[
            list[Disposition | Role | URIRef | str],
            Field(
                description="(Elucidation) realizes is a relation between a process b and realizable entity c such that c inheres in some d & for all t, if b has participant d then c exists & the type instantiated by b is correlated with the type instantiated by c"
            ),
        ]
        | None
    ) = None
    retrieves_media: (
        Annotated[
            list[Media | URIRef | str],
            Field(
                description="Relates a recent-tweet search process to a media artifact expanded in its response (the `includes.media` of the X v2 search response)."
            ),
        ]
        | None
    ) = None
    retrieves_referenced_tweet: (
        Annotated[
            list[ReferencedTweet | URIRef | str],
            Field(
                description="Relates a recent-tweet search process to a referenced tweet expanded in its response (an `includes.tweets` entry absent from `data`), retrieved as context for a match rather than as a match itself."
            ),
        ]
        | None
    ) = None
    retrieves_tweet: (
        Annotated[
            list[Tweet | URIRef | str],
            Field(
                description="Relates a recent-tweet search process to a tweet it retrieved as a match of its query (the `data` tweets of the X v2 search response)."
            ),
        ]
        | None
    ) = None
    retrieves_user: (
        Annotated[
            list[URIRef | XUser | str],
            Field(
                description="Relates a recent-tweet search process to an X user account expanded in its response (the `includes.users` of the X v2 search response)."
            ),
        ]
        | None
    ) = None
    uses_search_query: (
        Annotated[
            list[SearchQuery | URIRef | str],
            Field(
                description="Relates a recent-tweet search process to the search query artifact it executes against the X v2 API."
            ),
        ]
        | None
    ) = None


class SearchInterval(TemporalRegion, RDFEntity):
    """
    Search Interval
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/SearchInterval"
    _name: ClassVar[str] = "Search Interval"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_first_instant": "http://ontology.naas.ai/abi/hasFirstInstant",
        "has_last_instant": "http://ontology.naas.ai/abi/hasLastInstant",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "search_ended_at": "http://ontology.naas.ai/x/searchEndedAt",
        "search_started_at": "http://ontology.naas.ai/x/searchStartedAt",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_first_instant",
        "has_last_instant",
        "search_ended_at",
        "search_started_at",
    }

    # Data properties
    label: Annotated[str, Field(description="Label of the resource.")] | None = None
    created: (
        Annotated[
            datetime.datetime, Field(description="Date of creation of the resource.")
        ]
        | None
    ) = None
    creator: (
        Annotated[
            Any, Field(description="An entity responsible for making the resource.")
        ]
        | None
    ) = None

    # Object properties
    has_first_instant: (
        Annotated[
            list[TemporalInstant | URIRef | str],
            Field(description="t has first instant t' =Def t' first instant of t"),
        ]
        | None
    ) = None
    has_last_instant: (
        Annotated[
            list[TemporalInstant | URIRef | str],
            Field(description="t has last instant t' =Def t' last instant of t"),
        ]
        | None
    ) = None
    search_ended_at: (
        Annotated[
            list[TemporalInstant | URIRef | str],
            Field(
                description="Relates a search interval to the temporal instant at which the search process completed."
            ),
        ]
        | None
    ) = None
    search_started_at: (
        Annotated[
            list[TemporalInstant | URIRef | str],
            Field(
                description="Relates a search interval to the temporal instant at which the search process started."
            ),
        ]
        | None
    ) = None


# Rebuild models to resolve forward references
SearchQuery.model_rebuild()
SearchResultSet.model_rebuild()
SearchQueryRole.model_rebuild()
SearchRecentTweets.model_rebuild()
SearchInterval.model_rebuild()
