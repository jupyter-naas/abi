"""Policy documents: schema and validation.

A document is ``{"version": "2026-10-13", "statements": [...]}``; each statement
has an optional ``sid``, an ``effect`` (``Allow`` or ``Deny``), ``actions`` and
``resources``. Validation rejects the whole document on any failure and lists
every error.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, cast

import yaml

from naas_abi_core.services.iam.catalog import CatalogRegistry
from naas_abi_core.services.iam.names import (
    PLATFORM_SCOPE,
    PREFIX,
    has_wildcard,
    split_action,
    variables,
)

POLICY_VERSION = "2026-10-13"
MAX_DOCUMENT_BYTES = 32 * 1024
MAX_STATEMENTS = 100
MAX_PATTERNS = 100
# How deep a policy may sit under parents (AGENTS.md, "Sub-policies"): the root
# of a chain is at depth 1.
MAX_DEPTH = 8

Effect = Literal["Allow", "Deny"]

# Variables a stored policy may use in its resources. The module ones resolve
# for a module's service account, ``module/<project>/<id>``, and are bound when
# its manifest is approved; for any other principal they match nothing.
MODULE_VARIABLES = frozenset({"module.id", "module.project"})
POLICY_VARIABLES = frozenset({"scope", "principal.id", "user.id"}) | MODULE_VARIABLES
# What a policy attached at a scope writes each resource pattern as: the
# container itself, ``${scope}``, or what it holds, ``${scope}/...``.
SCOPE = "${scope}"
SCOPE_PREFIX = "${scope}/"


# How the grammar before container paths wrote it: ``${scope}:<service>:...``.
# A container's name is never followed by a ":" in a name, so such a pattern
# names nothing until the move of the names rewrites it ("Migrating").
OLD_SCOPE_PREFIX = "${scope}:"


def under_scope(pattern: str) -> bool:
    """Whether ``pattern`` names only the scope's container or what it holds."""
    return pattern == SCOPE or pattern.startswith((SCOPE_PREFIX, OLD_SCOPE_PREFIX))


_SID = re.compile(r"^[A-Za-z0-9]{1,64}$")
_ACTION_PATTERN = re.compile(r"^(\*|[a-z?*][a-z0-9_?*]*:[A-Za-z0-9?*]+)$")
_STATEMENT_KEYS = frozenset({"sid", "effect", "actions", "resources"})
_DOCUMENT_KEYS = frozenset({"version", "statements"})


