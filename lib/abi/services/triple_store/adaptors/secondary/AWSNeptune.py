from abi.services.triple_store.TripleStoreService import ITripleStorePort

import boto3
import botocore
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from rdflib import Graph, URIRef
from abi.services.triple_store.TripleStorePorts import OntologyEvent
import rdflib
from typing import Tuple, Any
import paramiko
from sshtunnel import SSHTunnelForwarder
from io import StringIO
import tempfile
import socket

from rdflib.plugins.sparql.results.xmlresults import XMLResultParser
from rdflib.query import ResultRow
from rdflib.term import Identifier
from rdflib.namespace import _NAMESPACE_PREFIXES_RDFLIB, _NAMESPACE_PREFIXES_CORE

from SPARQLWrapper import SPARQLWrapper

from enum import Enum

ORIGINAL_GETADDRINFO = socket.getaddrinfo

NEPTUNE_DEFAULT_GRAPH_NAME: URIRef = URIRef(
    "http://aws.amazon.com/neptune/vocab/v01/DefaultNamedGraph"
)


class QueryType(Enum):
    INSERT_DATA = "INSERT DATA"
    DELETE_DATA = "DELETE DATA"


class QueryMode(Enum):
    QUERY = "query"
    UPDATE = "update"


class AWSNeptune(ITripleStorePort):
    aws_region_name: str
    aws_access_key_id: str
    aws_secret_access_key: str

    bastion_host: str
    bastion_port: int
    bastion_user: str

    neptune_sparql_endpoint: str
    neptune_port: int
    neptune_sparql_url: str

    credentials: botocore.credentials.Credentials

    # SSH tunnel to the Bastion host
    tunnel: SSHTunnelForwarder

    def __init__(
        self, aws_region_name: str, aws_access_key_id: str, aws_secret_access_key: str
    ):
        assert isinstance(aws_region_name, str)
        assert isinstance(aws_access_key_id, str)
        assert isinstance(aws_secret_access_key, str)

        self.aws_region_name = aws_region_name

        self.session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region_name,
        )

        self.client = self.session.client("neptune", region_name=self.aws_region_name)
        self.neptune_sparql_endpoint = self.client.describe_db_instances()[
            "DBInstances"
        ][0]["Endpoint"]["Address"]
        self.neptune_port = self.client.describe_db_instances()["DBInstances"][0][
            "Endpoint"
        ]["Port"]

        self.credentials = self.session.get_credentials()

        self.neptune_sparql_url = (
            f"https://{self.neptune_sparql_endpoint}:{self.neptune_port}/sparql"
        )

    def __get_signed_headers(
        self,
        method: str,
        url: str,
        data: Any | None = None,
        params: Any | None = None,
        headers: Any | None = None,
    ):
        request = AWSRequest(
            method=method, url=url, data=data, params=params, headers=headers
        )
        SigV4Auth(
            self.credentials, "neptune-db", region_name=self.aws_region_name
        ).add_auth(request)
        return request.headers

    def __post_query(self, data: Any, timeout: int = 10) -> requests.Response:
        headers = {}
        headers["Accept"] = "application/sparql-results+xml"
        headers["Content-Type"] = "application/x-www-form-urlencoded"

        headers = self.__get_signed_headers(
            "POST",
            self.neptune_sparql_url,
            data=data,
            headers=headers,
        )

        response = requests.post(
            self.neptune_sparql_url,
            headers=headers,
            timeout=timeout,
            verify=True,
            data=data,
        )

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(response.text)
            raise e

        return response

    def insert(self, triples: Graph):
        query = self.graph_to_query(triples, QueryType.INSERT_DATA)

        s = SPARQLWrapper("")
        s.setQuery(query)

        query_type = str(s.queryType).upper()
        if query_type in ["SELECT", "CONSTRUCT", "ASK", "DESCRIBE"]:
            data = {"query": query}
        else:
            data = {"update": query}

        response = self.__post_query(data)
        return response

    def remove(self, triples: Graph):
        query = self.graph_to_query(triples, QueryType.DELETE_DATA)
        response = self.__post_query({"update": query})
        return response

    def get(self) -> Graph:
        response = self.__post_query("query=select ?s ?p ?o where {?s ?p ?o}")
        result = XMLResultParser().parse(StringIO(response.text))

        graph = Graph()
        for row in result:
            assert isinstance(row, ResultRow)

            s: Identifier | None = row.get("s")
            p: Identifier | None = row.get("p")
            o: Identifier | None = row.get("o")

            assert s is not None and p is not None and o is not None

            graph.add((s, p, o))

        return graph

    def handle_view_event(
        self,
        view: Tuple[URIRef | None, URIRef | None, URIRef | None],
        event: OntologyEvent,
        triple: Tuple[URIRef | None, URIRef | None, URIRef | None],
    ):
        pass

    def query(
        self, query: str, query_mode: QueryMode = QueryMode.QUERY
    ) -> rdflib.query.Result:
        response = self.__post_query({query_mode.value: query})
        try:
            result = XMLResultParser().parse(StringIO(response.text))
            return result
        except Exception as e:
            print(response.text)
            raise e

    def query_view(self, view: str, query: str) -> rdflib.query.Result:
        return self.query(query)

    def get_subject_graph(self, subject: URIRef) -> Graph:
        res = self.query(f"SELECT ?s ?p ?o WHERE  {{ <{str(subject)}> ?p ?o }}")

        graph = Graph()
        for row in res:
            assert isinstance(row, ResultRow)
            assert len(row) == 3
            _, p, o = row
            graph.add((subject, p, o))

        return graph

    def graph_to_query(self, graph: Graph, query_type: QueryType) -> str:
        """
        Convert an RDFLib graph to a SPARQL INSERT statement.

        Args:
            graph (Graph): The RDFLib graph to convert

        Returns:
            str: A SPARQL INSERT statement that can be used to insert the triples
        """
        # Get all namespaces from the graph
        namespaces = []
        for prefix, namespace in graph.namespaces():
            if (
                prefix in _NAMESPACE_PREFIXES_RDFLIB
                or prefix in _NAMESPACE_PREFIXES_CORE
            ):
                continue
            namespaces.append(f"PREFIX {prefix}: <{namespace}>")

        # Build the INSERT DATA statement
        triples = []
        for s, p, o in graph:
            # Convert each term to N3 format
            s_str = s.n3()
            p_str = p.n3()
            o_str = o.n3()
            triples.append(f"{s_str} {p_str} {o_str} .")

        # Combine everything into a SPARQL query
        query = "\n".join(namespaces)
        query += f"\n\n{query_type.value} {{\n"
        query += "\n".join(triples)
        query += "\n}"

        return query

    # Graph management

    def create_graph(self, graph_name: URIRef):
        assert graph_name is not None
        assert isinstance(graph_name, URIRef)

        result = self.__post_query(
            {QueryMode.UPDATE.value: f"CREATE GRAPH <{str(graph_name)}>"}
        )
        print(result.text)

    def clear_graph(self, graph_name: URIRef = NEPTUNE_DEFAULT_GRAPH_NAME):
        assert graph_name is not None
        assert isinstance(graph_name, URIRef)

        self.__post_query({QueryMode.UPDATE.value: f"CLEAR GRAPH <{str(graph_name)}>"})


