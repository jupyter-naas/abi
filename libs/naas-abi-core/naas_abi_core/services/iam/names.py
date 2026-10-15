"""Canonical resource names, action names and their wildcard patterns.

See docs/specs/rfcs/20261013_identity-and-authorization.md, §3.3 and §4:

    abi:<org>:<workspace>:<service>:<type>/<id>

Ids are percent-encoded UTF-8 (every octet outside RFC 3986 ``unreserved``),
so a canonical name never holds a raw ``*`` or ``?`` and a wildcard can never
be read as a literal. Callers build and parse names here, never by string
formatting. ``naas_abi_sdk.iam_names`` mirrors this module for SDK modules.
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
PLATFORM_SCOPE = "abi:-:-"

_SCOPE_ID = re.compile(r"^[a-z0-9_-]{1,64}$")
_SERVICE = re.compile(r"^[a-z][a-z0-9_]*$")
_ACTION_NAME = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_ACTION = re.compile(r"^([a-z][a-z0-9_]*):([A-Z][A-Za-z0-9]*)$")
# Inside a canonical id: unreserved characters, %XX escapes and "/".
_ID = re.compile(r"^(?:[A-Za-z0-9._~/-]|%[0-9A-F]{2})*$")
_VARIABLE = re.compile(r"\$\{([^}]*)\}")


@dataclass(frozen=True)
class ResourceName:
    """A parsed canonical name. ``id`` is the encoded form."""

    org: str
    workspace: str
    service: str
    type: str
    id: str

    @property
    def scope(self) -> str:
        """``abi:<org>:<workspace>``: the workspace, org or platform it sits in."""
        return f"abi:{self.org}:{self.workspace}"

    @property
    def segments(self) -> tuple[str, ...]:
        """The decoded id segments (one for opaque ids, ``()`` for singletons)."""
        if self.id == NONE:
            return ()
        return tuple(unquote(part) for part in self.id.split("/"))

    def __str__(self) -> str:
        return f"abi:{self.org}:{self.workspace}:{self.service}:{self.type}/{self.id}"


def encode_segment(value: str) -> str:
    """Percent-encode one id segment: everything outside ``unreserved``."""
    if not isinstance(value, str):
        raise TypeError("An id segment is a string")
    return quote(value, safe="")


def encode_id(parts: str | Sequence[str], kind: IdKind = "opaque") -> str:
    """The canonical id of a resource (RFC §4.3).

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


def resource_name(
    service: str,
    type: str,
    parts: str | Sequence[str] = (),
    *,
    kind: IdKind = "opaque",
    org: str = NONE,
    workspace: str = NONE,
) -> str:
    """Build a canonical name, platform-level unless ``org``/``workspace`` say otherwise."""
    _check_scope_id(org, "org")
    _check_scope_id(workspace, "workspace")
    if not _SERVICE.match(service):
        raise ValueError(f"Invalid service name {service!r}")
    if not _SERVICE.match(type):
        raise ValueError(f"Invalid resource type {type!r}")
    return f"abi:{org}:{workspace}:{service}:{type}/{encode_id(parts, kind)}"


def parse_resource_name(name: str) -> ResourceName:
    """Parse a canonical name; raises ``ValueError`` for anything else."""
    if not name.startswith(PREFIX):
        raise ValueError(f"A resource name starts with 'abi:': {name!r}")
    fields = name[len(PREFIX) :].split(":", 3)
    if len(fields) != 4:
        raise ValueError(f"Malformed resource name {name!r}")
    org, workspace, service, rest = fields
    type_, slash, id_ = rest.partition("/")
    if not slash or not id_:
        raise ValueError(f"A resource name ends with <type>/<id>: {name!r}")
    _check_scope_id(org, "org")
    _check_scope_id(workspace, "workspace")
    if not _SERVICE.match(service):
        raise ValueError(f"Invalid service in {name!r}")
    if not _SERVICE.match(type_):
        raise ValueError(f"Invalid resource type in {name!r}")
    if id_ != NONE and not _ID.match(id_):
        raise ValueError(f"The id of {name!r} is not canonically encoded")
    return ResourceName(org, workspace, service, type_, id_)


def scope_name(org: str = NONE, workspace: str = NONE) -> str:
    """``abi:<org>:<workspace>``, the form of an attachment scope."""
    _check_scope_id(org, "org")
    _check_scope_id(workspace, "workspace")
    return f"abi:{org}:{workspace}"


def validate_scope(scope: str) -> str:
    """Check an attachment scope (RFC §3.4): ``abi:<org>:<ws>``, ``abi:<org>:-``,
    ``abi:<org>:*`` or ``abi:-:-``."""
    if not scope.startswith(PREFIX):
        raise ValueError(f"A scope starts with 'abi:': {scope!r}")
    fields = scope[len(PREFIX) :].split(":")
    if len(fields) != 2:
        raise ValueError(f"A scope is abi:<org>:<workspace>: {scope!r}")
    org, workspace = fields
    _check_scope_id(org, "org")
    if workspace != "*":
        _check_scope_id(workspace, "workspace")
    if org == NONE and workspace != NONE:
        raise ValueError(f"A platform scope is abi:-:-, not {scope!r}")
    return scope


def scope_fields(scope: str) -> tuple[str, str]:
    """The ``(org, workspace)`` of a valid scope (``workspace`` may be ``*``)."""
    org, workspace = validate_scope(scope)[len(PREFIX) :].split(":")
    return org, workspace


def _check_scope_id(value: str, field: str) -> None:
    if value != NONE and not _SCOPE_ID.match(value):
        raise ValueError(f"Invalid {field} id {value!r}")


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
# Wildcard patterns (RFC §3.3, §4.5): "*" any run, "?" one character.
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

    A statement whose resource holds an unresolved variable matches nothing
    (RFC §3.4).
    """
    unresolved = False

    def replace(found: re.Match[str]) -> str:
        nonlocal unresolved
        value = values.get(found.group(1))
        if value is None:
            unresolved = True
            return ""
        return value

    result = _VARIABLE.sub(replace, pattern)
    return None if unresolved else result
