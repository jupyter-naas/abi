"""Canonical resource names, action names and their wildcard patterns.

Grammar and encoding: ``AGENTS.md``, "Resource names":

    abi:<org>:<workspace>:<service>:<type>/<id>

Ids are percent-encoded UTF-8 (every octet outside RFC 3986 ``unreserved``),
so a canonical name never holds a raw ``*`` or ``?`` and a wildcard can never
be read as a literal. Callers build and parse names here, never by string
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
# The workspace field of what spans every workspace of an org: the encoded "*",
# which no workspace id can be. Only org-wide attachments are named with it, so
# "abi:<org>:*" patterns reach them and "abi:<org>:-:" ones never do.
ALL_WORKSPACES = "%2A"
# The org field of what spans every org: unscoped attachments, named
# abi:%2A:%2A:iam:attachment/..., and the platform's own policies and groups,
# abi:%2A:%2A:iam:policy/... and iam:group/.... No ${scope} expands to it (no
# org id is "%2A"), so a role at any scope, the platform's abi:-:- included,
# never reaches them: only grants written for every org ("*", "abi:*:...") do.
ALL_ORGS = "%2A"
# The only resource type the workspace marker may name, with an org (org-wide).
ORG_WIDE_TYPE = ("iam", "attachment")
# Sets are written where only the level above reaches (``sets.write_resource``):
# an org's at abi:%2A:%2A:iam:set/<org>, a workspace's at abi:<org>:%2A:iam:set/<ws>.
SET_TYPE = ("iam", "set")
# The resource types the workspace marker may name, with an org.
ORG_WIDE_TYPES = frozenset({ORG_WIDE_TYPE, SET_TYPE})
# The resource types the org marker may name, with the workspace marker.
EVERY_ORG_TYPES = frozenset(
    {ORG_WIDE_TYPE, ("iam", "policy"), ("iam", "group"), SET_TYPE}
)
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
    if not _SERVICE.match(service):
        raise ValueError(f"Invalid service name {service!r}")
    if not _SERVICE.match(type):
        raise ValueError(f"Invalid resource type {type!r}")
    _check_org(org, workspace, service, type)
    _check_workspace(workspace, org, service, type)
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
    if not _SERVICE.match(service):
        raise ValueError(f"Invalid service in {name!r}")
    if not _SERVICE.match(type_):
        raise ValueError(f"Invalid resource type in {name!r}")
    _check_org(org, workspace, service, type_)
    _check_workspace(workspace, org, service, type_)
    if id_ != NONE and not _ID.match(id_):
        raise ValueError(f"The id of {name!r} is not canonically encoded")
    return ResourceName(org, workspace, service, type_, id_)


def scope_name(org: str = NONE, workspace: str = NONE) -> str:
    """``abi:<org>:<workspace>``, the form of an attachment scope."""
    _check_scope_id(org, "org")
    _check_scope_id(workspace, "workspace")
    return f"abi:{org}:{workspace}"


def validate_scope(scope: str) -> str:
    """Check an attachment scope: ``abi:<org>:<ws>``, ``abi:<org>:-``,
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


def validate_owner_scope(scope: str) -> str:
    """Check the scope that owns a policy or a group: the platform ``abi:-:-``,
    an org ``abi:<org>:-`` or a workspace ``abi:<org>:<ws>``, never org-wide."""
    if scope_fields(scope)[1] == "*":
        raise ValueError(
            "A policy or a group is owned by the platform, an org or a workspace, "
            f"not {scope!r}"
        )
    return scope


def within_owner(owner: str, scope: str | None) -> bool:
    """Whether an attachment at ``scope`` is at ``owner``'s level or below: an
    org's at the org, org-wide or at any of its workspaces, a workspace's at
    that workspace only, the platform's anywhere (unscoped included)."""
    if owner == PLATFORM_SCOPE:
        return True
    if scope is None:
        return False
    owner_org, owner_workspace = scope_fields(owner)
    org, workspace = scope_fields(scope)
    return org == owner_org and owner_workspace in (NONE, workspace)


def owner_ancestors(scope: str) -> list[str]:
    """The owner scopes above ``scope``, nearest first: a workspace's org, then
    the platform; an org's platform; none for the platform."""
    org, workspace = scope_fields(validate_owner_scope(scope))
    if org == NONE:
        return []
    if workspace == NONE:
        return [PLATFORM_SCOPE]
    return [scope_name(org), PLATFORM_SCOPE]


def _check_org(org: str, workspace: str, service: str, type: str) -> None:
    if org == ALL_ORGS:
        # Only unscoped attachments and the platform's policies and groups.
        if (service, type) not in EVERY_ORG_TYPES or workspace != ALL_WORKSPACES:
            raise ValueError(
                f"Org {ALL_ORGS} names unscoped attachments, the platform's "
                f"policies and groups, and the orgs' sets only, abi:{ALL_ORGS}:{ALL_WORKSPACES}:iam:..."
            )
        return
    _check_scope_id(org, "org")


def _check_workspace(workspace: str, org: str, service: str, type: str) -> None:
    if workspace == ALL_WORKSPACES:
        if org == ALL_ORGS:
            return  # checked with the org
        # Only org-wide attachments and workspace sets span every workspace.
        if (service, type) not in ORG_WIDE_TYPES:
            raise ValueError(
                f"Workspace {ALL_WORKSPACES} names org-wide attachments and "
                f"workspace sets only, "
                f"not {service}:{type}"
            )
        if org == NONE:
            raise ValueError("Every workspace of an org needs an org")
        return
    _check_scope_id(workspace, "workspace")


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

    def replace(found: re.Match[str]) -> str:
        nonlocal unresolved
        value = values.get(found.group(1))
        if value is None:
            unresolved = True
            return ""
        return value

    result = _VARIABLE.sub(replace, pattern)
    return None if unresolved else result
