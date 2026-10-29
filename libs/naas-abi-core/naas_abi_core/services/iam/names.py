"""Canonical resource names, action names and their wildcard patterns.

Grammar and encoding: ``AGENTS.md``, "Resource names". A name is a path of
containers:

    abi:<service>:<type>/<id>/.../<service>:<type>/<id>

``abi:``, the steps of the containers it sits in from the top, then its own
step. Ids are percent-encoded UTF-8 (every octet outside RFC 3986
``unreserved``), so a canonical name never holds a raw ``*`` or ``?`` and a
wildcard can never be read as a literal, and a raw ``:`` only ever separates a
step's service from its type. A container's id is one segment; only the last
step's id may be a path. Callers build and parse names here, never by string
formatting.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal
from urllib.parse import quote, unquote

IdKind = Literal["opaque", "path", "singleton"]

NONE = "-"
PREFIX = "abi:"
# The path of no container: what is platform-level, the platform as an owner, a
# scope or a placement. "${scope}/" reads "abi:" there.
PLATFORM = PREFIX
PLATFORM_SCOPE = PLATFORM
# The suffix of a scope below a container: it counts at every container under it.
BELOW = "/*"
# Below the platform: any container, or the platform. Never an attachment's scope:
# how a platform policy's ``${scope}`` is read when nobody attached it yet.
EVERYWHERE = PREFIX + "*"
# A container nobody registers: where an owner, a scope or a placement of the
# grammar before container paths resolves until it is rewritten. Only grants that
# span every container ("*", "abi:*/...") reach what is named in it.
UNRESOLVED = "abi:iam:unresolved/-"
# The old platform scope, read as the platform.
_OLD_PLATFORM = "abi:-:-"

_SERVICE = re.compile(r"^[a-z][a-z0-9_]*$")
_ACTION_NAME = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_ACTION = re.compile(r"^([a-z][a-z0-9_]*):([A-Z][A-Za-z0-9]*)$")
# One id segment: unreserved characters and %XX escapes.
_SEGMENT = re.compile(r"^(?:[A-Za-z0-9._~-]|%[0-9A-F]{2})+$")
# Inside a canonical id: unreserved characters, %XX escapes and "/".
_ID = re.compile(r"^(?:[A-Za-z0-9._~/-]|%[0-9A-F]{2})*$")
_VARIABLE = re.compile(r"\$\{([^}]*)\}")
_SCOPE_SLASH = "${scope}/"


@dataclass(frozen=True)
class Step:
    """One step of a path: ``<service>:<type>/<id>``, ``id`` encoded."""

    service: str
    type: str
    id: str

    @property
    def value(self) -> str:
        """The decoded id of a container step (one segment)."""
        return unquote(self.id)

    def __str__(self) -> str:
        return f"{self.service}:{self.type}/{self.id}"


@dataclass(frozen=True)
class ResourceName:
    """A parsed canonical name: the steps of its containers, then its own.
    ``id`` is the encoded form."""

    containers: tuple[Step, ...]
    service: str
    type: str
    id: str

    @property
    def container(self) -> str:
        """The name of the container it sits in, ``abi:`` for the platform."""
        return _join(self.containers)

    @property
    def segments(self) -> tuple[str, ...]:
        """The decoded id segments (one for opaque ids, ``()`` for singletons)."""
        if self.id == NONE:
            return ()
        return tuple(unquote(part) for part in self.id.split("/"))

    def __str__(self) -> str:
        return f"{_prefix(self.container)}{self.service}:{self.type}/{self.id}"


def _join(steps: Sequence[Step]) -> str:
    return PREFIX + "/".join(str(step) for step in steps) if steps else PLATFORM


def _prefix(container: str) -> str:
    """What a step is written after: ``abi:`` at the platform, ``<container>/``."""
    return PLATFORM if container == PLATFORM else container + "/"


def encode_segment(value: str) -> str:
    """Percent-encode one id segment: everything outside ``unreserved``."""
    if not isinstance(value, str):
        raise TypeError("An id segment is a string")
    return quote(value, safe="")


def encode_id(parts: str | Sequence[str], kind: IdKind = "opaque") -> str:
    """The canonical id of a resource.

    * ``opaque``: one value, wholly encoded (a ``/`` inside becomes ``%2F``);
    * ``path``: each part encoded on its own, joined with a raw ``/``;
    * ``singleton``: ``-``.
    """
    if kind == "singleton":
        return NONE
    values = [parts] if isinstance(parts, str) else list(parts)
    if kind == "opaque":
        if len(values) != 1:
            raise ValueError("An opaque id is exactly one value")
        if values[0] == "":
            raise ValueError("An opaque id cannot be empty")
        return encode_segment(values[0])
    if kind == "path":
        if not values:
            raise ValueError("A path id needs at least one part")
        return "/".join(encode_segment(value) for value in values)
    raise ValueError(f"Unknown id kind {kind!r}")


def path_parts(path: str) -> list[str]:
    """A slash-separated path as path-id parts: object storage's ``prefix/key``."""
    return path.strip("/").split("/") if path.strip("/") else []