class PolicyValidationError(ValueError):
    """A policy document that does not validate; ``errors`` lists every failure."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("Invalid policy document: " + "; ".join(errors))


@dataclass(frozen=True)
class Statement:
    effect: Effect
    actions: tuple[str, ...]
    resources: tuple[str, ...]
    sid: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self.sid is not None:
            data["sid"] = self.sid
        data["effect"] = self.effect
        data["actions"] = list(self.actions)
        data["resources"] = list(self.resources)
        return data

    @property
    def uses_scope(self) -> bool:
        return any("scope" in variables(r) for r in self.resources)


@dataclass(frozen=True)
class PolicyDocument:
    statements: tuple[Statement, ...]
    version: str = POLICY_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "statements": [s.to_dict() for s in self.statements],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"), sort_keys=True)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PolicyDocument:
        """A stored document, as IAM wrote it: already validated, not rechecked."""
        return cls(
            version=str(data.get("version", POLICY_VERSION)),
            statements=tuple(
                Statement(
                    effect=raw["effect"],
                    actions=tuple(raw["actions"]),
                    resources=tuple(raw["resources"]),
                    sid=raw.get("sid"),
                )
                for raw in data.get("statements", ())
            ),
        )

    @property
    def uses_scope(self) -> bool:
        """Whether a statement names ``${scope}``: then it needs a scoped attachment."""
        return any(s.uses_scope for s in self.statements)

    @property
    def confined_to_scope(self) -> bool:
        """Whether every Allow resource pattern is ``${scope}`` or ``${scope}/...``.

        Only such a policy may be attached at a scope: the scope fills
        ``${scope}`` and nothing else, so an Allow naming anything outside it
        would let whoever may attach at a scope grant beyond it. A Deny only
        narrows, so it may name anything.
        """
        return all(
            under_scope(pattern)
            for statement in self.statements
            if statement.effect == "Allow"
            for pattern in statement.resources
        )

    @property
    def wholly_within_scope(self) -> bool:
        """Whether every resource pattern, a Deny's included, is ``${scope}``
        or ``${scope}/...``: what a policy owned by a container is, so that,
        attached to anyone, it neither grants nor refuses beyond its scope."""
        return all(
            under_scope(pattern)
            for statement in self.statements
            for pattern in statement.resources
        )


def denies_beyond_scope(documents: Iterable[PolicyDocument]) -> bool:
    """Whether a Deny of one of ``documents`` (a policy and its chain) names
    anything outside ``${scope}``: then it refuses beyond the scope it is
    attached at, and only whoever may attach it unscoped attaches it at one."""
    return any(
        not under_scope(pattern)
        for document in documents
        for statement in document.statements
        if statement.effect == "Deny"
        for pattern in statement.resources
    )


def check_owned_document(document: PolicyDocument, owner: str) -> None:
    """A policy owned by a container (``owner``) is written for its scope: its
    Allow and Deny patterns are all ``${scope}`` or ``${scope}/...``, so it is
    always attached at a scope and reaches nothing beyond it, whoever holds it.
    ``PolicyValidationError`` names each pattern that does not."""
    if owner == PLATFORM_SCOPE or document.wholly_within_scope:
        return
    outside = sorted(
        {
            pattern
            for statement in document.statements
            for pattern in statement.resources
            if not under_scope(pattern)
        }
    )
    raise PolicyValidationError(
        [
            f"A policy of {owner} names only ${{scope}} and resources under "
            f"${{scope}}/, and {pattern!r} is not"
            for pattern in outside
        ]
    )


def within_scope(statement: Statement) -> Statement | None:
    """``statement`` as a scoped attachment may grant it (None: it grants nothing).

    Evaluation applies this to every statement reached through a scoped
    attachment, whatever the policy says now: an Allow keeps only its
    ``${scope}`` and ``${scope}/`` patterns, so a policy edited after it was attached, or an
    attachment written to the store by other means, still cannot reach past
    its scope. A Deny is kept whole: it only narrows.
    """
    if statement.effect == "Deny":
        return statement
    kept = tuple(r for r in statement.resources if under_scope(r))
    if not kept:
        return None
    if kept == statement.resources:
        return statement
    return Statement(
        effect=statement.effect,
        actions=statement.actions,
        resources=kept,
        sid=statement.sid,
    )


def bind_variables(
    statement: Statement, values: Mapping[str, str | None]
) -> Statement | None:
    """``statement`` with the variables of ``values`` replaced in its resources.

    Other variables stay. A pattern naming one of them with a None value is
    dropped (it would match nothing); None when no pattern is left.
    """
    kept: list[str] = []
    for pattern in statement.resources:
        names = set(variables(pattern)) & set(values)
        if any(values[name] is None for name in names):
            continue
        for name in names:
            pattern = pattern.replace("${" + name + "}", cast(str, values[name]))
        kept.append(pattern)
    if not kept:
        return None
    if tuple(kept) == statement.resources:
        return statement
    return Statement(
        effect=statement.effect,
        actions=statement.actions,
        resources=tuple(kept),
        sid=statement.sid,
    )


def parse_policy_document(
    data: Mapping[str, Any] | str | PolicyDocument,
    catalogs: CatalogRegistry | None = None,
) -> PolicyDocument:
    """Validate ``data`` (a mapping, or YAML/JSON text) into a document.

    With ``catalogs``, action patterns are checked against the registered
    catalogs: a concrete action must be registered, a wildcard must match at
    least one registered action. Managed policies are generated by IAM and
    validated without catalogs, since they may name services that register later.
    """
    if isinstance(data, PolicyDocument):
        data = data.to_dict()
    if isinstance(data, str):
        if len(data.encode()) > MAX_DOCUMENT_BYTES:
            raise PolicyValidationError(
                [f"the document exceeds {MAX_DOCUMENT_BYTES} bytes"]
            )
        try:
            data = yaml.safe_load(data)
        except yaml.YAMLError as exc:
            raise PolicyValidationError([f"unreadable document: {exc}"]) from exc
    if not isinstance(data, Mapping):
        raise PolicyValidationError(["a policy document is a mapping"])

    errors: list[str] = []
    try:
        size = len(json.dumps(data, separators=(",", ":"), default=str).encode())
    except (TypeError, ValueError):
        size = 0
        errors.append("the document is not JSON-serializable")
    if size > MAX_DOCUMENT_BYTES:
        errors.append(f"the document exceeds {MAX_DOCUMENT_BYTES} bytes")

    for key in sorted(set(data) - _DOCUMENT_KEYS):
        errors.append(f"unknown field {key!r}")
    version = data.get("version")
    if isinstance(version, date) and version.isoformat() == POLICY_VERSION:
        version = POLICY_VERSION  # unquoted in YAML, it parses as a date
    if version is None:
        errors.append("version is required")
    elif version != POLICY_VERSION:
        errors.append(f"version must be {POLICY_VERSION!r}")

    raw_statements = data.get("statements")
    statements: list[Statement] = []
    if not isinstance(raw_statements, list):
        errors.append("statements is required and is a list")
    elif not 1 <= len(raw_statements) <= MAX_STATEMENTS:
        errors.append(f"statements holds 1 to {MAX_STATEMENTS} items")
    else:
        sids: set[str] = set()
        for index, raw in enumerate(raw_statements):
            statement = _statement(raw, f"statements[{index}]", errors, catalogs)
            if statement is None:
                continue
            if statement.sid is not None:
                if statement.sid in sids:
                    errors.append(
                        f"statements[{index}]: duplicate sid {statement.sid!r}"
                    )
                sids.add(statement.sid)
            statements.append(statement)

    if errors:
        raise PolicyValidationError(errors)
    return PolicyDocument(statements=tuple(statements))


def _statement(
    raw: Any, where: str, errors: list[str], catalogs: CatalogRegistry | None
) -> Statement | None:
    if not isinstance(raw, Mapping):
        errors.append(f"{where}: a statement is a mapping")
        return None
    before = len(errors)
    for key in sorted(set(raw) - _STATEMENT_KEYS):
        if key == "conditions":
            errors.append(f"{where}: conditions are reserved in {POLICY_VERSION}")
        else:
            errors.append(f"{where}: unknown field {key!r}")

    sid = raw.get("sid")
    if sid is not None and (not isinstance(sid, str) or not _SID.match(sid)):
        errors.append(f"{where}: sid must match {_SID.pattern}")

    effect = raw.get("effect")
    if effect not in ("Allow", "Deny"):
        errors.append(f"{where}: effect must be exactly 'Allow' or 'Deny'")

    actions = _patterns(raw.get("actions"), f"{where}.actions", errors)
    for pattern in actions:
        _check_action(pattern, f"{where}.actions", errors, catalogs)
    resources = _patterns(raw.get("resources"), f"{where}.resources", errors)
    for pattern in resources:
        _check_resource(pattern, f"{where}.resources", errors)

    if len(errors) != before:
        return None
    return Statement(
        effect=cast(Effect, effect),
        actions=tuple(actions),
        resources=tuple(resources),
        sid=sid,
    )


def _patterns(value: Any, where: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        errors.append(f"{where}: a list of strings is required")
        return []
    if not 1 <= len(value) <= MAX_PATTERNS:
        errors.append(f"{where}: 1 to {MAX_PATTERNS} patterns")
        return []
    return list(value)


def _check_action(
    pattern: str, where: str, errors: list[str], catalogs: CatalogRegistry | None
) -> None:
    if "${" in pattern:
        errors.append(f"{where}: variables are not allowed in actions ({pattern!r})")
        return
    if not _ACTION_PATTERN.match(pattern):
        errors.append(f"{where}: {pattern!r} is not <service>:<Action>")
        return
    if not has_wildcard(pattern):
        try:
            split_action(pattern)
        except ValueError:
            errors.append(f"{where}: {pattern!r} is not <service>:<Action>")
            return
    if catalogs is None:
        return
    if has_wildcard(pattern):
        if not catalogs.matching(pattern):
            errors.append(f"{where}: {pattern!r} matches no registered action")
    elif not catalogs.is_registered(pattern):
        errors.append(f"{where}: {pattern!r} is not a registered action")


def _check_resource(pattern: str, where: str, errors: list[str]) -> None:
    if (
        pattern != "*"
        and not pattern.startswith(PREFIX)
        and not pattern.startswith("${scope}")
    ):
        errors.append(f"{where}: {pattern!r} is '*' or starts with 'abi:'")
    for name in variables(pattern):
        if name not in POLICY_VARIABLES:
            errors.append(f"{where}: unknown variable ${{{name}}} in {pattern!r}")
    if pattern.count("${") != len(variables(pattern)):
        errors.append(f"{where}: unterminated variable in {pattern!r}")
