from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from dotenv import load_dotenv
from naas_abi_core.services.triple_store.adaptors.secondary.AWSNeptune import (
    AWSNeptune,
    AWSNeptuneSSHTunnel,
    DEFAULT_CHUNK_SIZE,
)

load_dotenv()


@pytest.fixture
def aws_neptune():
    import os

    return AWSNeptuneSSHTunnel(
        aws_region_name=os.environ.get("AWS_REGION"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        db_instance_identifier=os.environ.get("AWS_NEPTUNE_DB_INSTANCE_IDENTIFIER"),
        bastion_host=os.environ.get("AWS_BASTION_HOST"),
        bastion_port=int(os.environ.get("AWS_BASTION_PORT")),
        bastion_user=os.environ.get("AWS_BASTION_USER"),
        bastion_private_key=os.environ.get("AWS_BASTION_PRIVATE_KEY"),
    )


# def test_get(aws_neptune):
#     graph = aws_neptune.get()
#     assert graph is not None
#     assert graph.serialize(format='turtle') is not None
#     assert graph.query("select ?s ?p ?o where {?s ?p ?o}") is not None


def test_graph_to_insert_query(aws_neptune):
    import rdflib
    from naas_abi_core.services.triple_store.adaptors.secondary.AWSNeptune import (
        NEPTUNE_DEFAULT_GRAPH_NAME,
        QueryType,
    )

    # from rdflib.namespace import _NAMESPACE_PREFIXES_RDFLIB, _NAMESPACE_PREFIXES_CORE

    graph = rdflib.Graph()

    graph.bind("test", "https://test.com/")
    graph.add(
        (
            rdflib.URIRef("https://test.com/s"),
            rdflib.URIRef("https://test.com/p"),
            rdflib.URIRef("https://test.com/o"),
        )
    )

    insert_statement = aws_neptune.graph_to_query(
        graph, QueryType.INSERT_DATA, graph_name=NEPTUNE_DEFAULT_GRAPH_NAME
    )

    # PREFIXES = "\n".join(
    #     [
    #         f"""PREFIX {prefix}: <{namespace}>"""
    #         for prefix, namespace in list(_NAMESPACE_PREFIXES_RDFLIB.items())
    #         + list(_NAMESPACE_PREFIXES_CORE.items())
    #     ]
    # )

    expected_insert_statement = f"""PREFIX test: <https://test.com/>

INSERT DATA {{ GRAPH <{str(NEPTUNE_DEFAULT_GRAPH_NAME)}> {{
<https://test.com/s> <https://test.com/p> <https://test.com/o> .
}}}}"""

    assert insert_statement == expected_insert_statement, (
        insert_statement,
        expected_insert_statement,
    )


def test_graph_management(aws_neptune: AWSNeptune):
    import uuid

    import rdflib

    left_graph_uuid = uuid.uuid4()
    right_graph_uuid = uuid.uuid4()
    left_graph_name = rdflib.URIRef(f"https://test.com/left/{left_graph_uuid}")
    right_graph_name = rdflib.URIRef(f"https://test.com/right/{right_graph_uuid}")

    left_graph = rdflib.Graph()
    right_graph = rdflib.Graph()

    left_graph.add(
        (
            rdflib.URIRef(f"https://test.com/left/{left_graph_uuid}s"),
            rdflib.URIRef(f"https://test.com/left/{left_graph_uuid}p"),
            rdflib.URIRef(f"https://test.com/left/{left_graph_uuid}o"),
        )
    )
    right_graph.add(
        (
            rdflib.URIRef(f"https://test.com/right/{right_graph_uuid}s"),
            rdflib.URIRef(f"https://test.com/right/{right_graph_uuid}p"),
            rdflib.URIRef(f"https://test.com/right/{right_graph_uuid}o"),
        )
    )

    aws_neptune.insert(right_graph)

    aws_neptune.create_graph(left_graph_name)
    aws_neptune.create_graph(right_graph_name)

    aws_neptune.insert(left_graph, left_graph_name)
    aws_neptune.insert(right_graph, right_graph_name)

    assert (
        len(
            list(
                aws_neptune.query(
                    f"""SELECT ?s ?p ?o WHERE {{ GRAPH <{str(left_graph_name)}> {{ ?s ?p ?o }} }}"""
                )
            )
        )
        == 1
    )
    assert (
        len(
            list(
                aws_neptune.query(
                    f"""SELECT ?s ?p ?o WHERE {{ GRAPH <{str(right_graph_name)}> {{ ?s ?p ?o }} }}"""
                )
            )
        )
        == 1
    )

    graph_list = aws_neptune.query("SELECT ?g WHERE { GRAPH ?g {} }")

    def _filter(row: Any) -> bool:
        assert isinstance(row, rdflib.query.ResultRow)
        return str(row[0]) in [str(left_graph_name), str(right_graph_name)]

    assert len(list(filter(_filter, list(graph_list)))) == 2

    aws_neptune.add_graph_to_graph(left_graph_name, right_graph_name)

    assert (
        len(
            list(
                aws_neptune.query(
                    f"""SELECT ?s ?p ?o WHERE {{ GRAPH <{str(left_graph_name)}> {{ ?s ?p ?o }} }}"""
                )
            )
        )
        == 1
    )
    assert (
        len(
            list(
                aws_neptune.query(
                    f"""SELECT ?s ?p ?o WHERE {{ GRAPH <{str(right_graph_name)}> {{ ?s ?p ?o }} }}"""
                )
            )
        )
        == 2
    )

    aws_neptune.copy_graph(left_graph_name, right_graph_name)

    assert (
        len(
            list(
                aws_neptune.query(
                    f"""SELECT ?s ?p ?o WHERE {{ GRAPH <{str(left_graph_name)}> {{ ?s ?p ?o }} }}"""
                )
            )
        )
        == 1
    )
    assert (
        len(
            list(
                aws_neptune.query(
                    f"""SELECT ?s ?p ?o WHERE {{ GRAPH <{str(right_graph_name)}> {{ ?s ?p ?o }} }}"""
                )
            )
        )
        == 1
    )

    aws_neptune.remove(left_graph, left_graph_name)

    assert (
        len(
            list(
                aws_neptune.query(
                    f"""SELECT ?s ?p ?o WHERE {{ GRAPH <{str(left_graph_name)}> {{ ?s ?p ?o }} }}"""
                )
            )
        )
        == 0
    )

    aws_neptune.clear_graph(left_graph_name)
    aws_neptune.clear_graph(right_graph_name)

    assert (
        len(
            list(
                aws_neptune.query(
                    f"""SELECT ?s ?p ?o WHERE {{ GRAPH <{str(left_graph_name)}> {{ ?s ?p ?o }} }}"""
                )
            )
        )
        == 0
    )
    assert (
        len(
            list(
                aws_neptune.query(
                    f"""SELECT ?s ?p ?o WHERE {{ GRAPH <{str(right_graph_name)}> {{ ?s ?p ?o }} }}"""
                )
            )
        )
        == 0
    )

    aws_neptune.drop_graph(left_graph_name)
    aws_neptune.drop_graph(right_graph_name)

    graph_list = aws_neptune.query("SELECT ?g WHERE { GRAPH ?g {} }")

    assert len(list(filter(_filter, list(graph_list)))) == 0


def test_AWSNeptune(aws_neptune):
    import uuid

    import rdflib

    graph = rdflib.Graph()

    prefix = f"https://test.com/{uuid.uuid4()}"

    graph.bind("test", prefix)
    graph.add(
        (
            rdflib.URIRef(f"{prefix}s"),
            rdflib.URIRef(f"{prefix}p"),
            rdflib.URIRef(f"{prefix}o"),
        )
    )

    # Testing insert

    aws_neptune.insert(graph)

    query = f"""PREFIX test: <{prefix}>

    SELECT ?s ?p ?o WHERE {{
        <{prefix}s> ?p ?o
    }}"""

    # Testing query

    query_result = aws_neptune.query(query)

    assert len(list(query_result)) == 1, query_result.serialize(format="json")

    for row in query_result:
        s, p, o = row
        assert s is None, row
        assert str(p) == f"{prefix}p", row
        assert str(o) == f"{prefix}o", row

    # Testing get_subject_graph

    subject_graph = aws_neptune.get_subject_graph(rdflib.URIRef(f"{prefix}s"))
    assert len(list(subject_graph)) == 1, subject_graph.serialize(format="json")

    for s, p, o in subject_graph:
        assert str(s) == f"{prefix}s", subject_graph
        assert str(p) == f"{prefix}p", subject_graph
        assert str(o) == f"{prefix}o", subject_graph


# Unit tests for chunking functionality


def test_chunk_graph(aws_neptune: AWSNeptune):
    """Test that _chunk_graph splits a graph into appropriately sized chunks."""
    import rdflib
    
    # Create a graph with more triples than the chunk size
    graph = rdflib.Graph()
    num_triples = DEFAULT_CHUNK_SIZE * 2 + 100  # 2.5 chunks worth
    
    for i in range(num_triples):
        graph.add(
            (
                rdflib.URIRef(f"https://test.com/subject_{i}"),
                rdflib.URIRef(f"https://test.com/predicate"),
                rdflib.URIRef(f"https://test.com/object_{i}"),
            )
        )
    
    # Chunk the graph
    chunks = aws_neptune._chunk_graph(graph, chunk_size=DEFAULT_CHUNK_SIZE)
    
    # Verify we get the expected number of chunks
    assert len(chunks) == 3, f"Expected 3 chunks, got {len(chunks)}"
    
    # Verify chunk sizes
    assert len(chunks[0]) == DEFAULT_CHUNK_SIZE
    assert len(chunks[1]) == DEFAULT_CHUNK_SIZE
    assert len(chunks[2]) == 100
    
    # Verify all triples are accounted for
    total_triples = sum(len(chunk) for chunk in chunks)
    assert total_triples == num_triples


def test_should_use_chunking_small_graph(aws_neptune: AWSNeptune):
    """Test that small graphs don't trigger chunking."""
    import rdflib
    
    graph = rdflib.Graph()
    # Add just a few triples
    for i in range(10):
        graph.add(
            (
                rdflib.URIRef(f"https://test.com/subject_{i}"),
                rdflib.URIRef(f"https://test.com/predicate"),
                rdflib.URIRef(f"https://test.com/object_{i}"),
            )
        )
    
    should_chunk = aws_neptune._should_use_chunking(graph)
    assert not should_chunk, "Small graph should not trigger chunking"


def test_should_use_chunking_large_graph(aws_neptune: AWSNeptune):
    """Test that large graphs trigger chunking."""
    import rdflib
    
    graph = rdflib.Graph()
    # Add more triples than the threshold
    for i in range(DEFAULT_CHUNK_SIZE + 100):
        graph.add(
            (
                rdflib.URIRef(f"https://test.com/subject_{i}"),
                rdflib.URIRef(f"https://test.com/predicate"),
                rdflib.URIRef(f"https://test.com/object_{i}"),
            )
        )
    
    should_chunk = aws_neptune._should_use_chunking(graph)
    assert should_chunk, "Large graph should trigger chunking"


def test_generate_temp_graph_name(aws_neptune: AWSNeptune):
    """Test that temporary graph names are unique."""
    name1 = aws_neptune._generate_temp_graph_name()
    name2 = aws_neptune._generate_temp_graph_name()
    
    assert name1 != name2, "Temporary graph names should be unique"
    assert str(name1).startswith("http://aws.amazon.com/neptune/temp/graph/")
    assert str(name2).startswith("http://aws.amazon.com/neptune/temp/graph/")


@pytest.mark.skipif(
    True,  # Skip by default as it requires Neptune instance
    reason="Integration test - requires Neptune instance",
)
def test_insert_with_chunking_integration(aws_neptune: AWSNeptune):
    """Integration test for chunked insert with real Neptune instance."""
    import uuid
    import rdflib
    
    # Create a large graph
    graph = rdflib.Graph()
    test_uuid = uuid.uuid4()
    num_triples = DEFAULT_CHUNK_SIZE * 2 + 100
    
    for i in range(num_triples):
        graph.add(
            (
                rdflib.URIRef(f"https://test.com/chunking_test/{test_uuid}/subject_{i}"),
                rdflib.URIRef(f"https://test.com/chunking_test/{test_uuid}/predicate"),
                rdflib.URIRef(f"https://test.com/chunking_test/{test_uuid}/object_{i}"),
            )
        )
    
    # Create a test graph
    test_graph_name = rdflib.URIRef(f"https://test.com/chunking_test/{test_uuid}")
    
    try:
        # Insert using chunking
        aws_neptune._insert_with_chunking(graph, test_graph_name)
        
        # Verify all triples were inserted
        result = aws_neptune.query(
            f"SELECT (COUNT(*) as ?count) WHERE {{ GRAPH <{str(test_graph_name)}> {{ ?s ?p ?o }} }}"
        )
        count = list(result)[0][0]
        assert int(count) == num_triples, f"Expected {num_triples} triples, found {count}"
        
    finally:
        # Cleanup
        try:
            aws_neptune.drop_graph(test_graph_name)
        except Exception as e:
            print(f"Cleanup failed: {e}")


def test_chunk_graph_preserves_namespaces(aws_neptune: AWSNeptune):
    """Test that chunking preserves namespace bindings."""
    import rdflib
    
    graph = rdflib.Graph()
    graph.bind("test", "https://test.com/")
    graph.bind("custom", "https://custom.org/")
    
    # Add triples spanning multiple chunks
    for i in range(DEFAULT_CHUNK_SIZE + 100):
        graph.add(
            (
                rdflib.URIRef(f"https://test.com/subject_{i}"),
                rdflib.URIRef(f"https://custom.org/predicate"),
                rdflib.URIRef(f"https://test.com/object_{i}"),
            )
        )
    
    chunks = aws_neptune._chunk_graph(graph)
    
    # Verify each chunk has the namespace bindings
    for chunk in chunks:
        namespaces = dict(chunk.namespaces())
        assert "test" in namespaces
        assert "custom" in namespaces
        assert str(namespaces["test"]) == "https://test.com/"
        assert str(namespaces["custom"]) == "https://custom.org/"


def test_chunk_graph_skips_blank_nodes(aws_neptune: AWSNeptune):
    """Test that chunking properly skips blank nodes."""
    import rdflib
    
    graph = rdflib.Graph()
    
    # Add regular triples
    for i in range(10):
        graph.add(
            (
                rdflib.URIRef(f"https://test.com/subject_{i}"),
                rdflib.URIRef(f"https://test.com/predicate"),
                rdflib.URIRef(f"https://test.com/object_{i}"),
            )
        )
    
    # Add blank node triples (should be skipped)
    bnode = rdflib.BNode()
    graph.add(
        (
            bnode,
            rdflib.URIRef("https://test.com/predicate"),
            rdflib.URIRef("https://test.com/object"),
        )
    )
    graph.add(
        (
            rdflib.URIRef("https://test.com/subject"),
            rdflib.URIRef("https://test.com/predicate"),
            bnode,
        )
    )
    
    chunks = aws_neptune._chunk_graph(graph)
    
    # Should only have the 10 regular triples, blank nodes skipped
    total_triples = sum(len(chunk) for chunk in chunks)
    assert total_triples == 10, f"Expected 10 triples (blank nodes skipped), got {total_triples}"
