"""Matched vs referenced tweets must land in distinct classes.

Exercised through :class:`XTweetGraphBuilder` rather than the pipeline so the
assertions run without a loaded engine — the pipeline fixtures skip when no
module/triple store is available.
"""

import json
from pathlib import Path

import pytest
from naas_abi_marketplace.applications.x.ontologies.modules.XOntology import (
    ReferencedTweet,
    Tweet,
)
from naas_abi_marketplace.applications.x.pipelines.utils._graph_builder import (
    XTweetGraphBuilder,
)
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

X = Namespace("http://ontology.naas.ai/x/")
RESULT_SET = f"{X}SearchResultSet/test"

# A recorded X v2 search response: 28 matched tweets in ``data`` and 40 in
# ``includes.tweets``, the latter being a superset carrying 12 context tweets.
ARTIFACT = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "artifacts"
    / "2026-08-07T06_55_19.928677+00_00_"
    "(drone_or_drones_or_uas_or_uav)_lang_en_-is_retweet.json"
)


class _AskFalse:
    askAnswer = False


class _EmptyStore:
    """Triple store in which no individual exists yet."""

    def query(self, _sparql):
        return _AskFalse()


@pytest.fixture
def envelope() -> dict:
    if not ARTIFACT.exists():
        pytest.skip(f"search artifact not available: {ARTIFACT}")
    return json.loads(ARTIFACT.read_text())


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
    assert len(data) == 28
    assert len(expanded) == 40
    assert len(referenced) == 12


def test_matched_and_referenced_tweets_get_distinct_classes(
    builder: XTweetGraphBuilder, envelope: dict
):
    graph = _build(builder, envelope)
    tweets = set(graph.subjects(RDF.type, URIRef(Tweet._class_uri)))
    referenced = set(graph.subjects(RDF.type, URIRef(ReferencedTweet._class_uri)))

    # Every ingested post carries x:Tweet — x:ReferencedTweet is the subset
    # that only came back as context. Nothing reasons over the store, so the
    # superclass has to be materialised for the subclass axiom to hold.
    assert len(tweets) == 40
    assert len(referenced) == 12
    assert referenced < tweets


def test_only_matches_are_linked_as_search_results(
    builder: XTweetGraphBuilder, envelope: dict
):
    graph = _build(builder, envelope)
    matched = set(graph.subjects(X.isContainedInSearchResultSet, URIRef(RESULT_SET)))
    context = set(
        graph.subjects(X.isReferencedTweetOfSearchResultSet, URIRef(RESULT_SET))
    )

    assert len(matched) == 28
    assert len(context) == 12
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
            term in r.get("text", "").lower()
            for term in ("drone", "drones", "uas", "uav")
        )
    ]
    assert len(off_topic) == 9
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
