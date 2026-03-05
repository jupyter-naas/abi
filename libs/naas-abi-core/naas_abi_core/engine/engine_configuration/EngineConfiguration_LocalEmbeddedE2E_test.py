import threading

import numpy as np
import pytest
from rdflib import Graph, Literal, URIRef

from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)


def test_local_embedded_services_end_to_end(tmp_path):
    pytest.importorskip("pyoxigraph")
    pytest.importorskip("qdrant_client")

    env_path = tmp_path / ".env"
    env_path.write_text("ENV=local\n", encoding="utf-8")

    config_yaml = f"""
api:
  title: "ABI API"
  description: "API for ABI"
  logo_path: "assets/logo.png"
  favicon_path: "assets/favicon.ico"
  cors_origins:
    - "http://localhost:9879"

global_config:
  ai_mode: "cloud"

modules:
  - module: naas_abi
    enabled: true
    config: {{}}

services:
  secret:
    secret_adapters:
      - adapter: "dotenv"
        config:
          path: "{env_path.as_posix()}"
  object_storage:
    object_storage_adapter:
      adapter: "fs"
      config:
        base_path: "{(tmp_path / "datastore").as_posix()}"
  triple_store:
    triple_store_adapter:
      adapter: "oxigraph_embedded"
      config:
        store_path: "{(tmp_path / "triplestore").as_posix()}"
  vector_store:
    vector_store_adapter:
      adapter: "qdrant_in_memory"
      config:
        storage_path: "{(tmp_path / "vectorstore").as_posix()}"
  bus:
    bus_adapter:
      adapter: "python_queue"
      config:
        persistence_path: "{(tmp_path / "bus.sqlite3").as_posix()}"
  kv:
    kv_adapter:
      adapter: "python"
      config:
        persistence_path: "{(tmp_path / "kv.sqlite3").as_posix()}"
"""

    configuration = EngineConfiguration.from_yaml_content(config_yaml)

    kv = configuration.services.kv.load()
    kv.set("k", b"v")
    assert kv.get("k") == b"v"

    bus = configuration.services.bus.load()
    bus.topic_publish("events", "user.created", b"pending")
    bus_restarted = configuration.services.bus.load()

    done = threading.Event()
    seen: list[bytes] = []

    def callback(payload: bytes) -> None:
        seen.append(payload)
        done.set()
        raise StopIteration()

    bus_restarted.topic_consume("events", "user.*", callback)
    assert done.wait(timeout=3)
    assert seen == [b"pending"]

    vector_service = configuration.services.vector_store.load()
    vector_service.ensure_collection("docs", 4)
    vector_service.add_documents(
        collection_name="docs",
        ids=["doc-1"],
        vectors=[np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)],
        metadata=[{"source": "e2e"}],
        payloads=[{"text": "hello"}],
    )
    assert vector_service.get_document("docs", "doc-1") is not None
    vector_service.adapter.close()

    vector_service_restarted = configuration.services.vector_store.load()
    assert vector_service_restarted.get_document("docs", "doc-1") is not None

    triple_store = configuration.services.triple_store.load()
    graph_name = URIRef("http://example.org/graphs/e2e")
    subject = URIRef("http://example.org/s")
    predicate = URIRef("http://example.org/p")
    graph = Graph()
    graph.add((subject, predicate, Literal("ok")))
    triple_store.insert(graph, graph_name)

    result = list(
        triple_store.query(
            f"""
            SELECT ?o WHERE {{
                GRAPH <{graph_name}> {{
                    <{subject}> <{predicate}> ?o .
                }}
            }}
            """
        )
    )
    assert len(result) == 1
    assert str(result[0].o) == "ok"

    triple_store_restarted = configuration.services.triple_store.load()
    result_restarted = list(
        triple_store_restarted.query(
            f"""
            SELECT ?o WHERE {{
                GRAPH <{graph_name}> {{
                    <{subject}> <{predicate}> ?o .
                }}
            }}
            """
        )
    )
    assert len(result_restarted) == 1

    object_storage = configuration.services.object_storage.load()
    object_storage.put_object("e2e", "file.txt", b"content")
    object_storage_restarted = configuration.services.object_storage.load()
    assert object_storage_restarted.get_object("e2e", "file.txt") == b"content"