def _check_type(service: str, type: str) -> None:
    if not _SERVICE.match(service):
        raise ValueError(f"Invalid service name {service!r}")
    if not _SERVICE.match(type):
        raise ValueError(f"Invalid resource type {type!r}")


def resource_name(
    service: str,
    type: str,
    parts: str | Sequence[str] = (),
    *,
    kind: IdKind = "opaque",
    container: str = PLATFORM,
) -> str:
    """Build a canonical name in ``container`` (a container's name; the platform
    by default)."""
    _check_type(service, type)
    parse_container(container)
    return f"{_prefix(container)}{service}:{type}/{encode_id(parts, kind)}"


def container_name(service: str, type: str, id: str, *, parent: str = PLATFORM) -> str:
    """The name of a container: its own step, ``<service>:<type>/<id>``, in
    ``parent``. Its id is one segment."""
    return resource_name(service, type, id, container=parent)


def _steps(body: str, name: str) -> list[tuple[str, str, list[str]]]:
    """The ``(service, type, id tokens)`` of each step of ``body``, the part of
    a name after ``abi:``."""
    steps: list[tuple[str, str, list[str]]] = []
    for token in body.split("/"):
        if ":" in token:
            service, _, type_ = token.partition(":")
            if ":" in type_ or not _SERVICE.match(service) or not _SERVICE.match(type_):
                raise ValueError(f"Malformed step {token!r} in {name!r}")
            steps.append((service, type_, []))
        elif not steps:
            raise ValueError(f"A resource name is abi:<service>:<type>/<id>: {name!r}")
        else:
            steps[-1][2].append(token)
    return steps


@lru_cache(maxsize=16384)
def parse_resource_name(name: str) -> ResourceName:
    """Parse a canonical name; raises ``ValueError`` for anything else."""
    if not isinstance(name, str) or not name.startswith(PREFIX):
        raise ValueError(f"A resource name starts with 'abi:': {name!r}")
    steps = _steps(name[len(PREFIX) :], name)
    if not steps:
        raise ValueError(f"Malformed resource name {name!r}")
    containers = tuple(_container_step(step, name) for step in steps[:-1])
    service, type_, tokens = steps[-1]
    id_ = "/".join(tokens)
    if not tokens or not id_:
        raise ValueError(f"A resource name ends with <type>/<id>: {name!r}")
    if id_ != NONE and not _ID.match(id_):
        raise ValueError(f"The id of {name!r} is not canonically encoded")
    return ResourceName(containers, service, type_, id_)


def _container_step(step: tuple[str, str, list[str]], name: str) -> Step:
    service, type_, tokens = step
    if len(tokens) != 1 or not _SEGMENT.match(tokens[0]):
        raise ValueError(f"A container's id is one encoded segment: {name!r}")
    return Step(service, type_, tokens[0])


