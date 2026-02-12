from abc import ABC, abstractmethod
import uuid

import pytest
from rdflib import Graph, Literal, URIRef


class GenericTripleStoreSecondaryAdapterTest(ABC):
    @pytest.fixture
    @abstractmethod
    def adapter(self):
        raise NotImplementedError()

    @pytest.fixture
    def supports_named_graphs(self) -> bool:
        return False

    def test_adapter_has_required_methods(self, adapter):
        assert callable(getattr(adapter, "insert", None))
        assert callable(getattr(adapter, "remove", None))
        assert callable(getattr(adapter, "query", None))
        assert callable(getattr(adapter, "get", None))
        assert callable(getattr(adapter, "get_subject_graph", None))

    def test_insert_query_remove_roundtrip_default_graph(self, adapter):
        marker = uuid.uuid4().hex
        subject = URIRef(f"http://test.example.org/{marker}/entity")
        predicate = URIRef("http://test.example.org/value")
        obj = Literal(f"value-{marker}")

        g = Graph()
        g.add((subject, predicate, obj))

        adapter.insert(g)

        result = list(
            adapter.query(
                f"""
                SELECT ?o WHERE {{
                    <{subject}> <{predicate}> ?o .
                }}
                """
            )
        )
        assert len(result) == 1
        assert str(result[0].o) == str(obj)

        subject_graph = adapter.get_subject_graph(subject)
        assert len(list(subject_graph.triples((subject, predicate, obj)))) == 1

        adapter.remove(g)

        result_after_delete = list(
            adapter.query(
                f"""
                SELECT ?o WHERE {{
                    <{subject}> <{predicate}> ?o .
                }}
                """
            )
        )
        assert len(result_after_delete) == 0

    def test_insert_query_remove_roundtrip_named_graph(
        self, adapter, supports_named_graphs: bool
    ):
        if not supports_named_graphs:
            pytest.skip("Adapter does not support named graphs")

        marker = uuid.uuid4().hex
        graph_name = URIRef(f"http://test.example.org/graph/{marker}")
        subject = URIRef(f"http://test.example.org/{marker}/entity")
        predicate = URIRef("http://test.example.org/value")
        obj = Literal(f"value-{marker}")

        g = Graph()
        g.add((subject, predicate, obj))

        adapter.insert(g, graph_name=graph_name)

        named_graph_result = list(
            adapter.query(
                f"""
                SELECT ?o WHERE {{
                    GRAPH <{graph_name}> {{
                        <{subject}> <{predicate}> ?o .
                    }}
                }}
                """
            )
        )
        assert len(named_graph_result) == 1
        assert str(named_graph_result[0].o) == str(obj)

        adapter.remove(g, graph_name=graph_name)

        named_graph_result_after_delete = list(
            adapter.query(
                f"""
                SELECT ?o WHERE {{
                    GRAPH <{graph_name}> {{
                        <{subject}> <{predicate}> ?o .
                    }}
                }}
                """
            )
        )
        assert len(named_graph_result_after_delete) == 0
