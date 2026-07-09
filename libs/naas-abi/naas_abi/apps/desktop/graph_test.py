"""Unit tests for DesktopGraph (embedded Oxigraph)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from desktop.graph import ABID, DesktopGraph


@pytest.fixture()
def graph(tmp_path: Path) -> Iterator[DesktopGraph]:
    g = DesktopGraph(tmp_path / "graph")
    yield g
    g.close()


def _chat(chat_id: str = "c1") -> dict:
    return {"id": chat_id, "title": "My chat", "section": "chat", "created_at": 1.0}


def _message(message_id: str = "m1", chat_id: str = "c1") -> dict:
    return {
        "id": message_id,
        "chat_id": chat_id,
        "role": "user",
        "content": "hello graph",
        "created_at": 2.0,
    }


def test_record_chat_creates_expected_triples(graph: DesktopGraph) -> None:
    graph.record_chat(_chat())
    result = graph.query(
        f"SELECT ?title WHERE {{ <{ABID}chat/c1> <{ABID}title> ?title }}"
    )
    assert result["type"] == "solutions"
    assert result["rows"] == [{"title": "My chat"}]


def test_record_message_links_to_chat(graph: DesktopGraph) -> None:
    graph.record_chat(_chat())
    graph.record_message(_message())
    result = graph.query(
        "SELECT ?content WHERE { "
        f"?m <{ABID}inChat> <{ABID}chat/c1> ; <{ABID}content> ?content }}"
    )
    assert result["rows"] == [{"content": "hello graph"}]


def test_message_content_truncated_to_2000_chars(graph: DesktopGraph) -> None:
    message = _message()
    message["content"] = "x" * 5000
    graph.record_message(message)
    result = graph.query(f"SELECT ?c WHERE {{ <{ABID}message/m1> <{ABID}content> ?c }}")
    assert len(result["rows"][0]["c"]) == 2000


def test_delete_chat_removes_chat_and_message_triples(graph: DesktopGraph) -> None:
    graph.record_chat(_chat())
    graph.record_message(_message())
    assert graph.stats()["triples"] > 0
    graph.delete_chat("c1")
    assert graph.stats()["triples"] == 0


def test_delete_chat_keeps_other_chats(graph: DesktopGraph) -> None:
    graph.record_chat(_chat("c1"))
    graph.record_chat(_chat("c2"))
    graph.record_message(_message("m1", "c1"))
    graph.record_message(_message("m2", "c2"))
    graph.delete_chat("c1")
    result = graph.query(f"SELECT ?m WHERE {{ ?m <{ABID}inChat> <{ABID}chat/c2> }}")
    assert result["rows"] == [{"m": f"{ABID}message/m2"}]


def test_ask_query_returns_boolean(graph: DesktopGraph) -> None:
    graph.record_chat(_chat())
    result = graph.query(f"ASK {{ <{ABID}chat/c1> ?p ?o }}")
    assert result == {"type": "boolean", "value": True}


def test_construct_query_returns_triples(graph: DesktopGraph) -> None:
    graph.record_chat(_chat())
    result = graph.query(
        f"CONSTRUCT {{ ?s <{ABID}title> ?t }} WHERE {{ ?s <{ABID}title> ?t }}"
    )
    assert result["type"] == "triples"
    assert result["triples"] == [
        {
            "subject": f"{ABID}chat/c1",
            "predicate": f"{ABID}title",
            "object": "My chat",
        }
    ]


def test_stats_counts_triples(graph: DesktopGraph) -> None:
    assert graph.stats() == {"triples": 0}
    graph.record_chat(_chat())
    assert graph.stats()["triples"] == 4


def test_load_org_model_context_ingests_ttl_files(
    graph: DesktopGraph, tmp_path: Path
) -> None:
    context = tmp_path / "acme" / "coder"
    context.mkdir(parents=True)
    (context / "ontology.ttl").write_text(
        "@prefix ex: <http://example.org/> .\nex:Thing a ex:Class .\n",
        encoding="utf-8",
    )
    (context / "instances.ttl").write_text(
        "@prefix ex: <http://example.org/> .\nex:item1 a ex:Thing .\n",
        encoding="utf-8",
    )

    loaded = graph.load_org_model_context("acme", "coder", context)
    assert loaded["org"] == "acme"
    assert loaded["model"] == "coder"
    assert set(loaded["loaded_files"]) == {"ontology.ttl", "instances.ttl"}
    assert loaded["context_triples"] >= 2
    assert graph.stats()["active_context"] == {"org": "acme", "model": "coder"}

    result = graph.query(
        "SELECT ?s WHERE { GRAPH <http://ontology.naas.ai/abi/desktop#context/acme/coder> { ?s ?p ?o } }"
    )
    assert result["type"] == "solutions"
    assert len(result["rows"]) >= 2


def test_load_org_model_context_replaces_previous_graph(
    graph: DesktopGraph, tmp_path: Path
) -> None:
    first = tmp_path / "org-a" / "m1"
    first.mkdir(parents=True)
    (first / "ontology.ttl").write_text(
        "@prefix ex: <http://example.org/a> .\nex:A a ex:Class .\n",
        encoding="utf-8",
    )
    second = tmp_path / "org-b" / "m2"
    second.mkdir(parents=True)
    (second / "ontology.ttl").write_text(
        "@prefix ex: <http://example.org/b> .\nex:B a ex:Class .\n",
        encoding="utf-8",
    )

    graph.load_org_model_context("org-a", "m1", first)
    graph.load_org_model_context("org-b", "m2", second)

    old = graph.query(
        "ASK { GRAPH <http://ontology.naas.ai/abi/desktop#context/org-a/m1> { ?s ?p ?o } }"
    )
    new = graph.query(
        "ASK { GRAPH <http://ontology.naas.ai/abi/desktop#context/org-b/m2> { ?s ?p ?o } }"
    )
    assert old == {"type": "boolean", "value": False}
    assert new == {"type": "boolean", "value": True}
