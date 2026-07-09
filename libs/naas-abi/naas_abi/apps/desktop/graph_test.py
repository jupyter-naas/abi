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
