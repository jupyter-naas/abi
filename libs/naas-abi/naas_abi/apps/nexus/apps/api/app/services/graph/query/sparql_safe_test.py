"""Tests for the SPARQL injection-safety layer (AUDIT §7b.4).

These are the foundation: every user-supplied token in a ViewQuerySpec passes through
one of these functions before reaching a query string. The tests double as the spec
for the three escaping/validation functions and the full-text helpers, and pin the
injection payloads the adversarial review called out.
"""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphQuerySpecError,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.sparql_safe import (
    XSD,
    lucene_query_literal,
    should_use_fulltext,
    sparql_iri,
    sparql_string_literal,
    sparql_typed_literal,
)


def _no_bare_quote(literal: str) -> bool:
    """Every `"` inside the literal body (between the wrapping quotes) is backslash-escaped."""
    assert literal[0] == '"' and literal[-1] == '"'
    body = literal[1:-1]
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\":
            i += 2  # skip the escaped char
            continue
        if ch == '"':
            return False  # an unescaped quote — injection escape
        i += 1
    return True


class TestSparqlIri:
    def test_valid_iri_is_wrapped(self) -> None:
        assert sparql_iri("http://x/y#z") == "<http://x/y#z>"

    def test_surrounding_whitespace_is_stripped(self) -> None:
        assert sparql_iri("  http://x/y  ") == "<http://x/y>"

    def test_empty_is_rejected(self) -> None:
        with pytest.raises(GraphQuerySpecError):
            sparql_iri("")
        with pytest.raises(GraphQuerySpecError):
            sparql_iri("   ")

    @pytest.mark.parametrize(
        "bad",
        [
            "http://x/y z",          # space
            "http://x/y>z",          # angle bracket — breaks out of <...>
            "http://x/y<z",
            'http://x/y"z',          # quote
            "http://x/y{z}",         # brace
            "http://x/y|z",          # pipe
            "http://x/y^z",          # caret
            "http://x/y`z",          # backtick
            "http://x/y\\z",         # backslash
            "http://x/y\nz",         # newline (control)
            "http://x/y\tz",         # tab (control)
            "http://x\x00y",         # NUL byte (control char)
        ],
    )
    def test_illegal_characters_are_rejected(self, bad: str) -> None:
        with pytest.raises(GraphQuerySpecError):
            sparql_iri(bad)


class TestSparqlStringLiteral:
    def test_plain_string(self) -> None:
        assert sparql_string_literal("solitude") == '"solitude"'

    def test_double_quote_is_escaped(self) -> None:
        assert sparql_string_literal('a"b') == '"a\\"b"'

    def test_backslash_is_escaped(self) -> None:
        # input: a \ b  →  literal "a\\b"
        assert sparql_string_literal("a\\b") == '"a\\\\b"'

    def test_newline_tab_carriage_return_are_escaped(self) -> None:
        assert sparql_string_literal("a\nb\tc\rd") == '"a\\nb\\tc\\rd"'

    def test_other_control_chars_are_unicode_escaped(self) -> None:
        assert sparql_string_literal("a\x00b") == '"a\\u0000b"'

    def test_injection_payload_cannot_break_out(self) -> None:
        # The classic "close the string and inject" payload.
        lit = sparql_string_literal('") } INSERT DATA { <a> <b> <c> } #')
        assert _no_bare_quote(lit)


class TestSparqlTypedLiteral:
    def test_integer(self) -> None:
        assert sparql_typed_literal(5, "number") == f'"5"^^<{XSD}integer>'

    def test_negative_integer(self) -> None:
        assert sparql_typed_literal(-12, "number") == f'"-12"^^<{XSD}integer>'

    def test_decimal_has_no_exponent(self) -> None:
        assert sparql_typed_literal(3.5, "number") == f'"3.5"^^<{XSD}decimal>'
        # A float that repr()s with an exponent must still be a plain decimal lexical form.
        out = sparql_typed_literal(1e-7, "number")
        lexical = out.split("^^")[0]  # the "<value>" part, before the datatype IRI
        assert "e" not in lexical and "E" not in lexical
        assert out.endswith(f'^^<{XSD}decimal>')

    def test_non_finite_numbers_are_rejected(self) -> None:
        for bad in (float("inf"), float("-inf"), float("nan")):
            with pytest.raises(GraphQuerySpecError):
                sparql_typed_literal(bad, "number")

    def test_bool_is_not_a_number(self) -> None:
        with pytest.raises(GraphQuerySpecError):
            sparql_typed_literal(True, "number")

    def test_string_is_not_a_number(self) -> None:
        with pytest.raises(GraphQuerySpecError):
            sparql_typed_literal("5", "number")

    def test_boolean(self) -> None:
        assert sparql_typed_literal(True, "boolean") == f'"true"^^<{XSD}boolean>'
        assert sparql_typed_literal(False, "boolean") == f'"false"^^<{XSD}boolean>'

    def test_non_bool_boolean_is_rejected(self) -> None:
        with pytest.raises(GraphQuerySpecError):
            sparql_typed_literal(1, "boolean")

    def test_date(self) -> None:
        assert sparql_typed_literal("2026-06-16", "date") == f'"2026-06-16"^^<{XSD}date>'

    def test_datetime(self) -> None:
        assert (
            sparql_typed_literal("2026-06-16T10:00:00Z", "date")
            == f'"2026-06-16T10:00:00Z"^^<{XSD}dateTime>'
        )

    def test_bad_date_is_rejected(self) -> None:
        # The regex is a lexical-shape gate (injection safety) — anything with a quote,
        # space, slash, or stray text is rejected. Calendar-range validity is the store's
        # job, so a well-shaped-but-impossible date is not this function's concern.
        for bad in ("not-a-date", '2026" } INJECT', "2026/06/16", "2026-06-16 OR 1=1"):
            with pytest.raises(GraphQuerySpecError):
                sparql_typed_literal(bad, "date")

    def test_iri_datatype_delegates_to_sparql_iri(self) -> None:
        assert sparql_typed_literal("http://x/y", "iri") == "<http://x/y>"
        with pytest.raises(GraphQuerySpecError):
            sparql_typed_literal("http://x y", "iri")

    def test_string_datatype_delegates_to_string_literal(self) -> None:
        assert sparql_typed_literal('a"b', "string") == '"a\\"b"'


class TestFullText:
    def test_should_use_fulltext_for_real_terms(self) -> None:
        assert should_use_fulltext("solitude")
        assert should_use_fulltext("a*")  # has a real char

    @pytest.mark.parametrize("term", ["", "   ", "*", "?", "**", "?*", "+"])
    def test_should_not_fulltext_for_empty_or_pure_wildcard(self, term: str) -> None:
        assert not should_use_fulltext(term)

    def test_plain_term_needs_no_escaping(self) -> None:
        assert lucene_query_literal("solitude") == '"solitude"'

    def test_wildcard_is_escaped_to_literal(self) -> None:
        # '*' is a Lucene metachar → backslash-escaped, then the backslash is
        # SPARQL-escaped → two backslashes precede the star in the SPARQL literal.
        assert lucene_query_literal("a*b") == '"a\\\\*b"'

    def test_lucene_injection_payload_cannot_break_out(self) -> None:
        # A term packed with Lucene operators AND a SPARQL-string-breaking quote.
        lit = lucene_query_literal('x") OR y:[a TO z] AND (')
        assert _no_bare_quote(lit)
