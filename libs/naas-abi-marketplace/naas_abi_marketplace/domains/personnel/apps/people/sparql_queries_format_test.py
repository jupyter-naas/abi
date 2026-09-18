"""SPARQL display formatting."""

from __future__ import annotations

from naas_abi_marketplace.domains.personnel.apps.people import sparql_queries as sq


def test_format_sparql_dedents_prefix_and_where_blocks() -> None:
    raw = """
            PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            SELECT ?x
            WHERE {
              { ?x rdf:type ?t . }
            }
            LIMIT 1
        """
    out = sq.format_sparql(raw)
    assert out.startswith("PREFIX rdf:")
    assert "\nSELECT ?x\n" in out
    assert "\nWHERE {\n" in out
    assert "  { ?x rdf:type ?t . }" in out or "\n  {\n" in out
    assert out.rstrip().endswith("LIMIT 1")


def test_render_query_is_formatted_for_profile_header() -> None:
    text = sq.render_query("find_profile_header", slug="bob_martin")
    assert text.startswith("PREFIX ")
    assert 'LCASE("bob_martin")' in text
    assert not text.splitlines()[0].startswith(" ")
