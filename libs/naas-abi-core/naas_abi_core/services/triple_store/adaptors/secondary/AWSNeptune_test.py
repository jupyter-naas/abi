from typing import Any

import pytest
from dotenv import load_dotenv
from naas_abi_core.services.triple_store.adaptors.secondary.AWSNeptune import (
    AWSNeptune,
    AWSNeptuneSSHTunnel,
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
