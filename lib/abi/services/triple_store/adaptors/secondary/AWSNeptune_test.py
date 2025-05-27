import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture
def aws_neptune():
    import os
    from abi.services.triple_store.adaptors.secondary.AWSNeptune import (
        AWSNeptuneSSHTunnel,
    )

    return AWSNeptuneSSHTunnel(
        aws_region_name=os.environ.get("AWS_REGION"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
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
    from abi.services.triple_store.adaptors.secondary.AWSNeptune import QueryType
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

    insert_statement = aws_neptune.graph_to_query(graph, QueryType.INSERT_DATA)

    # PREFIXES = "\n".join(
    #     [
    #         f"""PREFIX {prefix}: <{namespace}>"""
    #         for prefix, namespace in list(_NAMESPACE_PREFIXES_RDFLIB.items())
    #         + list(_NAMESPACE_PREFIXES_CORE.items())
    #     ]
    # )

    expected_insert_statement = """PREFIX test: <https://test.com/>

INSERT DATA {{
<https://test.com/s> <https://test.com/p> <https://test.com/o> .
}}"""

    assert insert_statement == expected_insert_statement, (
        insert_statement,
        expected_insert_statement,
    )


def test_graph_management(aws_neptune):
    import rdflib
    import uuid

    graph_name = rdflib.URIRef(f"https://test.com/{uuid.uuid4()}")

    aws_neptune.create_graph(graph_name)

    query_result = aws_neptune.query("SELECT ?g WHERE { GRAPH ?g {} }")

    assert (
        len(list(filter(lambda row: str(row[0]) == str(graph_name), query_result))) == 1
    ), query_result.serialize(format="json")

    aws_neptune.clear_graph(graph_name)

    # query_result = aws_neptune.query("""SELECT ?g WHERE {{ GRAPH ?g {{}} }}""")

    # assert len(list(filter(lambda row: str(row[0]) == str(graph_name), query_result))) == 0, query_result.serialize(format='json')


def test_AWSNeptune(aws_neptune):
    import rdflib
    import uuid

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

    # Testing remove

    aws_neptune.remove(graph)

    query_result = aws_neptune.query(query)

    assert len(list(query_result)) == 0, query_result.serialize(format="json")

    # Testing clear_graph

    aws_neptune.clear_graph()

    query_result = aws_neptune.query("""SELECT ?s ?p ?o WHERE { ?s ?p ?o }""")

    assert len(list(query_result)) == 0, query_result.serialize(format="json")