@lru_cache(maxsize=16384)
def parse_container(name: str) -> tuple[Step, ...]:
    """The steps of a container's name, ``()`` for the platform ``abi:``."""
    if name == PLATFORM:
        return ()
    if not isinstance(name, str) or not name.startswith(PREFIX):
        raise ValueError(f"A container's name starts with 'abi:': {name!r}")
    steps = _steps(name[len(PREFIX) :], name)
    if not steps:
        raise ValueError(f"Malformed container name {name!r}")
    return tuple(_container_step(step, name) for step in steps)


def path_of(name: ResourceName) -> list[str]:
    """The containers a name sits in, from the top down to its own."""
    return [
        _join(name.containers[:depth]) for depth in range(1, len(name.containers) + 1)
    ]


# The platform's own policies, groups and attachments (unscoped ones included):
# no ${scope} names them, the platform's included (AGENTS.md, "Attachments and scope").
_PLATFORM_OWN = tuple(PREFIX + f"iam:{t}/" for t in ("policy", "group", "attachment"))


def platform_own(resource: str) -> bool:
    return resource.startswith(_PLATFORM_OWN)


def is_container_name(value: str) -> bool:
    try:
        parse_container(value)
    except (TypeError, ValueError):
        return False
    return True


def parent_of(container: str) -> str:
    """The container ``container`` sits in, the platform for a top one."""
    return _join(parse_container(container)[:-1])


def top_container(container: str) -> str:
    """The first step of a container's path (itself for a top one); the platform
    for the platform."""
    return _join(parse_container(container)[:1])


def ancestors(container: str) -> list[str]:
    """The containers ``container`` sits in, nearest first, the platform last."""
    steps = parse_container(container)
    return [_join(steps[:depth]) for depth in range(len(steps) - 1, -1, -1)]


def within(container: str, ancestor: str) -> bool:
    """Whether ``container`` is ``ancestor`` or sits below it (anything is within
    the platform)."""
    if ancestor == PLATFORM:
        return True
    return container == ancestor or container.startswith(ancestor + "/")


def anywhere(rest: str) -> list[str]:
    """Patterns for ``<service>:<type>/<id>`` (a pattern) at the platform and in
    any container: ``abi:<rest>`` and ``abi:*/<rest>``."""
    return [PREFIX + rest, PREFIX + "*/" + rest]


# A scope or an owner of the grammar before container paths, ``abi:<x>:<y>``.
_OLD_SCOPE = re.compile(r"^abi:[^:/]+:[^:/]+$")


def is_old_scope(value: str | None) -> bool:
    """Whether ``value`` is a scope or an owner of the grammar before container
    paths (``abi:<org>:<ws>``, ``abi:<org>:-``, ``abi:<org>:*``): written only by
    the start-up moves that predate them, named in ``UNRESOLVED`` until the
    names are rewritten."""
    return value is not None and bool(_OLD_SCOPE.match(value))


def as_container(value: str | None) -> str:
    """A stored owner, scope or placement as a container: itself when it is one
    (or the platform), the platform for the old ``abi:-:-``, else ``UNRESOLVED``
    (the grammar before container paths, waiting to be rewritten)."""
    if value is None or value == _OLD_PLATFORM:
        return PLATFORM
    return value if is_container_name(value) else UNRESOLVED


# ---------------------------------------------------------------------------
# Scopes and owners
# ---------------------------------------------------------------------------


def below(container: str) -> str:
    """The scope below ``container``: at it and at every container under it."""
    if container == PLATFORM:
        raise ValueError("Below the platform is everywhere: attach without a scope")
    parse_container(container)
    return container + BELOW


def is_below(scope: str | None) -> bool:
    return scope is not None and scope.endswith(BELOW)


def container_of_scope(scope: str) -> str:
    """The container of a scope (a below one's, without ``/*``)."""
    return scope.removesuffix(BELOW)


def validate_scope(scope: str) -> str:
    """Check an attachment scope: a container, below one (``<container>/*``) or
    the platform ``abi:``."""
    if scope == PLATFORM:
        return scope
    if not isinstance(scope, str) or not scope.startswith(PREFIX):
        raise ValueError(f"A scope is a container's name or abi:: {scope!r}")
    container = container_of_scope(scope)
    if container == PLATFORM or (scope.endswith(BELOW) and container + BELOW != scope):
        raise ValueError(f"Invalid scope {scope!r}")
    try:
        parse_container(container)
    except ValueError as error:
        raise ValueError(f"Invalid scope {scope!r}: {error}") from error
    return scope