class AWSNeptuneSSHTunnel(AWSNeptune):
    def __init__(
        self,
        aws_region_name: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        bastion_host: str,
        bastion_port: int,
        bastion_user: str,
        bastion_private_key: str,
    ):
        super().__init__(
            aws_region_name=aws_region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )

        assert isinstance(bastion_host, str)
        assert isinstance(bastion_port, int)
        assert isinstance(bastion_user, str)
        assert isinstance(bastion_private_key, str)

        self.bastion_host = bastion_host
        self.bastion_port = bastion_port
        self.bastion_user = bastion_user
        self.bastion_private_key = bastion_private_key

        self.bastion_client = paramiko.SSHClient()
        self.bastion_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # self.bastion_client.connect(self.bastion_host, port=self.bastion_port, username=self.bastion_user, pkey=paramiko.RSAKey.from_private_key(StringIO(self.bastion_private_key)))
        self.tunnel = self.__create_ssh_tunnel()

        # We patch the neptune_sparql_url to use the tunnel.
        self.neptune_sparql_url = f"https://{self.neptune_sparql_endpoint}:{self.tunnel.local_bind_port}/sparql"

    def __monkey_patch_getaddrinfo(self):
        """
        Monkey patches the socket.getaddrinfo function to redirect requests for the Neptune endpoint
        to localhost. This is necessary because the SSH tunnel forwards traffic to localhost, but
        the original code tries to connect to the actual Neptune endpoint.
        """
        assert self.neptune_sparql_endpoint is not None

        def new_getaddrinfo(*args):
            if args[0] == self.neptune_sparql_endpoint:
                return ORIGINAL_GETADDRINFO("127.0.0.1", *args[1:])
            else:
                return ORIGINAL_GETADDRINFO(*args)

        socket.getaddrinfo = new_getaddrinfo

    def __create_ssh_tunnel(self) -> SSHTunnelForwarder:
        """
        Creates an SSH tunnel to the Neptune database through a bastion host.

        Returns:
            SSHTunnelForwarder: An active SSH tunnel that forwards traffic from localhost
                               to the Neptune database endpoint through the bastion host.

        The tunnel is configured to:
        - Connect to the bastion host using the provided credentials
        - Forward traffic from a local port to the Neptune database endpoint
        - Use the private key for authentication
        """
        assert self.neptune_sparql_endpoint is not None
        assert self.neptune_port is not None

        # Write pkey to tmpfile
        with tempfile.NamedTemporaryFile(delete=True) as tmpfile:
            tmpfile.write(self.bastion_private_key.encode("utf-8"))
            tmpfile.flush()
            tmpfile.name

            tunnel = SSHTunnelForwarder(
                (self.bastion_host, self.bastion_port),
                ssh_username=self.bastion_user,
                ssh_pkey=tmpfile.name,
                remote_bind_address=(
                    socket.gethostbyname(self.neptune_sparql_endpoint),
                    self.neptune_port,
                ),
            )

            tunnel.start()

            self.__monkey_patch_getaddrinfo()

            return tunnel


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    neptune = AWSNeptuneSSHTunnel(
        aws_region_name=os.environ["AWS_REGION"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        bastion_host=os.environ["AWS_BASTION_HOST"],
        bastion_port=int(os.environ["AWS_BASTION_PORT"]),
        bastion_user=os.environ["AWS_BASTION_USER"],
        bastion_private_key=os.environ["AWS_BASTION_PRIVATE_KEY"],
    )

    while True:
        query = input("Enter a query: ")
        if query == "exit":
            break
        elif query.startswith("create graph "):
            graph_name = URIRef(query.split(" ")[2])
            neptune.create_graph(graph_name)
        elif query.startswith("clear graph "):
            graph_name = URIRef(query.split(" ")[2])
            neptune.clear_graph(graph_name)
        elif query.startswith("list graphs"):
            result = neptune.query("SELECT ?g WHERE { GRAPH ?g { }}")
            print(result.serialize(format="json"))
        else:
            query_mode = QueryMode.QUERY
            if query.lower().startswith("insert"):
                query_mode = QueryMode.UPDATE
            result = neptune.query(query, query_mode)
            print(result.serialize(format="json"))
