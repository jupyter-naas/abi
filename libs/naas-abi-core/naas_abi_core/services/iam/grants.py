"""Grant only what you hold (``AGENTS.md``, "Grant only what you hold").

Whether what a grant gives is held by whoever gives it. A grant is a policy's
Allow statements as they apply at one scope (``${scope}`` filled, and
``policy.within_scope`` applied at a scope); the giver's holdings are the
statements of each side that decides for them (the user, an actor that is not
first-party, the token's narrowing). For each action an Allow statement
matches, its wildcards expanded against the registered catalogs, every
resource it names must be named by an Allow of each side for that action, and
by no Deny of any side.

Resource patterns are compared as languages: ``*`` is any run (``:`` and
``/`` included), ``?`` exactly one character (one of the three of ``%2F``).
Only names of the action's resource types count
(``abi:<org>:<ws>:<service>:<type>/<id>``, each field free of ``:``), so
``${scope}:triple_store:*`` is no wider than ``${scope}:triple_store:graph/*``
for an action on graphs only. Containment is decided on the product of the
patterns' automata; when that takes more than ``STATE_BUDGET`` states, it is not
proven, and the grant is refused.

Variables keep their form: ``${principal.id}`` and ``${user.id}`` in a grant
are covered by the giver holding the same variable at that place (or a
wildcard), never by a literal id; the module variables likewise.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from naas_abi_core.services.iam.catalog import CatalogRegistry
from naas_abi_core.services.iam.IAMPorts import GrantableAction, GrantableCatalog
from naas_abi_core.services.iam.names import (
    literal_prefix,
    matches,
    scope_fields,
    split_action,
)
from naas_abi_core.services.iam.policy import Statement, within_scope

# Variables, as one character no canonical name holds: a grant's variable is
# covered by the same variable, or by a wildcard, never by a literal id.
MARKS = {
    "principal.id": "\x01",
    "user.id": "\x02",
    "module.id": "\x03",
    "module.project": "\x04",
}
_SHOWN = {mark: "${" + name + "}" for name, mark in MARKS.items()}
STATE_BUDGET = 20_000

# Pattern tokens: a literal character, "?" (one), "*" (a run), and, in the
# names of a type only, one character or a run of characters that are not ":".
_LIT, _ONE, _RUN, _FIELD_ONE, _FIELD_RUN = range(5)
Token = tuple[int, str]
Tokens = tuple[Token, ...]


class Unproven(Exception):
    """Containment took more than ``STATE_BUDGET`` states to decide."""


def held_form(pattern: str, scope: str | None) -> str | None:
    """``pattern`` with ``${scope}`` filled and the other variables as marks.

    None when it names ``${scope}`` and there is no scope: it matches nothing.
    """
    if "${scope}" in pattern:
        if scope is None:
            return None
        pattern = pattern.replace("${scope}", scope)
    for name, mark in MARKS.items():
        pattern = pattern.replace("${" + name + "}", mark)
    return pattern


def shown(pattern: str) -> str:
    """A pattern in held form, as a person reads it: marks back to variables."""
    for mark, variable in _SHOWN.items():
        pattern = pattern.replace(mark, variable)
    return pattern


@lru_cache(maxsize=8192)
def _glob(pattern: str) -> Tokens:
    return tuple(
        (_RUN, "") if c == "*" else (_ONE, "") if c == "?" else (_LIT, c)
        for c in pattern
    )


@lru_cache(maxsize=1024)
def universe(service: str, resource_type: str) -> Tokens:
    """The canonical names of a resource type,
    ``abi:<org>:<ws>:<service>:<type>/<id>`` (no field holds a raw ``:``)."""
    field_: Tokens = ((_FIELD_ONE, ""), (_FIELD_RUN, ""))
    return (
        *_glob("abi:"),
        *field_,
        (_LIT, ":"),
        *field_,
        *_glob(f":{service}:{resource_type}/"),
        *field_,
    )


EVERYTHING: Tokens = ((_RUN, ""),)


def _close(tokens: Tokens, states: Iterable[int]) -> frozenset[int]:
    found: set[int] = set()
    for state in states:
        while state not in found:
            found.add(state)
            if state < len(tokens) and tokens[state][0] in (_RUN, _FIELD_RUN):
                state += 1
            else:
                break
    return frozenset(found)


def _step(tokens: Tokens, states: frozenset[int], char: str) -> frozenset[int]:
    after: list[int] = []
    for state in states:
        if state == len(tokens):
            continue
        kind, literal = tokens[state]
        if kind == _LIT:
            if char == literal:
                after.append(state + 1)
        elif kind == _ONE:
            after.append(state + 1)
        elif kind == _RUN:
            after.append(state)
        elif char != ":":
            after.append(state + 1 if kind == _FIELD_ONE else state)
    return _close(tokens, after)


def _accepts(tokens: Tokens, states: frozenset[int]) -> bool:
    return len(tokens) in states


def _alphabet(*token_lists: Tokens) -> list[str]:
    """Every literal character, ``:``, and one character none of them is: the
    patterns treat every other character alike."""
    literals = {c for tokens in token_lists for kind, c in tokens if kind == _LIT}
    literals.add(":")
    other = next(chr(c) for c in range(0x10, 0x110000) if chr(c) not in literals)
    return sorted(literals) + [other]


def _compatible(a: str, b: str) -> bool:
    """Whether some name could match both: one literal prefix extends the other."""
    pa, pb = literal_prefix(a), literal_prefix(b)
    return pa.startswith(pb) or pb.startswith(pa)


def _search(
    grant: str,
    others: tuple[str, ...],
    within: Tokens,
    goal: Literal["uncovered", "overlap"],
) -> bool:
    """Whether some name of ``within`` matches ``grant`` and none of ``others``
    (``uncovered``), or ``grant`` and one of ``others`` (``overlap``)."""
    g, u = _glob(grant), within
    hs = [_glob(other) for other in others]
    alphabet = _alphabet(g, u, *hs)
    State = tuple[frozenset[int], frozenset[int], tuple[frozenset[int], ...]]
    start: State = (
        _close(g, (0,)),
        _close(u, (0,)),
        tuple(_close(h, (0,)) for h in hs),
    )
    seen = {start}
    queue = deque([start])
    while queue:
        gs, us, hstates = queue.popleft()
        if _accepts(g, gs) and _accepts(u, us):
            held = any(_accepts(h, s) for h, s in zip(hs, hstates))
            if (goal == "uncovered" and not held) or (goal == "overlap" and held):
                return True
        for char in alphabet:
            nxt: State = (
                _step(g, gs, char),
                _step(u, us, char),
                tuple(_step(h, s, char) for h, s in zip(hs, hstates)),
            )
            if not nxt[0] or not nxt[1] or (goal == "overlap" and not any(nxt[2])):
                continue
            if nxt not in seen:
                if len(seen) >= STATE_BUDGET:
                    raise Unproven(grant)
                seen.add(nxt)
                queue.append(nxt)
    return False


@lru_cache(maxsize=16384)
def _covered(grant: str, held: tuple[str, ...], within: Tokens) -> bool:
    if grant in held or "*" in held:
        return True
    held = tuple(h for h in held if _compatible(grant, h))
    if not held:
        return not _search(grant, (), within, "uncovered")
    try:
        return not _search(grant, held, within, "uncovered")
    except Unproven:
        return False


@lru_cache(maxsize=16384)
def _overlaps(grant: str, others: tuple[str, ...], within: Tokens) -> bool:
    others = tuple(o for o in others if _compatible(grant, o))
    if not others:
        return False
    try:
        return _search(grant, others, within, "overlap")
    except Unproven:
        return True


def covered(grant: str, held: Iterable[str], within: Tokens = EVERYTHING) -> bool:
    """Whether every name of ``within`` that ``grant`` matches is matched by
    one of ``held``. False when that is not proven."""
    return _covered(grant, tuple(sorted(set(held))), within)


def overlaps(grant: str, others: Iterable[str], within: Tokens = EVERYTHING) -> bool:
    """Whether some name of ``within`` matches ``grant`` and one of ``others``.
    True when that is not disproven."""
    return _overlaps(grant, tuple(sorted(set(others))), within)


# ---------------------------------------------------------------------------
# Holdings: what a caller holds, side by side.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HeldStatement:
    """A statement of the giver, its resources in held form."""

    effect: Literal["Allow", "Deny"]
    actions: tuple[str, ...]
    resources: tuple[str, ...]
    policy_id: str | None = None


@dataclass(frozen=True)
class Side:
    """One side that decides for the giver: the user, an actor acting for them,
    or the narrowing of their credential (Allow statements only)."""

    statements: tuple[HeldStatement, ...]
    lacks: str  # how a refusal says this side does not hold it
    active: bool = True


@dataclass(frozen=True)
class Uncovered:
    """The first part of a grant its giver does not hold."""

    statement: int
    sid: str | None
    action: str
    resource: str
    reason: str


@dataclass
class Holdings:
    sides: Sequence[Side]
    catalogs: CatalogRegistry
    _allows: dict[tuple[int, str], tuple[str, ...]] = field(default_factory=dict)
    _denies: dict[tuple[int, str], tuple[tuple[str, str | None], ...]] = field(
        default_factory=dict
    )

    # -- what one side holds for one action ------------------------------------

    def _allowed(self, index: int, action: str) -> tuple[str, ...]:
        key = (index, action)
        if key not in self._allows:
            side = self.sides[index]
            self._allows[key] = (
                tuple(
                    sorted(
                        {
                            r
                            for s in side.statements
                            if s.effect == "Allow"
                            and any(matches(p, action) for p in s.actions)
                            for r in s.resources
                        }
                    )
                )
                if side.active
                else ()
            )
        return self._allows[key]

    def _denied(self, index: int, action: str) -> tuple[tuple[str, str | None], ...]:
        key = (index, action)
        if key not in self._denies:
            self._denies[key] = tuple(
                sorted(
                    {
                        (r, s.policy_id)
                        for s in self.sides[index].statements
                        if s.effect == "Deny"
                        and any(matches(p, action) for p in s.actions)
                        for r in s.resources
                    },
                    key=lambda d: (d[0], d[1] or ""),
                )
            )
        return self._denies[key]

    def _universes(self, action: str) -> list[Tokens]:
        try:
            service, name = split_action(action)
        except ValueError:
            return [EVERYTHING]
        catalog = self.catalogs.get(service)
        spec = catalog.action(name) if catalog is not None else None
        if spec is None or not spec.resource_types:
            return [EVERYTHING]
        return [universe(service, t) for t in spec.resource_types]

    def _actions(self, patterns: Iterable[str]) -> list[str]:
        """Each action a statement's patterns match: the registered ones a
        wildcard matches, and a concrete name as it is."""
        found: dict[str, None] = {}
        for pattern in patterns:
            if "*" in pattern or "?" in pattern:
                found.update(dict.fromkeys(self.catalogs.matching(pattern)))
            else:
                found[pattern] = None
        return list(found)

    # -- the rule ----------------------------------------------------------------

    def first_uncovered(
        self, statements: Sequence[Statement], scope: str | None
    ) -> Uncovered | None:
        """The first (statement, action, resource) of the grant of
        ``statements`` at ``scope`` (None: unscoped) the giver does not hold."""
        for index, raw in enumerate(statements):
            if raw.effect != "Allow":
                continue  # a Deny only narrows: it needs no cover
            statement = within_scope(raw) if scope is not None else raw
            if statement is None:
                continue
            grants = [
                g
                for g in (held_form(r, scope) for r in statement.resources)
                if g is not None
            ]
            for action in self._actions(statement.actions):
                universes = self._universes(action)
                for grant in grants:
                    reason = self._refusal(action, grant, universes)
                    if reason is not None:
                        return Uncovered(index, raw.sid, action, shown(grant), reason)
        return None

    def _refusal(self, action: str, grant: str, universes: list[Tokens]) -> str | None:
        for index, side in enumerate(self.sides):
            allowed = self._allowed(index, action)
            if not all(covered(grant, allowed, u) for u in universes):
                return side.lacks
        for index in range(len(self.sides)):
            for pattern, policy_id in self._denied(index, action):
                if any(overlaps(grant, (pattern,), u) for u in universes):
                    return (
                        f"a Deny of policy {policy_id} refuses {shown(pattern)}"
                        if policy_id
                        else f"a Deny refuses {shown(pattern)}"
                    )
        return None

    # -- what may be granted -------------------------------------------------------

    def grantable(self, scope: str) -> list[GrantableCatalog]:
        """For each catalog, the actions held at ``scope`` and the resource
        patterns they are held on there, written ``${scope}:...``, minus what a
        Deny takes back (whole patterns dropped, partial ones in ``excluded``)."""
        scope_fields(scope)
        found: list[GrantableCatalog] = []
        for catalog in self.catalogs.all():
            actions: list[GrantableAction] = []
            for spec in catalog.actions:
                action = catalog.qualified(spec.name)
                held = self._held_at(action, scope)
                if held:
                    actions.append(held)
            if actions:
                found.append(GrantableCatalog(catalog.service, tuple(actions)))
        return found

    def _held_at(self, action: str, scope: str) -> GrantableAction | None:
        if not self.sides:
            return None
        universes = self._universes(action)
        kept: list[str] = []
        excluded: list[str] = []
        for pattern in self._allowed(0, action):
            restricted = _restrict(pattern, scope)
            if restricted is None or restricted in kept:
                continue
            if not all(
                covered(restricted, self._allowed(i, action), u)
                for i in range(1, len(self.sides))
                for u in universes
            ):
                continue
            denies = [
                d
                for i in range(len(self.sides))
                for d, _policy in self._denied(i, action)
            ]
            if denies and all(covered(restricted, denies, u) for u in universes):
                continue
            kept.append(restricted)
            excluded += [
                d
                for d in denies
                if any(overlaps(restricted, (d,), u) for u in universes)
            ]
        if not kept:
            return None
        prefix = f"{scope}:"
        return GrantableAction(
            action,
            tuple(shown("${scope}:" + k.removeprefix(prefix)) for k in kept),
            tuple(sorted({shown(d) for d in excluded})),
        )


def _restrict(pattern: str, scope: str) -> str | None:
    """A pattern, in held form, of the names under ``scope`` that ``pattern``
    matches (``<scope>:<rest>``), or None. It may say less than ``pattern``
    reaches there, never more."""
    prefix = f"{scope}:"
    if pattern.startswith(prefix):
        return pattern
    if covered(f"{prefix}*", (pattern,)):
        return f"{prefix}*"
    fields = pattern.split(":", 3)
    if len(fields) == 4 and fields[0] == "abi":
        org, workspace = scope_fields(scope)
        rest = fields[3]
        if (
            matches(fields[1], org)
            and matches(fields[2], workspace)
            and covered(prefix + rest, (pattern,))
        ):
            return prefix + rest
    return None
