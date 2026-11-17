"""Matched vs referenced tweets must land in distinct classes.

Exercised through :class:`XTweetGraphBuilder` rather than the pipeline, over a
stub triple store, so the assertions need no engine.
"""

import pytest
from naas_abi_apps.x.ontologies.modules.XOntology import (
    ReferencedTweet,
    Tweet,
)
from naas_abi_apps.x.pipelines.utils._graph_builder import (
    XTweetGraphBuilder,
)
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

X = Namespace("http://ontology.naas.ai/x/")
RESULT_SET = f"{X}SearchResultSet/test"


def _tweet(tweet_id: str, text: str, lang: str = "en", **fields) -> dict:
    return {"id": tweet_id, "text": text, "lang": lang, "author_id": "7", **fields}


# A search response in the shape X returns (the in-engine test read a recorded
# one that is not in the repository): 3 matched tweets in ``data`` and 5 in
# ``includes.tweets``, a superset carrying the 3 matches and 2 context tweets.
_MATCHED = [
    _tweet(
        "300",
        "OpenAI ships a model",
        referenced_tweets=[{"type": "quoted", "id": "100"}],
        public_metrics={"like_count": 5, "retweet_count": 1},
        entities={
            "urls": [{"url": "https://t.co/a", "expanded_url": "https://openai.com"}]
        },
    ),
    _tweet(
        "200",
        "Anthropic replies",
        referenced_tweets=[{"type": "replied_to", "id": "50"}],
        context_annotations=[
            {
                "domain": {"id": "46", "name": "Business"},
                "entity": {"id": "9", "name": "AI"},
            }
        ],
    ),
    _tweet("150", "An LLM thread", referenced_tweets=[{"type": "quoted", "id": "300"}]),
]
_CONTEXT = [
    _tweet("100", "Bonjour tout le monde", lang="fr"),
    _tweet("50", "What a day"),
]
ENVELOPE = {
    "query": "(openai OR anthropic) lang:en -is:retweet",
    "results": {
        "data": _MATCHED,
        "includes": {"tweets": [*_MATCHED, *_CONTEXT]},
        "meta": {"newest_id": "300", "oldest_id": "150", "result_count": 3},
    },
}


class _AskFalse:
    askAnswer = False


class _EmptyStore:
    """Triple store in which no individual exists yet."""

    def query(self, _sparql):
        return _AskFalse()


@pytest.fixture
def envelope() -> dict:
    return ENVELOPE


@pytest.fixture
def builder() -> XTweetGraphBuilder:
    return XTweetGraphBuilder(
        _EmptyStore(),  # type: ignore[arg-type]
        "http://example.org/graph",
        ontology_namespace=str(X),
    )


def _split(envelope: dict) -> tuple[list[dict], list[dict]]:
    """Partition the envelope the way the pipeline does."""
    results = envelope["results"]
    data = results["data"]
    expanded = results["includes"]["tweets"]
    matched_ids = {str(r["id"]) for r in data if r.get("id")}
    referenced = [
        r for r in expanded if r.get("id") and str(r["id"]) not in matched_ids
    ]
    return data, referenced


def _build(builder: XTweetGraphBuilder, envelope: dict) -> Graph:
    data, referenced = _split(envelope)
    graph = Graph()
    for record in data:
        graph += builder.build_tweet(record, source_set_uri=RESULT_SET)
    for record in referenced:
        graph += builder.build_tweet(record, source_set_uri=RESULT_SET, referenced=True)
    return graph


def test_expanded_tweets_are_a_superset_of_the_matches(envelope: dict):
    """``includes.tweets`` repeats every match, so only the rest is context."""
    data, referenced = _split(envelope)
    expanded = envelope["results"]["includes"]["tweets"]
    assert len(data) == 3
    assert len(expanded) == 5
    assert len(referenced) == 2


def test_matched_and_referenced_tweets_get_distinct_classes(
    builder: XTweetGraphBuilder, envelope: dict
):
    graph = _build(builder, envelope)
    tweets = set(graph.subjects(RDF.type, URIRef(Tweet._class_uri)))
    referenced = set(graph.subjects(RDF.type, URIRef(ReferencedTweet._class_uri)))

    # Every ingested post carries x:Tweet — x:ReferencedTweet is the subset
    # that only came back as context. Nothing reasons over the store, so the
    # superclass has to be materialised for the subclass axiom to hold.
    assert len(tweets) == 5
    assert len(referenced) == 2
    assert referenced < tweets


def test_only_matches_are_linked_as_search_results(
    builder: XTweetGraphBuilder, envelope: dict
):
    graph = _build(builder, envelope)
    matched = set(graph.subjects(X.isContainedInSearchResultSet, URIRef(RESULT_SET)))
    context = set(
        graph.subjects(X.isReferencedTweetOfSearchResultSet, URIRef(RESULT_SET))
    )

    assert len(matched) == 3
    assert len(context) == 2
    # The two populations partition the ingested posts: counting result-set
    # membership must never pick up a context tweet.
    assert not matched & context


def test_every_referenced_tweet_is_referenced_by_a_match(envelope: dict):
    """Context tweets exist only because a match points at them."""
    data, referenced = _split(envelope)
    pointed_at = {
        str(ref["id"])
        for record in data
        for ref in (record.get("referenced_tweets") or [])
        if ref.get("id")
    }
    assert {str(r["id"]) for r in referenced} <= pointed_at


def test_referenced_tweet_need_not_match_the_query(envelope: dict):
    """The reason the split matters: context tweets fail the search filters.

    They are pulled in by id, so they routinely carry none of the query terms
    and can even sit outside the requested language.
    """
    _, referenced = _split(envelope)
    off_topic = [
        r
        for r in referenced
        if not any(
            term in r.get("text", "").lower() for term in ("openai", "anthropic", "llm")
        )
    ]
    assert len(off_topic) == 2
    assert any(r.get("lang") != "en" for r in referenced)


def test_result_set_link_survives_an_already_ingested_tweet(
    envelope: dict,
):
    """A tweet first seen as context must still gain its match link later.

    The dedup guard suppresses re-emitting the individual, but result-set
    membership is asserted unconditionally — otherwise a tweet ingested as
    context in an earlier run would silently drop out of the matched counts.
    """

    class _AskTrue:
        askAnswer = True

    class _FullStore:
        def query(self, _sparql):
            return _AskTrue()

    builder = XTweetGraphBuilder(
        _FullStore(),  # type: ignore[arg-type]
        "http://example.org/graph",
        ontology_namespace=str(X),
    )
    record = envelope["results"]["data"][0]
    graph = builder.build_tweet(record, source_set_uri=RESULT_SET)

    subject = URIRef(builder.uri("Tweet", str(record["id"])))
    assert (subject, X.isContainedInSearchResultSet, URIRef(RESULT_SET)) in graph
    # ...while the individual itself was not re-emitted.
    assert (subject, RDF.type, URIRef(Tweet._class_uri)) not in graph
