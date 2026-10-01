"""Render and validate topic SPARQL templates against their role contract."""

from __future__ import annotations

import re
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.graph.adapters.secondary.scoped_store import (
    query_shape,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphAccessError,
    GraphQuerySpecError,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.query.sparql_safe import (
    sparql_iri,
    sparql_string_literal,
)
from naas_abi.apps.nexus.apps.api.app.services.search.topics.topics__schema import (
    RESERVED_TOPIC_IDS,
    ROLE_CONTRACTS,
    TOPIC_ID_PATTERN,
    SearchTopic,
    SearchTopicValidationError,
)
from rdflib.plugins.sparql import prepareQuery

PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")

_SAMPLE_PARAMS: dict[str, Any] = {
    "q": "sample",
    "uri": "http://example.org/sample",
    "limit": 10,
    "offset": 0,
}


def placeholders(template: str) -> set[str]:
    return {m.group(1) for m in PLACEHOLDER.finditer(template)}


def _render_value(name: str, value: Any) -> str:
    if name == "q":
        # Content of a string literal: the template supplies the quotes.
        return sparql_string_literal(str(value or ""))[1:-1]
    if name == "uri":
        return sparql_iri(str(value))
    if name in {"limit", "offset"}:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise GraphQuerySpecError(f"{name} must be a non-negative integer")
        return str(value)
    raise GraphQuerySpecError(f"Unknown placeholder: {name}")


def render(template: str, role: str, params: dict[str, Any]) -> str:
    """Substitute the role's placeholders. Unknown or missing ones are errors."""
    allowed = ROLE_CONTRACTS[role].placeholders

    def substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in allowed:
            raise GraphQuerySpecError(
                f"Placeholder {{{{ {name} }}}} is not allowed in a {role} query"
            )
        if name not in params:
            raise GraphQuerySpecError(f"Missing value for {{{{ {name} }}}}")
        return _render_value(name, params[name])

    return PLACEHOLDER.sub(substitute, template)


def projected_variables(sparql: str) -> list[str]:
    algebra = prepareQuery(sparql).algebra
    return [str(v) for v in algebra.get("PV") or []]


def validate_query(template: str, role: str, *, label: str = "") -> list[str]:
    """Return human-readable errors; an empty list means the template fits its role."""
    prefix = f"{label}: " if label else ""
    contract = ROLE_CONTRACTS.get(role)
    if contract is None:
        return [f"{prefix}unknown role {role!r}"]
    if not template.strip():
        return [f"{prefix}query is empty"]

    errors = [
        f"{prefix}placeholder {{{{ {name} }}}} is not allowed (use {', '.join(sorted(contract.placeholders))})"
        for name in sorted(placeholders(template) - contract.placeholders)
    ]
    if errors:
        return errors
    try:
        rendered = render(template, role, _SAMPLE_PARAMS)
        kind, _ = query_shape(rendered)
        if kind != "SelectQuery":
            return [f"{prefix}must be a SELECT query"]
        projected = set(projected_variables(rendered))
    except GraphAccessError:
        return [
            f"{prefix}SERVICE and FROM clauses are not allowed: queries run on the workspace graphs"
        ]
    except Exception as exc:  # parse errors carry the useful message
        return [f"{prefix}invalid SPARQL ({exc})"]

    missing = contract.required - projected
    if missing:
        errors.append(f"{prefix}must project {', '.join('?' + v for v in sorted(missing))}")
    return errors


def validate_topic(topic: SearchTopic) -> None:
    errors: list[str] = []
    if not TOPIC_ID_PATTERN.match(topic.id):
        errors.append("id must be 2-48 chars of a-z, 0-9, '_' or '-', starting with a letter")
    elif topic.id in RESERVED_TOPIC_IDS:
        errors.append(f"id {topic.id!r} is reserved for a search scope")
    if not topic.label.strip():
        errors.append("label is required")
    if topic.class_iri:
        try:
            sparql_iri(topic.class_iri)
        except GraphQuerySpecError:
            errors.append("class_iri is not a valid IRI")
    errors += validate_query(topic.results_query, "results", label="results query")
    errors += validate_query(topic.header_query, "header", label="header query")
    seen: set[str] = set()
    for section in topic.sections:
        if not TOPIC_ID_PATTERN.match(section.id):
            errors.append(f"section id {section.id!r} is invalid")
        if section.id in seen:
            errors.append(f"section id {section.id!r} is duplicated")
        seen.add(section.id)
        errors += validate_query(section.query, "section", label=f"section {section.id}")
    if errors:
        raise SearchTopicValidationError(errors)
