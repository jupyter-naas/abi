"""Unit tests for DesktopGraph (embedded Oxigraph)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from desktop.graph import ABID, DesktopGraph, tag_intent_from_text


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
    assert graph.stats() == {"triples": 0, "system_loaded": False}
    graph.record_chat(_chat())
    assert graph.stats()["triples"] == 4
    assert graph.stats()["system_loaded"] is False


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
    assert loaded["system"]["loaded_files"]
    assert graph.stats()["active_context"] == {"org": "acme", "model": "coder"}
    assert graph.stats()["system_loaded"] is True

    result = graph.query(
        "SELECT ?s WHERE { GRAPH <http://ontology.naas.ai/abi/desktop#context/acme/coder> { ?s ?p ?o } }"
    )
    assert result["type"] == "solutions"
    assert len(result["rows"]) >= 2


def test_load_system_ontology_loads_bfo7_and_routing_vocab(
    graph: DesktopGraph,
) -> None:
    loaded = graph.load_system_ontology()
    assert loaded["reused"] is False
    assert "desktop-routing.ttl" in loaded["loaded_files"]
    assert any(
        name.endswith("BFO7BucketsProcessOntology.ttl")
        for name in loaded["loaded_files"]
    )
    assert loaded["system_triples"] > 50
    ask = graph.query(
        "ASK { GRAPH <http://ontology.naas.ai/abi/desktop#system> { "
        "<http://ontology.naas.ai/abi/desktop#SectionRoute> ?p ?o } }"
    )
    assert ask == {"type": "boolean", "value": True}


def test_resolve_route_agent_from_scaffolded_context(
    graph: DesktopGraph, tmp_path: Path
) -> None:
    from desktop.workspace_layout import scaffold_org_model

    workspace = tmp_path / "ws"
    workspace.mkdir()
    context = scaffold_org_model(workspace, "acme", "coder")
    graph.load_org_model_context("acme", "coder", context)

    assert graph.resolve_route_agent("acme", "coder", "chat") == "plan"
    assert graph.resolve_route_agent("acme", "coder", "code") == "build"
    assert graph.resolve_route_agent("acme", "coder", "other") is None


def test_query_section_route_returns_bfo_bucket_label(
    graph: DesktopGraph, tmp_path: Path
) -> None:
    from desktop.workspace_layout import scaffold_org_model

    workspace = tmp_path / "ws"
    workspace.mkdir()
    context = scaffold_org_model(workspace, "default", "default")
    graph.load_org_model_context("default", "default", context)

    route = graph.query_section_route("default", "default", "chat")
    assert route is not None
    assert route["agent"] == "plan"
    assert route.get("harness") == "opencode"
    assert route.get("bucketLabel") == "role"


def test_resolve_route_returns_agent_model_hint_and_bucket(
    graph: DesktopGraph, tmp_path: Path
) -> None:
    from desktop.workspace_layout import scaffold_org_model

    workspace = tmp_path / "ws"
    workspace.mkdir()
    context = scaffold_org_model(workspace, "acme", "coder")
    instances = (context / "instances.ttl").read_text(encoding="utf-8")
    (context / "instances.ttl").write_text(
        instances.replace(
            'abid:usesHarness "opencode" ;',
            'abid:usesHarness "opencode" ;\n    abid:harnessModel "ollama/qwen2.5-coder" ;',
            1,
        ),
        encoding="utf-8",
    )
    graph.load_org_model_context("acme", "coder", context)

    chat_route = graph.resolve_route("acme", "coder", "chat")
    assert chat_route is not None
    assert chat_route["agent"] == "plan"
    assert chat_route["model_hint"] == "ollama/qwen2.5-coder"
    assert chat_route["harness"] == "opencode"
    assert chat_route["bucket_label"] == "role"

    code_route = graph.resolve_route("acme", "coder", "code")
    assert code_route is not None
    assert code_route["agent"] == "build"
    assert code_route["bucket_label"] == "process"


def test_active_routing_summary_returns_both_intents(
    graph: DesktopGraph, tmp_path: Path
) -> None:
    from desktop.workspace_layout import scaffold_org_model

    workspace = tmp_path / "ws"
    workspace.mkdir()
    context = scaffold_org_model(workspace, "default", "default")
    graph.load_org_model_context("default", "default", context)

    summary = graph.active_routing_summary("default", "default")
    assert summary["org"] == "default"
    assert summary["chat"]["agent"] == "plan"
    assert summary["code"]["agent"] == "build"
    assert len(summary["language_models"]) >= 2
    refs = {item["model_ref"] for item in summary["language_models"]}
    assert "ollama/qwen2.5-coder:7b" in refs


def test_build_routing_prompt_hint_includes_agent_and_bucket(
    graph: DesktopGraph, tmp_path: Path
) -> None:
    from desktop.workspace_layout import scaffold_org_model

    workspace = tmp_path / "ws"
    workspace.mkdir()
    context = scaffold_org_model(workspace, "default", "default")
    graph.load_org_model_context("default", "default", context)

    hint = graph.build_routing_prompt_hint("default", "default", "chat")
    assert "Harness agent: `plan`" in hint
    assert "BFO7 bucket: role" in hint
    assert "Harness: `opencode`" in hint


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


def test_tag_intent_from_text_detects_code_and_plan() -> None:
    assert tag_intent_from_text("refactor this python file") == ["code"]
    assert tag_intent_from_text("plan the system architecture") == ["plan"]
    assert tag_intent_from_text("hello") == ["general"]


def test_suggest_models_prefers_local_for_code_intent(
    graph: DesktopGraph, tmp_path: Path
) -> None:
    from desktop.workspace_layout import scaffold_org_model

    workspace = tmp_path / "ws"
    workspace.mkdir()
    context = scaffold_org_model(workspace, "default", "default")
    graph.load_org_model_context("default", "default", context)

    suggestions = graph.suggest_models(
        ["code"], prefer_local=True, org="default", model="default"
    )
    assert len(suggestions) >= 1
    assert suggestions[0].model_ref == "ollama/qwen2.5-coder:7b"
    assert suggestions[0].hosted_at == "local"
    assert "process" in suggestions[0].reason.lower()


def test_suggest_models_returns_cloud_for_plan_when_only_cloud_realizes_role(
    graph: DesktopGraph, tmp_path: Path
) -> None:
    from desktop.workspace_layout import scaffold_org_model

    workspace = tmp_path / "ws"
    workspace.mkdir()
    context = scaffold_org_model(workspace, "default", "default")
    graph.load_org_model_context("default", "default", context)

    suggestions = graph.suggest_models(
        ["plan"], prefer_local=True, org="default", model="default"
    )
    assert len(suggestions) == 1
    assert suggestions[0].model_ref == "openai/gpt-5"
    assert suggestions[0].hosted_at == "cloud"
    assert "role" in suggestions[0].reason.lower()


def test_suggest_models_fixture_filters_non_tool_models(
    graph: DesktopGraph, tmp_path: Path
) -> None:
    context = tmp_path / "ctx"
    context.mkdir()
    (context / "instances.ttl").write_text(
        """@prefix abi: <http://ontology.naas.ai/abi/> .
@prefix ctx: <http://ontology.naas.ai/abi/desktop/acme/router#> .
@prefix bfo: <http://purl.obolibrary.org/obo/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ctx:modelNoTools a abi:LanguageModel ;
    abi:hostedAt abi:SiteLocal ;
    abi:supportsTools false ;
    abi:canRealize bfo:BFO_0000015 ;
    abi:modelRef "ollama/phi:latest" .

ctx:modelTools a abi:LanguageModel ;
    abi:hostedAt abi:SiteLocal ;
    abi:supportsTools true ;
    abi:canRealize bfo:BFO_0000015 ;
    abi:modelRef "ollama/qwen2.5-coder:7b" .
""",
        encoding="utf-8",
    )
    graph.load_org_model_context("acme", "router", context)

    suggestions = graph.suggest_models(
        ["code"], prefer_local=True, org="acme", model="router"
    )
    assert [s.model_ref for s in suggestions] == ["ollama/qwen2.5-coder:7b"]
