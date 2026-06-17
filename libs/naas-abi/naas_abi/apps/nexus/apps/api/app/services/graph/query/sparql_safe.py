"""SPARQL injection-safety layer (AUDIT §7b.4).

Every user-supplied token in a ``ViewQuerySpec`` — IRIs, literal filter values,
full-text terms — passes through exactly one of these functions before it is
interpolated into a query string. There is never a raw f-string of an unescaped value.

This unifies and hardens the two divergent legacy helpers the rework inherited:
``_escape_sparql_string`` (``graph/service.py``, escaped only ``\\`` and ``"``) and
``_sparql_iri`` (``view/service.py``, rejected only ``< > " ' space``). Both should be
migrated to import from here.

Three rules:
  * IRIs are **validated and rejected** (never escaped) — an IRI that reaches a query
    must be grammar-valid, so any control or SPARQL-significant character is an error.
  * String literals are **escaped** and double-quoted.
  * Typed literals (number/date/boolean) **validate the lexical form** then emit
    ``"lex"^^xsd:type`` — numbers reject non-finite/exponent forms so an attacker cannot
    smuggle ``inf``/``nan``/``1e9`` into a typed slot.
Full-text terms are Lucene-escaped (so they match literally and cannot inject Lucene
operators or trigger wildcard full-index scans) and then string-escaped.
"""

from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphQuerySpecError,
)

XSD = "http://www.w3.org/2001/XMLSchema#"

# SPARQL IRIREF forbids control chars (<= 0x20) and these significant characters.
# We whitelist-validate by rejecting any of them rather than trying to escape.
_ILLEGAL_IRI_CHARS = frozenset('<>"{}|^`\\')

# A canonical xsd:date / xsd:dateTime lexical form (date, or date with a time + optional
# fractional seconds + optional timezone). Strict — anything else is rejected.
_DT_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?)?$"
)
# A plain decimal lexical form: optional sign, digits, optional fraction. No exponent.
_DECIMAL_RE = re.compile(r"^-?\d+(\.\d+)?$")

# Lucene query-parser metacharacters. Backslash-escaping each makes a user term match
# literally — neutralising both query injection and leading/standalone wildcard scans.
_LUCENE_META = frozenset('+-&|!(){}[]^"~*?:\\/')


def sparql_iri(value: str) -> str:
    """Validate ``value`` as an IRI and return it wrapped as ``<value>``.

    Raises ``GraphQuerySpecError`` on an empty IRI or any control/SPARQL-significant
    character — these are never escaped, because an IRIREF that contains them is simply
    invalid and indicates a malformed (or malicious) spec.
    """
    candidate = (value or "").strip()
    if not candidate:
        raise GraphQuerySpecError("empty IRI")
    for ch in candidate:
        if ord(ch) <= 0x20 or ch in _ILLEGAL_IRI_CHARS:
            raise GraphQuerySpecError(f"illegal character in IRI: {value!r}")
    return f"<{candidate}>"


def sparql_string_literal(value: str) -> str:
    """Escape ``value`` and wrap it as a SPARQL double-quoted string literal."""
    out: list[str] = []
    for ch in str(value):
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04X}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def sparql_typed_literal(value: Any, datatype: str) -> str:
    """Render a filter ``value`` as a typed literal for the given column ``datatype``.

    ``number`` rejects bools, non-numerics, and non-finite floats, and emits a plain
    decimal (no exponent); ``date`` is validated against a strict xsd regex; ``boolean``
    must be a real bool; ``iri``/``string`` delegate to the dedicated helpers.
    """
    if datatype == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise GraphQuerySpecError(f"non-numeric value for number column: {value!r}")
        if isinstance(value, float) and not math.isfinite(value):
            raise GraphQuerySpecError(f"non-finite number: {value!r}")
        if isinstance(value, int):
            return f'"{value:d}"^^<{XSD}integer>'
        try:
            lexical = format(Decimal(str(value)), "f")  # canonical decimal, never exponent
        except (InvalidOperation, ValueError) as exc:  # pragma: no cover - defensive
            raise GraphQuerySpecError(f"invalid decimal: {value!r}") from exc
        if not _DECIMAL_RE.match(lexical):  # pragma: no cover - defensive
            raise GraphQuerySpecError(f"invalid decimal lexical form: {lexical!r}")
        return f'"{lexical}"^^<{XSD}decimal>'

    if datatype == "boolean":
        if not isinstance(value, bool):
            raise GraphQuerySpecError(f"non-boolean value: {value!r}")
        return f'"{str(value).lower()}"^^<{XSD}boolean>'

    if datatype == "date":
        s = str(value).strip()
        if not _DT_RE.match(s):
            raise GraphQuerySpecError(f"invalid xsd date/dateTime: {value!r}")
        xsd_type = "dateTime" if "T" in s else "date"
        return f'"{s}"^^<{XSD}{xsd_type}>'

    if datatype == "iri":
        return sparql_iri(str(value))

    return sparql_string_literal(str(value))


def should_use_fulltext(term: str) -> bool:
    """Whether ``term`` is worth routing to a Lucene full-text index.

    Empty/whitespace-only or pure-metacharacter terms (``*``, ``?`` …) would scan the
    whole index or match nothing, so the caller falls back to ``CONTAINS`` for those.
    """
    stripped = (term or "").strip()
    if not stripped:
        return False
    return any(ch not in _LUCENE_META for ch in stripped)


def lucene_query_literal(term: str) -> str:
    """Escape ``term`` for the jena-text Lucene query parser, then as a SPARQL string.

    Composition order is deliberate: Lucene-escape **first** (so the term matches
    literally and cannot inject Lucene operators or a leading wildcard), then
    SPARQL-string-escape, so the SPARQL parser hands one intact string to jena-text.
    """
    escaped: list[str] = []
    for ch in term or "":
        if ch in _LUCENE_META:
            escaped.append("\\" + ch)
        else:
            escaped.append(ch)
    return sparql_string_literal("".join(escaped))
