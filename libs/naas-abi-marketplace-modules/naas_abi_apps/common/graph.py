"""Build RDF the way ``naas_abi_core.utils.Graph.ABIGraph`` does, without core
(needs ``naas-abi-sdk[rdf]``): same namespaces, same individual URIs, so data a
remote module writes lines up with what the in-engine module wrote."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import quote

from rdflib import DCTERMS, OWL, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import SKOS

BFO = Namespace("http://purl.obolibrary.org/obo/")
ABI = Namespace("http://ontology.naas.ai/abi/")
CCO = Namespace("https://www.commoncoreontologies.org/")
TIME = Namespace("http://www.w3.org/2006/time#")


def _now() -> Literal:
    return Literal(
        datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S%z"), datatype=XSD.dateTime
    )


class ABIGraph(Graph):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.bind("bfo", BFO)
        self.bind("skos", SKOS)
        self.bind("abi", ABI)
        self.bind("cco", CCO)
        self.bind("xsd", XSD)
        self.bind("time", TIME)

    def add_data_properties(
        self, uri: URIRef, lang: str = "en", **properties: Any
    ) -> None:
        for name, value in properties.items():
            if value is None:
                continue
            if isinstance(value, str):
                self.add((uri, ABI[name], Literal(value.strip(), lang=lang)))
            elif isinstance(value, bool):
                self.add((uri, ABI[name], Literal(value)))
            elif isinstance(value, int | float):
                self.add((uri, ABI[name], Literal(value, datatype=XSD.integer)))
            elif isinstance(value, datetime):
                if value.tzinfo is None:
                    value = value.replace(tzinfo=UTC)
                self.add(
                    (
                        uri,
                        ABI[name],
                        Literal(
                            value.strftime("%Y-%m-%dT%H:%M:%S%z"), datatype=XSD.dateTime
                        ),
                    )
                )
            elif isinstance(value, date):
                self.add(
                    (
                        uri,
                        ABI[name],
                        Literal(value.strftime("%Y-%m-%d"), datatype=XSD.date),
                    )
                )
        self.add((uri, DCTERMS.modified, _now()))

    def add_individual(
        self,
        uri: URIRef,
        label: Any,
        is_a: Any,
        lang: str = "en",
        skip_if_exists: bool = True,
        **properties: Any,
    ) -> URIRef:
        if not (skip_if_exists and (uri, RDF.type, URIRef(is_a)) in self):
            self.add((uri, RDF.type, OWL.NamedIndividual))
            self.add((uri, RDF.type, URIRef(is_a)))
            self.add((uri, RDFS.label, Literal(str(label), lang=lang)))
            self.add((uri, DCTERMS.created, _now()))
        self.add_data_properties(uri, lang, **properties)
        return uri

    def add_individual_to_prefix(
        self,
        prefix: Namespace,
        uid: Any,
        label: Any,
        is_a: Any,
        lang: str = "en",
        skip_if_exists: bool = True,
        **properties: Any,
    ) -> URIRef:
        """``<prefix><TypeName>#<uid>``, as core's ABIGraph names individuals."""
        uid = str(uid).split(":")[-1]
        type_name = str(is_a).split("/")[-1]
        uri = URIRef(quote(f"{prefix!s}{type_name}#{uid}", safe=":/#"))
        return self.add_individual(uri, label, is_a, lang, skip_if_exists, **properties)


def rows(result: Any) -> list[dict[str, str]]:
    """A SPARQL SELECT result as ``[{variable: value}]``; unbound variables left out."""
    variables = [str(v) for v in (result.vars or [])]
    out = []
    for row in result:
        values = (
            row.asdict()
            if hasattr(row, "asdict")
            else dict(zip(variables, row, strict=False))
        )
        out.append({str(k): str(v) for k, v in values.items() if v is not None})
    return out


def sparql_string(value: str) -> str:
    """``value`` as a quoted SPARQL string literal (quotes, backslashes and
    newlines escaped), so user input cannot change the query."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'
