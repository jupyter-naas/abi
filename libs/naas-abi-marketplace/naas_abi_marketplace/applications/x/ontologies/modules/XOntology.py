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
    Person,
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


class XPlatform(Site, RDFEntity):
    """
    X Platform
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/XPlatform"
    _name: ClassVar[str] = "X Platform"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = set()

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


class XUser(GenericallyDependentContinuant, RDFEntity):
    """
    X User
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/XUser"
    _name: ClassVar[str] = "X User"
    _property_uris: ClassVar[dict] = {
        "author_id": "http://ontology.naas.ai/x/author_id",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_authored_tweet": "http://ontology.naas.ai/x/hasAuthoredTweet",
        "has_user_public_metrics": "http://ontology.naas.ai/x/hasUserPublicMetrics",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_identity_verified": "http://ontology.naas.ai/x/is_identity_verified",
        "is_x_user_account_of": "http://ontology.naas.ai/x/isXUserAccountOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "most_recent_tweet_id": "http://ontology.naas.ai/x/most_recent_tweet_id",
        "parody": "http://ontology.naas.ai/x/parody",
        "pinned_tweet_id": "http://ontology.naas.ai/x/pinned_tweet_id",
        "profile_banner_url": "http://ontology.naas.ai/x/profile_banner_url",
        "profile_image_url": "http://ontology.naas.ai/x/profile_image_url",
        "protected": "http://ontology.naas.ai/x/protected",
        "subscription_type": "http://ontology.naas.ai/x/subscription_type",
        "user_created_at": "http://ontology.naas.ai/x/user_created_at",
        "user_description": "http://ontology.naas.ai/x/user_description",
        "user_display_name": "http://ontology.naas.ai/x/user_name",
        "user_location": "http://ontology.naas.ai/x/user_location",
        "user_url": "http://ontology.naas.ai/x/user_url",
        "username": "http://ontology.naas.ai/x/username",
        "verified": "http://ontology.naas.ai/x/verified",
        "verified_type": "http://ontology.naas.ai/x/verified_type",
    }
    _object_properties: ClassVar[set[str]] = {
        "author_id",
        "generically_depends_on",
        "has_authored_tweet",
        "has_user_public_metrics",
        "is_concretized_by",
        "is_x_user_account_of",
    }

    # Data properties
    username: Optional[
        Annotated[
            str,
            Field(description="The unique handle of the X user account (without the "),
        ]
    ] = None
    user_display_name: Optional[
        Annotated[
            str,
            Field(
                description="The display name of the X user account; corresponds to the `name` field of the X v2 User object."
            ),
        ]
    ] = None
    user_description: Optional[
        Annotated[
            str,
            Field(
                description="The profile bio of the X user account; corresponds to the `description` field of the X v2 User object."
            ),
        ]
    ] = None
    user_location: Optional[
        Annotated[
            str,
            Field(
                description="The free-form location declared on the X user profile; corresponds to the `location` field of the X v2 User object."
            ),
        ]
    ] = None
    user_url: Optional[
        Annotated[
            str,
            Field(
                description="The website URL declared on the X user profile; corresponds to the `url` field of the X v2 User object."
            ),
        ]
    ] = None
    user_created_at: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="The UTC timestamp at which the X user account was created; corresponds to the `created_at` field of the X v2 User object."
            ),
        ]
    ] = None
    verified: Optional[
        Annotated[
            bool,
            Field(
                description="Whether the X user account is verified; corresponds to the `verified` field of the X v2 User object."
            ),
        ]
    ] = None
    verified_type: Optional[
        Annotated[
            str,
            Field(
                description="The verification type of the X user account ('blue', 'business', 'government', 'none'); corresponds to the `verified_type` field of the X v2 User object."
            ),
        ]
    ] = None
    protected: Optional[
        Annotated[
            bool,
            Field(
                description="Whether the X user account's tweets are protected (private); corresponds to the `protected` field of the X v2 User object."
            ),
        ]
    ] = None
    parody: Optional[
        Annotated[
            bool,
            Field(
                description="Whether the X user account is self-declared as a parody account; corresponds to the `parody` field of the X v2 User object."
            ),
        ]
    ] = None
    is_identity_verified: Optional[
        Annotated[
            bool,
            Field(
                description="Whether the identity of the X user account holder has been verified by X; corresponds to the `is_identity_verified` field of the X v2 User object."
            ),
        ]
    ] = None
    subscription_type: Optional[
        Annotated[
            str,
            Field(
                description="The X premium subscription tier of the user account; corresponds to the `subscription_type` field of the X v2 User object."
            ),
        ]
    ] = None
    profile_image_url: Optional[
        Annotated[
            str,
            Field(
                description="URL of the profile image of the X user account; corresponds to the `profile_image_url` field of the X v2 User object."
            ),
        ]
    ] = None
    profile_banner_url: Optional[
        Annotated[
            str,
            Field(
                description="URL of the profile banner image of the X user account; corresponds to the `profile_banner_url` field of the X v2 User object."
            ),
        ]
    ] = None
    pinned_tweet_id: Optional[
        Annotated[
            str,
            Field(
                description="Id of the tweet pinned on the X user profile; corresponds to the `pinned_tweet_id` field of the X v2 User object."
            ),
        ]
    ] = None
    most_recent_tweet_id: Optional[
        Annotated[
            str,
            Field(
                description="Id of the most recent tweet posted by the X user account; corresponds to the `most_recent_tweet_id` field of the X v2 User object."
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
    author_id: Optional[
        Annotated[
            Union[URIRef, str],
            Field(
                description="The unique numeric identifier of a user account on the X platform; corresponds to the `author_id` field returned on tweet objects by the X v2 API."
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
    has_authored_tweet: Optional[
        Annotated[
            List[Union[Tweet, URIRef, str]],
            Field(
                description="Relates an X user account to a tweet authored by it on the X platform."
            ),
        ]
    ] = None
    has_user_public_metrics: Optional[
        Annotated[
            List[Union[URIRef, XUserPublicMetrics, str]],
            Field(
                description="Relates an X user account to the public account metrics artifact (followers, following, tweet, listed, like and media counts) exposed by the X v2 API."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_x_user_account_of: Optional[
        Annotated[
            List[Union[Person, URIRef, str]],
            Field(
                description="Relates an X user account to the person on which it generically depends."
            ),
        ]
    ] = None


class Tweet(GenericallyDependentContinuant, RDFEntity):
    """
    Tweet
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/Tweet"
    _name: ClassVar[str] = "Tweet"
    _property_uris: ClassVar[dict] = {
        "card_uri": "http://ontology.naas.ai/x/card_uri",
        "conversation_id": "http://ontology.naas.ai/x/conversation_id",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "edit_history_tweet_id": "http://ontology.naas.ai/x/edit_history_tweet_id",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "has_attached_media": "http://ontology.naas.ai/x/hasAttachedMedia",
        "has_context_annotation": "http://ontology.naas.ai/x/hasContextAnnotation",
        "has_language": "http://ontology.naas.ai/x/hasLanguage",
        "has_public_metrics": "http://ontology.naas.ai/x/hasPublicMetrics",
        "has_url_entity": "http://ontology.naas.ai/x/hasUrlEntity",
        "in_reply_to_user": "http://ontology.naas.ai/x/inReplyToUser",
        "is_authored_by": "http://ontology.naas.ai/x/isAuthoredBy",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_contained_in_search_result_set": "http://ontology.naas.ai/x/isContainedInSearchResultSet",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "mentions_user": "http://ontology.naas.ai/x/mentionsUser",
        "paid_partnership": "http://ontology.naas.ai/x/paid_partnership",
        "possibly_sensitive": "http://ontology.naas.ai/x/possibly_sensitive",
        "quotes_tweet": "http://ontology.naas.ai/x/quotesTweet",
        "references_tweet": "http://ontology.naas.ai/x/referencesTweet",
        "replies_to_tweet": "http://ontology.naas.ai/x/repliesToTweet",
        "reply_settings": "http://ontology.naas.ai/x/reply_settings",
        "retweets_tweet": "http://ontology.naas.ai/x/retweetsTweet",
        "tweet_created_at": "http://ontology.naas.ai/x/tweet_created_at",
        "tweet_id": "http://ontology.naas.ai/x/tweet_id",
        "tweet_text": "http://ontology.naas.ai/x/tweet_text",
        "tweeted_at": "http://ontology.naas.ai/x/tweetedAt",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "has_attached_media",
        "has_context_annotation",
        "has_language",
        "has_public_metrics",
        "has_url_entity",
        "in_reply_to_user",
        "is_authored_by",
        "is_concretized_by",
        "is_contained_in_search_result_set",
        "mentions_user",
        "quotes_tweet",
        "references_tweet",
        "replies_to_tweet",
        "retweets_tweet",
        "tweeted_at",
    }

    # Data properties
    tweet_id: Optional[
        Annotated[
            str,
            Field(
                description="The unique numeric identifier of a tweet on the X platform; corresponds to the `id` field returned by the X v2 API."
            ),
        ]
    ] = None
    tweet_text: Optional[
        Annotated[
            str,
            Field(
                description="The text content of a tweet as published on the X platform; corresponds to the `text` field returned by the X v2 API."
            ),
        ]
    ] = None
    tweet_created_at: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="The UTC timestamp at which the tweet was published on the X platform; corresponds to the `created_at` field returned by the X v2 API."
            ),
        ]
    ] = None
    edit_history_tweet_id: Optional[
        Annotated[
            str,
            Field(
                description="An identifier in the chronological edit history of a tweet, including the original tweet id and any subsequent edited versions; corresponds to the `edit_history_tweet_ids` field returned by the X v2 API."
            ),
        ]
    ] = None
    conversation_id: Optional[
        Annotated[
            str,
            Field(
                description="Id of the root tweet of the conversation thread this tweet belongs to; corresponds to the `conversation_id` field returned by the X v2 API."
            ),
        ]
    ] = None
    reply_settings: Optional[
        Annotated[
            str,
            Field(
                description="Who can reply to the tweet ('everyone', 'mentioned_users', 'followers', ...); corresponds to the `reply_settings` field returned by the X v2 API."
            ),
        ]
    ] = None
    possibly_sensitive: Optional[
        Annotated[
            bool,
            Field(
                description="Whether the tweet content may be sensitive, as flagged by the X platform via the `possibly_sensitive` field."
            ),
        ]
    ] = None
    paid_partnership: Optional[
        Annotated[
            bool,
            Field(
                description="Whether the tweet is flagged as paid-partnership content via the `paid_partnership` field."
            ),
        ]
    ] = None
    card_uri: Optional[
        Annotated[
            str,
            Field(
                description="URI of the link-preview card attached to the tweet; corresponds to the `card_uri` field returned by the X v2 API."
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
    has_attached_media: Optional[
        Annotated[
            List[Union[Media, URIRef, str]],
            Field(
                description="Relates a tweet to a media artifact (photo, video, animated gif) attached to it, resolved through the X v2 `attachments.media_keys` expansion."
            ),
        ]
    ] = None
    has_context_annotation: Optional[
        Annotated[
            List[Union[ContextAnnotation, URIRef, str]],
            Field(
                description="Relates a tweet to a context annotation (domain/entity classification pair) inferred for it by the X platform, as exposed by the X v2 `context_annotations` field."
            ),
        ]
    ] = None
    has_language: Optional[
        Annotated[
            List[Union[TweetLanguage, URIRef, str]],
            Field(
                description="Relates a tweet to the natural-language quality detected for its text content."
            ),
        ]
    ] = None
    has_public_metrics: Optional[
        Annotated[
            List[Union[TweetPublicMetrics, URIRef, str]],
            Field(
                description="Relates a tweet to the public engagement metrics artifact exposed by the X v2 API."
            ),
        ]
    ] = None
    has_url_entity: Optional[
        Annotated[
            List[Union[TweetURL, URIRef, str]],
            Field(
                description="Relates a tweet to a URL entity contained in its text, as exposed by the X v2 `entities.urls` field."
            ),
        ]
    ] = None
    in_reply_to_user: Optional[
        Annotated[
            List[Union[URIRef, XUser, str]],
            Field(
                description="Relates a reply tweet to the X user account whose tweet it replies to, as exposed by the X v2 `in_reply_to_user_id` field."
            ),
        ]
    ] = None
    is_authored_by: Optional[
        Annotated[
            List[Union[URIRef, XUser, str]],
            Field(
                description="Relates a tweet to the X user account that authored it."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_contained_in_search_result_set: Optional[
        Annotated[
            List[Union[SearchResultSet, URIRef, str]],
            Field(
                description="Relates a tweet to a search result set in which it appears."
            ),
        ]
    ] = None
    mentions_user: Optional[
        Annotated[
            List[Union[URIRef, XUser, str]],
            Field(
                description="Relates a tweet to an X user account mentioned in its text, as exposed by the X v2 `entities.mentions` field."
            ),
        ]
    ] = None
    quotes_tweet: Optional[
        Annotated[
            List[Union[Tweet, URIRef, str]],
            Field(
                description="Relates a quote tweet to the tweet it quotes (`referenced_tweets[].type == 'quoted'`)."
            ),
        ]
    ] = None
    references_tweet: Optional[
        Annotated[
            List[Union[Tweet, URIRef, str]],
            Field(
                description="Relates a tweet to another tweet it references (reply, quote or retweet), as exposed by the X v2 `referenced_tweets` field."
            ),
        ]
    ] = None
    replies_to_tweet: Optional[
        Annotated[
            List[Union[Tweet, URIRef, str]],
            Field(
                description="Relates a reply tweet to the tweet it replies to (`referenced_tweets[].type == 'replied_to'`)."
            ),
        ]
    ] = None
    retweets_tweet: Optional[
        Annotated[
            List[Union[Tweet, URIRef, str]],
            Field(
                description="Relates a retweet to the tweet it retweets (`referenced_tweets[].type == 'retweeted'`)."
            ),
        ]
    ] = None
    tweeted_at: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(
                description="Relates a tweet to the temporal instant at which it was published on the X platform."
            ),
        ]
    ] = None


class TweetPublicMetrics(GenericallyDependentContinuant, RDFEntity):
    """
    Tweet Public Metrics
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/TweetPublicMetrics"
    _name: ClassVar[str] = "Tweet Public Metrics"
    _property_uris: ClassVar[dict] = {
        "bookmark_count": "http://ontology.naas.ai/x/bookmark_count",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "impression_count": "http://ontology.naas.ai/x/impression_count",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_public_metrics_of": "http://ontology.naas.ai/x/isPublicMetricsOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "like_count": "http://ontology.naas.ai/x/like_count",
        "quote_count": "http://ontology.naas.ai/x/quote_count",
        "reply_count": "http://ontology.naas.ai/x/reply_count",
        "retweet_count": "http://ontology.naas.ai/x/retweet_count",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "is_concretized_by",
        "is_public_metrics_of",
    }

    # Data properties
    retweet_count: Optional[
        Annotated[
            int,
            Field(
                description="The number of times a tweet has been retweeted, as exposed by the X v2 `public_metrics.retweet_count` field."
            ),
        ]
    ] = None
    reply_count: Optional[
        Annotated[
            int,
            Field(
                description="The number of replies to a tweet, as exposed by the X v2 `public_metrics.reply_count` field."
            ),
        ]
    ] = None
    like_count: Optional[
        Annotated[
            int,
            Field(
                description="The number of likes received by a tweet, as exposed by the X v2 `public_metrics.like_count` field."
            ),
        ]
    ] = None
    quote_count: Optional[
        Annotated[
            int,
            Field(
                description="The number of quote tweets referencing this tweet, as exposed by the X v2 `public_metrics.quote_count` field."
            ),
        ]
    ] = None
    bookmark_count: Optional[
        Annotated[
            int,
            Field(
                description="The number of times a tweet has been bookmarked, as exposed by the X v2 `public_metrics.bookmark_count` field."
            ),
        ]
    ] = None
    impression_count: Optional[
        Annotated[
            int,
            Field(
                description="The number of times a tweet has been viewed by users, as exposed by the X v2 `public_metrics.impression_count` field."
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
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_public_metrics_of: Optional[
        Annotated[
            List[Union[Tweet, URIRef, str]],
            Field(
                description="Relates a public engagement metrics artifact to the tweet on which it depends."
            ),
        ]
    ] = None


class XUserPublicMetrics(GenericallyDependentContinuant, RDFEntity):
    """
    X User Public Metrics
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/XUserPublicMetrics"
    _name: ClassVar[str] = "X User Public Metrics"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "followers_count": "http://ontology.naas.ai/x/followers_count",
        "following_count": "http://ontology.naas.ai/x/following_count",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_user_public_metrics_of": "http://ontology.naas.ai/x/isUserPublicMetricsOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "listed_count": "http://ontology.naas.ai/x/listed_count",
        "user_like_count": "http://ontology.naas.ai/x/user_like_count",
        "user_media_count": "http://ontology.naas.ai/x/user_media_count",
        "user_tweet_count": "http://ontology.naas.ai/x/user_tweet_count",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "is_concretized_by",
        "is_user_public_metrics_of",
    }

    # Data properties
    followers_count: Optional[
        Annotated[
            int,
            Field(
                description="The number of followers of the X user account, as exposed by the X v2 `public_metrics.followers_count` field on User objects."
            ),
        ]
    ] = None
    following_count: Optional[
        Annotated[
            int,
            Field(
                description="The number of accounts the X user follows, as exposed by the X v2 `public_metrics.following_count` field on User objects."
            ),
        ]
    ] = None
    user_tweet_count: Optional[
        Annotated[
            int,
            Field(
                description="The number of tweets posted by the X user account, as exposed by the X v2 `public_metrics.tweet_count` field on User objects."
            ),
        ]
    ] = None
    listed_count: Optional[
        Annotated[
            int,
            Field(
                description="The number of public lists the X user account appears on, as exposed by the X v2 `public_metrics.listed_count` field on User objects."
            ),
        ]
    ] = None
    user_like_count: Optional[
        Annotated[
            int,
            Field(
                description="The number of tweets liked by the X user account, as exposed by the X v2 `public_metrics.like_count` field on User objects."
            ),
        ]
    ] = None
    user_media_count: Optional[
        Annotated[
            int,
            Field(
                description="The number of media items posted by the X user account, as exposed by the X v2 `public_metrics.media_count` field on User objects."
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
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_user_public_metrics_of: Optional[
        Annotated[
            List[Union[URIRef, XUser, str]],
            Field(
                description="Relates a public account metrics artifact to the X user account on which it depends."
            ),
        ]
    ] = None


class Media(GenericallyDependentContinuant, RDFEntity):
    """
    Media
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/Media"
    _name: ClassVar[str] = "Media"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "duration_ms": "http://ontology.naas.ai/x/duration_ms",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_attached_media_of": "http://ontology.naas.ai/x/isAttachedMediaOf",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "media_height": "http://ontology.naas.ai/x/media_height",
        "media_key": "http://ontology.naas.ai/x/media_key",
        "media_type": "http://ontology.naas.ai/x/media_type",
        "media_url": "http://ontology.naas.ai/x/media_url",
        "media_width": "http://ontology.naas.ai/x/media_width",
        "preview_image_url": "http://ontology.naas.ai/x/preview_image_url",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "is_attached_media_of",
        "is_concretized_by",
    }

    # Data properties
    media_key: Optional[
        Annotated[
            str,
            Field(
                description="The unique key of a media artifact on the X platform; corresponds to the `media_key` field of the X v2 Media object."
            ),
        ]
    ] = None
    media_type: Optional[
        Annotated[
            str,
            Field(
                description="The kind of media artifact ('photo', 'video', 'animated_gif'); corresponds to the `type` field of the X v2 Media object."
            ),
        ]
    ] = None
    media_url: Optional[
        Annotated[
            str,
            Field(
                description="Direct URL of the media content (photos); corresponds to the `url` field of the X v2 Media object."
            ),
        ]
    ] = None
    preview_image_url: Optional[
        Annotated[
            str,
            Field(
                description="URL of the static preview image of a video or animated gif; corresponds to the `preview_image_url` field of the X v2 Media object."
            ),
        ]
    ] = None
    media_width: Optional[
        Annotated[
            int,
            Field(
                description="Width of the media artifact in pixels; corresponds to the `width` field of the X v2 Media object."
            ),
        ]
    ] = None
    media_height: Optional[
        Annotated[
            int,
            Field(
                description="Height of the media artifact in pixels; corresponds to the `height` field of the X v2 Media object."
            ),
        ]
    ] = None
    duration_ms: Optional[
        Annotated[
            int,
            Field(
                description="Duration of a video or animated gif in milliseconds; corresponds to the `duration_ms` field of the X v2 Media object."
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
    is_attached_media_of: Optional[
        Annotated[
            List[Union[Tweet, URIRef, str]],
            Field(
                description="Relates a media artifact to a tweet to which it is attached."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None


class ContextAnnotation(GenericallyDependentContinuant, RDFEntity):
    """
    Context Annotation
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/ContextAnnotation"
    _name: ClassVar[str] = "Context Annotation"
    _property_uris: ClassVar[dict] = {
        "context_domain_description": "http://ontology.naas.ai/x/context_domain_description",
        "context_domain_id": "http://ontology.naas.ai/x/context_domain_id",
        "context_domain_name": "http://ontology.naas.ai/x/context_domain_name",
        "context_entity_description": "http://ontology.naas.ai/x/context_entity_description",
        "context_entity_id": "http://ontology.naas.ai/x/context_entity_id",
        "context_entity_name": "http://ontology.naas.ai/x/context_entity_name",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_context_annotation_of": "http://ontology.naas.ai/x/isContextAnnotationOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "is_concretized_by",
        "is_context_annotation_of",
    }

    # Data properties
    context_domain_id: Optional[
        Annotated[
            str,
            Field(
                description="Id of the classification domain of a context annotation; corresponds to `context_annotations[].domain.id` in the X v2 API."
            ),
        ]
    ] = None
    context_domain_name: Optional[
        Annotated[
            str,
            Field(
                description="Name of the classification domain of a context annotation; corresponds to `context_annotations[].domain.name` in the X v2 API."
            ),
        ]
    ] = None
    context_domain_description: Optional[
        Annotated[
            str,
            Field(
                description="Description of the classification domain of a context annotation; corresponds to `context_annotations[].domain.description` in the X v2 API."
            ),
        ]
    ] = None
    context_entity_id: Optional[
        Annotated[
            str,
            Field(
                description="Id of the entity recognized by a context annotation; corresponds to `context_annotations[].entity.id` in the X v2 API."
            ),
        ]
    ] = None
    context_entity_name: Optional[
        Annotated[
            str,
            Field(
                description="Name of the entity recognized by a context annotation; corresponds to `context_annotations[].entity.name` in the X v2 API."
            ),
        ]
    ] = None
    context_entity_description: Optional[
        Annotated[
            str,
            Field(
                description="Description of the entity recognized by a context annotation; corresponds to `context_annotations[].entity.description` in the X v2 API."
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
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_context_annotation_of: Optional[
        Annotated[
            List[Union[Tweet, URIRef, str]],
            Field(description="Relates a context annotation to a tweet it classifies."),
        ]
    ] = None


class TweetURL(GenericallyDependentContinuant, RDFEntity):
    """
    Tweet URL
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/TweetUrl"
    _name: ClassVar[str] = "Tweet URL"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "display_url": "http://ontology.naas.ai/x/display_url",
        "expanded_url": "http://ontology.naas.ai/x/expanded_url",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "is_url_entity_of": "http://ontology.naas.ai/x/isUrlEntityOf",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "unwound_url": "http://ontology.naas.ai/x/unwound_url",
        "url": "http://ontology.naas.ai/x/url",
        "url_description": "http://ontology.naas.ai/x/url_description",
        "url_title": "http://ontology.naas.ai/x/url_title",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "is_concretized_by",
        "is_url_entity_of",
    }

    # Data properties
    url: Optional[
        Annotated[
            str,
            Field(
                description="The shortened t.co URL as it appears in the tweet text; corresponds to `entities.urls[].url` in the X v2 API."
            ),
        ]
    ] = None
    expanded_url: Optional[
        Annotated[
            str,
            Field(
                description="The fully resolved destination URL; corresponds to `entities.urls[].expanded_url` in the X v2 API."
            ),
        ]
    ] = None
    display_url: Optional[
        Annotated[
            str,
            Field(
                description="The truncated URL as displayed in the tweet; corresponds to `entities.urls[].display_url` in the X v2 API."
            ),
        ]
    ] = None
    unwound_url: Optional[
        Annotated[
            str,
            Field(
                description="The final unrolled URL after following redirects; corresponds to `entities.urls[].unwound_url` in the X v2 API."
            ),
        ]
    ] = None
    url_title: Optional[
        Annotated[
            str,
            Field(
                description="The HTML title of the linked page; corresponds to `entities.urls[].title` in the X v2 API."
            ),
        ]
    ] = None
    url_description: Optional[
        Annotated[
            str,
            Field(
                description="The HTML meta description of the linked page; corresponds to `entities.urls[].description` in the X v2 API."
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
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_url_entity_of: Optional[
        Annotated[
            List[Union[Tweet, URIRef, str]],
            Field(
                description="Relates a URL entity to a tweet whose text contains it."
            ),
        ]
    ] = None


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
    query_string: Optional[
        Annotated[
            str,
            Field(
                description="The X v2 search query expression (1-4096 chars) submitted as the `query` parameter to GET /2/tweets/search/recent."
            ),
        ]
    ] = None
    start_time: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="The oldest UTC timestamp (inclusive) bounding the search window, sent as the `start_time` parameter."
            ),
        ]
    ] = None
    end_time: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="The newest UTC timestamp (exclusive) bounding the search window, sent as the `end_time` parameter."
            ),
        ]
    ] = None
    since_id: Optional[
        Annotated[
            str,
            Field(
                description="Lower-exclusive tweet-id bound: only tweets with an id greater than this value are returned."
            ),
        ]
    ] = None
    until_id: Optional[
        Annotated[
            str,
            Field(
                description="Upper-exclusive tweet-id bound: only tweets with an id less than this value are returned."
            ),
        ]
    ] = None
    max_results: Optional[
        Annotated[
            int,
            Field(
                description="Maximum number of tweets to return per page (10-100) when querying GET /2/tweets/search/recent."
            ),
        ]
    ] = None
    sort_order: Optional[
        Annotated[
            str,
            Field(
                description="Sort order requested for returned tweets: either 'recency' or 'relevancy'."
            ),
        ]
    ] = None
    max_pages: Optional[
        Annotated[
            int,
            Field(
                description="Maximum number of result pages to fetch from the X v2 endpoint during a single search process."
            ),
        ]
    ] = None
    tweet_fields: Optional[
        Annotated[
            str,
            Field(
                description="Comma-joined list of fields to include on each Tweet object, sent as the `tweet.fields` parameter."
            ),
        ]
    ] = None
    expansions: Optional[
        Annotated[
            str,
            Field(
                description="Comma-joined list of object expansions to apply, sent as the `expansions` parameter."
            ),
        ]
    ] = None
    media_fields: Optional[
        Annotated[
            str,
            Field(
                description="Comma-joined list of fields on expanded Media objects, sent as the `media.fields` parameter."
            ),
        ]
    ] = None
    poll_fields: Optional[
        Annotated[
            str,
            Field(
                description="Comma-joined list of fields on expanded Poll objects, sent as the `poll.fields` parameter."
            ),
        ]
    ] = None
    user_fields: Optional[
        Annotated[
            str,
            Field(
                description="Comma-joined list of fields on expanded User objects, sent as the `user.fields` parameter."
            ),
        ]
    ] = None
    place_fields: Optional[
        Annotated[
            str,
            Field(
                description="Comma-joined list of fields on expanded Place objects, sent as the `place.fields` parameter."
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
    has_search_query_role: Optional[
        Annotated[
            List[Union[SearchQueryRole, URIRef, str]],
            Field(
                description="Relates a search query artifact to a search query role that concretizes it during search execution."
            ),
        ]
    ] = None
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None
    is_search_query_of: Optional[
        Annotated[
            List[Union[SearchRecentTweets, URIRef, str]],
            Field(
                description="Relates a search query artifact to the recent-tweet search process that executes it."
            ),
        ]
    ] = None


class SearchResultSet(GenericallyDependentContinuant, RDFEntity):
    """
    Search Result Set
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/SearchResultSet"
    _name: ClassVar[str] = "Search Result Set"
    _property_uris: ClassVar[dict] = {
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
        "result_count": "http://ontology.naas.ai/x/result_count",
        "result_set_id": "http://ontology.naas.ai/x/result_set_id",
    }
    _object_properties: ClassVar[set[str]] = {
        "contains_tweet",
        "generically_depends_on",
        "is_concretized_by",
        "is_produced_by",
    }

    # Data properties
    result_set_id: Optional[
        Annotated[
            str,
            Field(
                description="Short hash identifying the search result set in the local datastore; an 8-character hex digest of the sorted parameter dictionary used as the cache key and filename."
            ),
        ]
    ] = None
    result_count: Optional[
        Annotated[
            int,
            Field(description="Number of tweets contained in the search result set."),
        ]
    ] = None
    file_path: Optional[
        Annotated[
            str,
            Field(
                description="Path to the JSON envelope file in object storage that persists the query, options and merged results backing this search result set."
            ),
        ]
    ] = None
    newest_id: Optional[
        Annotated[
            str,
            Field(
                description="Id of the most recent tweet in the result set, as exposed by the X v2 `meta.newest_id` field."
            ),
        ]
    ] = None
    oldest_id: Optional[
        Annotated[
            str,
            Field(
                description="Id of the oldest tweet in the result set, as exposed by the X v2 `meta.oldest_id` field."
            ),
        ]
    ] = None
    next_token: Optional[
        Annotated[
            str,
            Field(
                description="Pagination token to retrieve the next page of results, as exposed by the X v2 `meta.next_token` field."
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
    contains_tweet: Optional[
        Annotated[
            List[Union[Tweet, URIRef, str]],
            Field(description="Relates a search result set to a tweet it contains."),
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
    is_produced_by: Optional[
        Annotated[
            List[Union[Process, SearchRecentTweets, URIRef, str]],
            Field(
                description="Relates a search result set to the process that produced it."
            ),
        ]
    ] = None


class TweetFile(GenericallyDependentContinuant, RDFEntity):
    """
    Tweet File
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/TweetFile"
    _name: ClassVar[str] = "Tweet File"
    _property_uris: ClassVar[dict] = {
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "file_size_bytes": "http://ontology.naas.ai/x/file_size_bytes",
        "generically_depends_on": "http://ontology.naas.ai/abi/genericallyDependsOn",
        "is_concretized_by": "http://ontology.naas.ai/abi/isConcretizedBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "object_storage_key": "http://ontology.naas.ai/x/object_storage_key",
        "object_storage_prefix": "http://ontology.naas.ai/x/object_storage_prefix",
        "sha256": "http://ontology.naas.ai/x/sha256",
    }
    _object_properties: ClassVar[set[str]] = {
        "generically_depends_on",
        "is_concretized_by",
    }

    # Data properties
    sha256: Optional[
        Annotated[
            str,
            Field(
                description="SHA-256 hex digest of the tweet dataset file bytes; used for deduplication before ingestion."
            ),
        ]
    ] = None
    object_storage_prefix: Optional[
        Annotated[
            str,
            Field(
                description="Object-storage prefix under which the tweet dataset file is stored."
            ),
        ]
    ] = None
    object_storage_key: Optional[
        Annotated[
            str,
            Field(
                description="Object key of the tweet dataset file under its storage prefix."
            ),
        ]
    ] = None
    file_size_bytes: Optional[
        Annotated[int, Field(description="Size of the tweet dataset file in bytes.")]
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
    is_concretized_by: Optional[
        Annotated[
            List[Union[Disposition, Process, Quality, Role, URIRef, str]],
            Field(description="c is concretized by b =Def b concretizes c"),
        ]
    ] = None


class TweetLanguage(Quality, RDFEntity):
    """
    Tweet Language
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/TweetLanguage"
    _name: ClassVar[str] = "Tweet Language"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "inheresIn": "http://ontology.naas.ai/abi/inheresIn",
        "inheres_in": "http://ontology.naas.ai/abi/inheresIn",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "language_code": "http://ontology.naas.ai/x/lang",
        "participates_in": "http://ontology.naas.ai/abi/participatesIn",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "inheresIn",
        "inheres_in",
        "participates_in",
    }

    # Data properties
    language_code: Optional[
        Annotated[
            str,
            Field(
                description="The IETF BCP 47 language tag detected for a tweet's text content; corresponds to the `lang` field returned by the X v2 API."
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
    concretizes: Optional[
        Annotated[
            List[Union[GenericallyDependentContinuant, URIRef, str]],
            Field(
                description="b concretizes c =Def b is a process or a specifically dependent continuant & c is a generically dependent continuant & there is some time t such that c is the pattern or content which b shares at t with actual or potential copies"
            ),
        ]
    ] = None
    inheresIn: Optional[Annotated[List[Union[Tweet, URIRef, str]], Field()]] = None
    inheres_in: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
    ] = None
    participates_in: Optional[
        Annotated[
            List[Union[Process, URIRef, str]],
            Field(
                description="(Elucidation) participates in holds between some b that is either a specifically dependent continuant or generically dependent continuant or independent continuant that is not a spatial region & some process p such that b participates in p some way"
            ),
        ]
    ] = None


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
    has_realization: Optional[
        Annotated[
            List[Union[Process, URIRef, str]],
            Field(description="b has realization c =Def c realizes b"),
        ]
    ] = None
    inheres_in: Optional[
        Annotated[
            List[Union[MaterialEntity, URIRef, str]],
            Field(
                description="b inheres in c =Def b is a specifically dependent continuant & c is an independent continuant that is not a spatial region & b specifically depends on c"
            ),
        ]
    ] = None
    is_search_query_role_of: Optional[
        Annotated[
            List[Union[SearchQuery, URIRef, str]],
            Field(
                description="Relates a search query role to the search query artifact in which it inheres."
            ),
        ]
    ] = None


class TweetFileImport(Process, RDFEntity):
    """
    Tweet File Import
    """

    _class_uri: ClassVar[str] = "http://ontology.naas.ai/x/TweetFileImport"
    _name: ClassVar[str] = "Tweet File Import"
    _property_uris: ClassVar[dict] = {
        "concretizes": "http://ontology.naas.ai/abi/concretizes",
        "created": "http://purl.org/dc/terms/created",
        "creator": "http://purl.org/dc/terms/creator",
        "has_participant": "http://ontology.naas.ai/abi/hasParticipant",
        "has_search_interval": "http://ontology.naas.ai/x/hasSearchInterval",
        "imports_file": "http://ontology.naas.ai/x/imports_file",
        "is_preceded_by": "http://ontology.naas.ai/x/isPrecededBy",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
        "occupies_temporal_region": "http://ontology.naas.ai/abi/occupiesTemporalRegion",
        "occurs_in": "http://ontology.naas.ai/abi/occursIn",
        "realizes": "http://ontology.naas.ai/abi/realizes",
    }
    _object_properties: ClassVar[set[str]] = {
        "concretizes",
        "has_participant",
        "has_search_interval",
        "imports_file",
        "is_preceded_by",
        "occupies_temporal_region",
        "occurs_in",
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
    has_search_interval: Optional[
        Annotated[
            List[Union[SearchInterval, URIRef, str]],
            Field(
                description="Relates an X process to the temporal interval that bounds its execution, carrying a first instant (searchStartedAt) and a last instant (searchEndedAt)."
            ),
        ]
    ] = None
    imports_file: Optional[
        Annotated[
            List[Union[TweetFile, URIRef, str]],
            Field(
                description="Relates a tweet-file import process to the tweet dataset file it reads from object storage."
            ),
        ]
    ] = None
    is_preceded_by: Optional[
        Annotated[
            List[Union[SearchRecentTweets, URIRef, str]],
            Field(
                description="Relates a process to another process that precedes it temporally; sub-property of BFO preceded_by (BFO_0000062)."
            ),
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
    realizes: Optional[
        Annotated[
            List[Union[Disposition, Role, URIRef, str]],
            Field(
                description="(Elucidation) realizes is a relation between a process b and realizable entity c such that c inheres in some d & for all t, if b has participant d then c exists & the type instantiated by b is correlated with the type instantiated by c"
            ),
        ]
    ] = None


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
        "retrieves_tweet",
        "retrieves_user",
        "uses_search_query",
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
    executed_at: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(
                description="Relates a recent-tweet search process to the temporal instant at which the API call was issued."
            ),
        ]
    ] = None
    executed_by: Optional[
        Annotated[
            List[Union[URIRef, XUser, str]],
            Field(
                description="Relates a recent-tweet search process to the X user account on whose behalf the API call was made."
            ),
        ]
    ] = None
    has_participant: Optional[
        Annotated[
            List[Union[MaterialEntity, Quality, URIRef, str]],
            Field(description="p has participant c =Def c participates in p"),
        ]
    ] = None
    has_search_interval: Optional[
        Annotated[
            List[Union[SearchInterval, URIRef, str]],
            Field(
                description="Relates an X process to the temporal interval that bounds its execution, carrying a first instant (searchStartedAt) and a last instant (searchEndedAt)."
            ),
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
    occursIn: Optional[Annotated[List[Union[URIRef, XPlatform, str]], Field()]] = None
    occurs_in: Optional[
        Annotated[
            List[Union[Site, URIRef, str]],
            Field(
                description="b occurs in c =Def b is a process or a process boundary & c is a material entity or site & there exists a spatiotemporal region r & b occupies spatiotemporal region r & for all time t, if b exists at t then c exists at t & there exist spatial regions s and s' where b spatially projects onto s at t & c occupies spatial region s' at t & s is a continuant part of s' at t"
            ),
        ]
    ] = None
    produces_search_result: Optional[
        Annotated[
            List[Union[SearchResultSet, URIRef, str]],
            Field(
                description="Relates a tweet-ingestion process to the search result set it produces."
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
    retrieves_media: Optional[
        Annotated[
            List[Union[Media, URIRef, str]],
            Field(
                description="Relates a recent-tweet search process to a media artifact expanded in its response (the `includes.media` of the X v2 search response)."
            ),
        ]
    ] = None
    retrieves_tweet: Optional[
        Annotated[
            List[Union[Tweet, URIRef, str]],
            Field(
                description="Relates a recent-tweet search process to a tweet it retrieved from the X v2 search response (the matched `data` tweets)."
            ),
        ]
    ] = None
    retrieves_user: Optional[
        Annotated[
            List[Union[URIRef, XUser, str]],
            Field(
                description="Relates a recent-tweet search process to an X user account expanded in its response (the `includes.users` of the X v2 search response)."
            ),
        ]
    ] = None
    uses_search_query: Optional[
        Annotated[
            List[Union[SearchQuery, URIRef, str]],
            Field(
                description="Relates a recent-tweet search process to the search query artifact it executes against the X v2 API."
            ),
        ]
    ] = None


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
    search_ended_at: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(
                description="Relates a search interval to the temporal instant at which the search process completed."
            ),
        ]
    ] = None
    search_started_at: Optional[
        Annotated[
            List[Union[TemporalInstant, URIRef, str]],
            Field(
                description="Relates a search interval to the temporal instant at which the search process started."
            ),
        ]
    ] = None


# Rebuild models to resolve forward references
XPlatform.model_rebuild()
XUser.model_rebuild()
Tweet.model_rebuild()
TweetPublicMetrics.model_rebuild()
XUserPublicMetrics.model_rebuild()
Media.model_rebuild()
ContextAnnotation.model_rebuild()
TweetURL.model_rebuild()
SearchQuery.model_rebuild()
SearchResultSet.model_rebuild()
TweetFile.model_rebuild()
TweetLanguage.model_rebuild()
SearchQueryRole.model_rebuild()
TweetFileImport.model_rebuild()
SearchRecentTweets.model_rebuild()
SearchInterval.model_rebuild()