def validate_owner_scope(scope: str) -> str:
    """Check the owner of a policy or a group: the platform or a container,
    never below one."""
    if is_below(scope):
        raise ValueError(f"A policy or a group is owned by a container, not {scope!r}")
    return validate_scope(scope)


def within_owner(owner: str, scope: str | None) -> bool:
    """Whether an attachment at ``scope`` is at ``owner`` or below it: the
    platform's anywhere (unscoped included), a container's at it, below it or at
    any container inside it."""
    if owner == PLATFORM:
        return True
    if scope is None:
        return False
    # The grammar before container paths: both in UNRESOLVED until rewritten.
    return within(as_container(container_of_scope(scope)), as_container(owner))


def owner_ancestors(container: str) -> list[str]:
    """The owners above ``container``, nearest first: its containers up to the
    platform; none for the platform."""
    return ancestors(container) if container != PLATFORM else []


def expand_scope(pattern: str, scope: str) -> str | None:
    """``pattern`` with ``${scope}`` filled with a container (or the platform,
    where ``${scope}/`` reads ``abi:`` and ``${scope}`` alone is unresolved)."""
    return substitute(pattern, {"scope": scope})


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


def action_name(service: str, action: str) -> str:
    """``<service>:<Action>``."""
    name = f"{service}:{action}"
    if not _ACTION.match(name):
        raise ValueError(f"Invalid action {name!r}")
    return name


def split_action(action: str) -> tuple[str, str]:
    """The ``(service, Action)`` of a concrete action name."""
    found = _ACTION.match(action)
    if found is None:
        raise ValueError(f"Invalid action {action!r}")
    return found.group(1), found.group(2)


def is_valid_service(name: str) -> bool:
    return bool(_SERVICE.match(name))


def is_valid_action_name(name: str) -> bool:
    """A PascalCase action name, without its service."""
    return bool(_ACTION_NAME.match(name))


# ---------------------------------------------------------------------------
# Wildcard patterns: "*" any run, "?" one character.
# ---------------------------------------------------------------------------


def has_wildcard(pattern: str) -> bool:
    return "*" in pattern or "?" in pattern


@lru_cache(maxsize=8192)
def _compiled(pattern: str) -> re.Pattern[str]:
    regex = "".join(
        ".*" if char == "*" else "." if char == "?" else re.escape(char)
        for char in pattern
    )
    return re.compile(regex, re.DOTALL)


def matches(pattern: str, value: str) -> bool:
    """Whether ``pattern`` matches the whole of ``value``. Case-sensitive."""
    if pattern == "*":
        return True
    if not has_wildcard(pattern):
        return pattern == value
    return _compiled(pattern).fullmatch(value) is not None


def literal_prefix(pattern: str) -> str:
    """The characters before the first wildcard: every match starts with them."""
    for index, char in enumerate(pattern):
        if char in "*?":
            return pattern[:index]
    return pattern


def variables(pattern: str) -> list[str]:
    """The ``${...}`` variable names in ``pattern``, in order."""
    return _VARIABLE.findall(pattern)


def substitute(pattern: str, values: dict[str, str | None]) -> str | None:
    """``pattern`` with its variables replaced; None when one is unresolved.

    A statement whose resource holds an unresolved variable matches nothing.
    """
    unresolved = False
    if values.get("scope") == PLATFORM and _SCOPE_SLASH in pattern:
        pattern = pattern.replace(_SCOPE_SLASH, PREFIX)

    def replace(found: re.Match[str]) -> str:
        nonlocal unresolved
        value = values.get(found.group(1))
        if value is None or (found.group(1) == "scope" and value == PLATFORM):
            unresolved = True
            return ""
        return value

    result = _VARIABLE.sub(replace, pattern)
    return None if unresolved else result
