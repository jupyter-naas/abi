# onto2py-source-sha256: 2555185c87d921d4a94fe27109a4004f077d6b3de8f0005fa4b641d36a8ddf2c
from __future__ import annotations

import datetime
import uuid
from typing import (
    Annotated,
    Any,
    Callable,
    ClassVar,
    Iterable,
    List,
    Optional,
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
        if origin in (list, List):
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


class TweetCountResultSet(GenericallyDependentContinuant, RDFEntity):
    """
    Tweet Count Result Set
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/TweetCountResultSet"
    _name: ClassVar[str] = "Tweet Count Result Set"
    _property_uris: ClassVar[dict] = {
        "contains_count_bucket": "http://ontology.naas.ai/x/containsCountBucket",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "end_time": "http://ontology.naas.ai/x/end_time",
        "file_path": "http://ontology.naas.ai/x/file_path",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "granularity": "http://ontology.naas.ai/x/granularity",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_count_result_produced_by": "http://ontology.naas.ai/x/isCountResultProducedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "query_string": "http://ontology.naas.ai/x/query_string",
        "start_time": "http://ontology.naas.ai/x/start_time",
        "total_tweet_count": "http://ontology.naas.ai/x/total_tweet_count",
    }
    _object_properties: ClassVar[set[str]] = {
        "contains_count_bucket",
        "generically_depends_on",
        "is_concretized_by",
        "is_count_result_produced_by",
    }

    # Data properties
    query_string: Optional[
        Annotated[
            str,
            Field(
                description="The X v2 search query expression (1-4096 chars) submitted as the `query` parameter to GET /2/tweets/counts/recent that this count result set answers."
            ),
        ]
    ] = None
    granularity: Optional[
        Annotated[
            str,
            Field(
                description="The time-bucket size requested from the X v2 counts endpoint: 'minute', 'hour' or 'day'; sent as the `granularity` parameter."
            ),
        ]
    ] = None
    start_time: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="The oldest UTC timestamp (inclusive) bounding the count window, sent as the `start_time` parameter."
            ),
        ]
    ] = None
    end_time: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="The newest UTC timestamp (exclusive) bounding the count window, sent as the `end_time` parameter."
            ),
        ]
    ] = None
    total_tweet_count: Optional[
        Annotated[
            int,
            Field(
                description="The grand total of tweets matching the query across every bucket of the count result set, as exposed by the summed X v2 `meta.total_tweet_count` field."
            ),
        ]
    ] = None
    file_path: Optional[
        Annotated[
            str,
            Field(
                description="Path to the JSON envelope file in object storage that persists the query, options and merged count buckets backing this count result set."
            ),
        ]
    ] = None
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Optional[
        Annotated[
            datetime.datetime,
            Field(description="Date of creation of the resource."),
        ]
    ] = None
    creator: Optional[
        Annotated[
            Any,
            Field(description="An entity responsible for making the resource."),
        ]
    ] = None

    # Object properties
    contains_count_bucket: Optional[
        Annotated[
            List[Union[TweetCountBucket, URIRef, str]],
            Field(
                description="Relates a count result set to a time-bucketed tweet count it contains."
            ),
        ]
    ] = None
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_count_result_produced_by: Optional[
        Annotated[
            List[Union[CountRecentTweets, Process, URIRef, str]],
            Field(
                description="Relates a count result set to the process that produced it."
            ),
        ]
    ] = None


class TweetCountBucket(GenericallyDependentContinuant, RDFEntity):
    """
    Tweet Count Bucket
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/TweetCountBucket"
    _name: ClassVar[str] = "Tweet Count Bucket"
    _property_uris: ClassVar[dict] = {
        "bucket_tweet_count": "http://ontology.naas.ai/x/bucket_tweet_count",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_count_interval": "http://ontology.naas.ai/x/hasCountInterval",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_count_bucket_of": "http://ontology.naas.ai/x/isCountBucketOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_count_interval",
        "is_concretized_by",
        "is_count_bucket_of",
    }

    # Data properties
    bucket_tweet_count: Optional[
        Annotated[
            int,
            Field(
                description="The number of tweets matching the query during a single time bucket, as exposed by the X v2 `data[].tweet_count` field of the counts endpoint."
            ),
        ]
    ] = None
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Optional[
        Annotated[
            datetime.datetime,
            Field(description="Date of creation of the resource."),
        ]
    ] = None
    creator: Optional[
        Annotated[
            Any,
            Field(description="An entity responsible for making the resource."),
        ]
    ] = None

    # Object properties
    generically_depends_on: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b generically depends on c =Def b is a generically dependent continuant & c is an independent continuant that is not a spatial region & at some time t there inheres in c a specifically dependent continuant which concretizes b at t"
            ),
        ]
    ] = None
    has_count_interval: Optional[
        Annotated[
            List[Union[CountInterval, URIRef, str]],
            Field(
                description="Relates a time-bucketed tweet count to the temporal interval it counts over (its bucket, carrying a first instant bucketStart and a last instant bucketEnd)."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_count_bucket_of: Optional[
        Annotated[
            List[Union[TweetCountResultSet, URIRef, str]],
            Field(
                description="Relates a time-bucketed tweet count to a count result set it belongs to."
            ),
        ]
    ] = None


class CountRecentTweets(Process, RDFEntity):
    """
    Count Recent Tweets
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/CountRecentTweets"
    _name: ClassVar[str] = "Count Recent Tweets"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_participant": "http://ontology.naas.ai/abi/hasParticipant",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "occupies_temporal_region": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "occurs_in": "http://ontology.naas.ai/abi/occursIn",
        "produces_count_result": "http://ontology.naas.ai/x/producesCountResult",
        "realizes": "http://ontology.naas.ai/abi/realizes",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_participant",
        "occupies_temporal_region",
        "occurs_in",
        "produces_count_result",
        "realizes",
    }

    # Data properties
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Optional[
        Annotated[
            datetime.datetime,
            Field(description="Date of creation of the resource."),
        ]
    ] = None
    creator: Optional[
        Annotated[
            Any,
            Field(description="An entity responsible for making the resource."),
        ]
    ] = None

    # Object properties
    concretizes: Optional[
        Annotated[
            List[Union[GenericallyDependentContinuant, URIRef, str]],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
    ] = None
    has_participant: Optional[
        Annotated[
            List[Union[MaterialEntity, Quality, URIRef, str]],
            Field(description="p has participant c =Def c participates in p"),
        ]
    ] = None
    occupies_temporal_region: Optional[
        Annotated[
            List[Union[TemporalRegion, URIRef, str]],
            Field(
                description="p occupies temporal region t =Def p is a process or process boundary & the spatiotemporal region occupied by p temporally projects onto t"
            ),
        ]
    ] = None
    occurs_in: Optional[
        Annotated[
            List[Union[Site, URIRef, str]],
            Field(
                description="b occurs in c =Def b is a process or a process boundary & c is a material entity or site & there exists a spatiotemporal region r & b occupies spatiotemporal region r & for all time t, if b exists at t then c exists at t & there exist spatial regions s and s' where b spatially projects onto s at t & c occupies spatial region s' at t & s is a continuant part of s' at t"
            ),
        ]
    ] = None
    produces_count_result: Optional[
        Annotated[
            List[Union[TweetCountResultSet, URIRef, str]],
            Field(
                description="Relates a tweet-count process to the time-bucketed count result set it produces."
            ),
        ]
    ] = None
    realizes: Optional[
        Annotated[
            List[Union[Disposition, Role, URIRef, str]],
            Field(
                description="(Elucidation) realizes is a relation between a process b and realizable entity c such that c inheres in some d & for all t, if b has participant d then c exists & the type instantiated by b is correlated with the type instantiated by c"
            ),
        ]
    ] = None


class CountInterval(TemporalRegion, RDFEntity):
    """
    Count Interval
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/CountInterval"
    _name: ClassVar[str] = "Count Interval"
    _property_uris: ClassVar[dict] = {
        "bucket_end": "http://ontology.naas.ai/x/bucket_end",
        "bucket_start": "http://ontology.naas.ai/x/bucket_start",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_first_instant": "http://ontology.naas.ai/abi/hasFirstInstant",
        "has_last_instant": "http://ontology.naas.ai/abi/hasLastInstant",
        "is_count_interval_of": "http://ontology.naas.ai/x/isCountIntervalOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "has_first_instant",
        "has_last_instant",
        "is_count_interval_of",
    }

    # Data properties
    bucket_start: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="The inclusive UTC start instant of a count bucket, as exposed by the X v2 `data[].start` field of the counts endpoint."
            ),
        ]
    ] = None
    bucket_end: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="The exclusive UTC end instant of a count bucket, as exposed by the X v2 `data[].end` field of the counts endpoint."
            ),
        ]
    ] = None
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Optional[
        Annotated[
            datetime.datetime,
            Field(description="Date of creation of the resource."),
        ]
    ] = None
    creator: Optional[
        Annotated[
            Any,
            Field(description="An entity responsible for making the resource."),
        ]
    ] = None

    # Object properties
    has_first_instant: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(description="t has first instant t' =Def t' first instant of t"),
        ]
    ] = None
    has_last_instant: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(description="t has last instant t' =Def t' last instant of t"),
        ]
    ] = None
    is_count_interval_of: Optional[
        Annotated[
            List[Union[TweetCountBucket, URIRef, str]],
            Field(
                description="Relates a count interval to the time-bucketed tweet count that occupies it."
            ),
        ]
    ] = None


# Rebuild models to resolve forward references
TweetCountResultSet.model_rebuild()
TweetCountBucket.model_rebuild()
CountRecentTweets.model_rebuild()
CountInterval.model_rebuild()
