"""Queries over the papers the pipeline added, in the module's named graph of
the engine's triple store (the in-engine module read local Turtle files)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from naas_abi_apps.common.graph import rows, sparql_string

PREFIXES = """PREFIX abi: <http://ontology.naas.ai/abi/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""
ONTOLOGY = Path(__file__).parent / "ontologies" / "ArXivOntology.ttl"


class ArXivQueries:
    def __init__(self, triple_store: Any, graph_name: str) -> None:
        self.triple_store = triple_store
        self.graph_name = graph_name

    async def _select(self, body: str) -> list[dict[str, str]]:
        query = f"{PREFIXES}SELECT {body}"
        return rows(
            await self.triple_store.query(
                query.replace("WHERE {", f"FROM <{self.graph_name}> WHERE {{", 1)
            )
        )

    async def query_authors(
        self, paper_id: str | None = None, paper_title: str | None = None
    ) -> dict[str, Any]:
        """Authors of papers matching an ID or part of a title."""
        if not paper_id and not paper_title:
            return {"error": "You must provide either paper_id or paper_title"}
        filters = ""
        if paper_id:
            filters += f"FILTER(CONTAINS(STR(?paper), {sparql_string(paper_id)}))\n"
        if paper_title:
            filters += f"FILTER(CONTAINS(LCASE(?paperTitle), LCASE({sparql_string(paper_title)})))\n"
        found = await self._select(
            "?paper ?paperTitle ?authorName WHERE {\n"
            "  ?paper a abi:ArXivPaper ; rdfs:label ?paperTitle ; abi:hasAuthor ?author .\n"
            f"  ?author rdfs:label ?authorName .\n{filters}}}"
        )
        papers: dict[str, dict[str, Any]] = {}
        for row in found:
            paper_key = row["paper"].split("#")[-1].split("/")[-1]
            paper = papers.setdefault(
                paper_key, {"id": paper_key, "title": row["paperTitle"], "authors": []}
            )
            if row["authorName"] not in paper["authors"]:
                paper["authors"].append(row["authorName"])
        return {"papers": list(papers.values())}

    async def query_papers(
        self, author_name: str | None = None, category: str | None = None
    ) -> dict[str, Any]:
        """Papers by an author or in a category."""
        if not author_name and not category:
            return {"error": "You must provide either author_name or category"}
        clauses = ""
        if author_name:
            clauses += (
                "  ?paper abi:hasAuthor ?author . ?author rdfs:label ?authorName .\n"
                f"  FILTER(CONTAINS(LCASE(?authorName), LCASE({sparql_string(author_name)})))\n"
            )
        if category:
            clauses += (
                "  ?paper abi:hasCategory ?category . ?category rdfs:label ?categoryName .\n"
                f"  FILTER(CONTAINS(LCASE(?categoryName), LCASE({sparql_string(category)})))\n"
            )
        found = await self._select(
            "DISTINCT ?paper ?paperTitle ?pdfUrl WHERE {\n"
            "  ?paper a abi:ArXivPaper ; rdfs:label ?paperTitle .\n"
            f"  OPTIONAL {{ ?paper abi:url ?pdfUrl . }}\n{clauses}}}"
        )
        return {
            "papers": [
                {
                    "id": row["paper"].split("#")[-1].split("/")[-1],
                    "title": row["paperTitle"],
                    "pdf_url": row.get("pdfUrl"),
                }
                for row in found
            ]
        }

    async def frequent_authors(self) -> dict[str, Any]:
        """Authors ranked by how many saved papers they wrote."""
        found = await self._select(
            "?authorName (COUNT(?paper) AS ?paperCount) WHERE {\n"
            "  ?paper a abi:ArXivPaper ; abi:hasAuthor ?author . ?author rdfs:label ?authorName .\n"
            "} GROUP BY ?authorName ORDER BY DESC(?paperCount)"
        )
        return {
            "authors": [
                {"name": r["authorName"], "paper_count": int(r["paperCount"])}
                for r in found
            ]
        }

    async def execute(self, query: str) -> dict[str, Any]:
        """A custom SPARQL query, run against the whole knowledge graph."""
        try:
            return {"results": rows(await self.triple_store.query(query))}
        except Exception as exc:  # noqa: BLE001 - reported to the agent
            return {"error": f"Query execution failed: {exc!s}"}

    @staticmethod
    def schema() -> dict[str, str]:
        """The ArXiv ontology (Turtle)."""
        return {"schema": ONTOLOGY.read_text(encoding="utf-8")}
