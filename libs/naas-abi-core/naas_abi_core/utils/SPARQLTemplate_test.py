import pytest

from naas_abi_core.utils.SPARQLTemplate import (
    BARE,
    IRI,
    STRING,
    SPARQLTemplate,
    placeholder_contexts,
    safe_values,
)

LITERAL_BREAKOUT = 'a")) } UNION { GRAPH ?g { ?s ?p ?o } } #'


def test_contexts_follow_where_the_placeholder_stands():
    template = """
        # a "comment with a quote
        SELECT ?s WHERE {
          ?s rdfs:label ?l .
          FILTER(CONTAINS(LCASE(STR(?l)), LCASE("{{ name }}")))
          FILTER(?s != <{{ uri }}>)
          BIND('{{ other | lower }}' AS ?o)
          FILTER(STRSTARTS(STR(?s), "http://x/{{name}}"))
        } LIMIT {{ limit }}
    """
    assert placeholder_contexts(template) == {
        "name": {STRING},
        "uri": {IRI},
        "other": {STRING},
        "limit": {BARE},
    }


def test_a_literal_value_is_escaped():
    contexts = {"name": {STRING}}

    assert safe_values({"name": LITERAL_BREAKOUT}, contexts)["name"] == (
        'a\\")) } UNION { GRAPH ?g { ?s ?p ?o } } #'
    )
    assert safe_values({"name": "l'eau\\\n"}, contexts)["name"] == "l\\'eau\\\\\\n"


@pytest.mark.parametrize(
    "value", ["http://x> } UNION { ?s ?p ?o", "http://x y", 'http://x"', "http://x\\u"]
)
def test_a_value_that_would_leave_its_iri_is_refused(value):
    with pytest.raises(ValueError, match="not a valid IRI"):
        safe_values({"uri": value}, {"uri": {IRI}})


def test_a_bare_value_must_be_a_number():
    assert safe_values({"limit": "10"}, {"limit": {BARE}}) == {"limit": "10"}
    assert safe_values({"limit": 10}, {"limit": {BARE}}) == {"limit": "10"}
    with pytest.raises(ValueError, match="must be a number"):
        safe_values({"limit": "10 } UNION { ?s ?p ?o }"}, {"limit": {BARE}})


def test_values_only_read_by_statements_and_none_pass_unchanged():
    template = SPARQLTemplate(
        """{% if depth and depth|int == 1 %}SELECT * WHERE { <{{ s }}> ?p ?o }
        {% else %}SELECT * WHERE { <{{ s }}> ?p ?o . ?o ?q ?r }{% endif %}
        {% if name %}FILTER("{{ name }}"){% endif %}"""
    )

    rendered = template.render(depth="1", s="http://x/a", name=None)

    assert "?q" not in rendered and "FILTER" not in rendered
    assert "<http://x/a>" in rendered
