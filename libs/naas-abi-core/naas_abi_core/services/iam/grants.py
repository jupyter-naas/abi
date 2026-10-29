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
Only names of the action's resource types count (``universe``: ``abi:``, steps
of the registered container types, then ``<service>:<type>/<id>``), so
``${scope}/triple_store:*`` is no wider than ``${scope}/triple_store:graph/*``
for an action on graphs only.

Scopes (``held_forms``): ``${scope}`` is a container, the platform (where
``${scope}/`` reads ``abi:``), or below a container, where it stands for each
container under it: a pattern then has several forms, fewer for what a caller
holds (``over=False``: never more than the evaluator lets through), more for
what a grant gives or a Deny refuses (``over=True``: never less). A grant one held pattern embeds is covered at
once (``_embeds``); otherwise containment is decided on the product of the
patterns' automata; when one search takes more than ``STATE_BUDGET`` states, or
the searches of one check more than ``CALL_BUDGET`` together, it is not proven,
and the grant is refused.

Variables keep their form: ``${principal.id}`` and ``${user.id}`` in a grant
are covered by the giver holding the same variable at that place (or a ``*``),
never by a literal id or a ``?``: a variable stands for a whole id. The module
variables likewise.

Sub-policies ("Sub-policies"): a sub-policy's grant is its own within its
chain's, so the searches take each policy of the chain as one more automaton a
name must be accepted by (``first_uncovered(parents=)``). What a giver holds
through a sub-policy is narrowed without a search (``within_chain``).
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal
from urllib.parse import unquote

from naas_abi_core.services.iam.broker import BUS_ACTIONS, TOPIC_PREFIX
from naas_abi_core.services.iam.catalog import CatalogRegistry
from naas_abi_core.services.iam.IAMPorts import GrantableAction, GrantableCatalog
from naas_abi_core.services.iam.names import (
    PLATFORM,
    container_of_scope,
    encode_segment,
    is_below,
    literal_prefix,
    matches,
    split_action,
    substitute,
    validate_scope,
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
_MARK_CHARS = frozenset(MARKS.values())
# About 1 s of searching each: the built-in roles take a few hundred states.
STATE_BUDGET = 20_000  # one search
CALL_BUDGET = 20_000  # every search of one check, together

# Pattern tokens: a literal character, "?" (one), "*" (a run), and, in the
# names of a type only, one character or a run of characters that are not ":".
_LIT, _ONE, _RUN, _FIELD_ONE, _FIELD_RUN = range(5)
Token = tuple[int, str]
Tokens = tuple[Token, ...]


class Unproven(Exception):
    """Containment took more than ``STATE_BUDGET`` states to decide."""


class Exhausted(Exception):
    """The searches of one check took more than ``CALL_BUDGET`` states.

    Unlike ``Unproven``, it says nothing of the patterns searched, so no result
    is cached for it."""


# The states the current check may still spend (``budget()``), None outside one.
_LEFT: ContextVar[list[int] | None] = ContextVar("grants_budget", default=None)


@contextmanager
def budget() -> Iterator[None]:
    """Bound the searches of one check, together, to ``CALL_BUDGET`` states; a
    search past it raises ``Exhausted``. Within a check, it is that check's."""
    if _LEFT.get() is not None:
        yield
        return
    token = _LEFT.set([CALL_BUDGET])
    try:
        yield
    finally:
        _LEFT.reset(token)


def _spend() -> None:
    left = _LEFT.get()
    if left is not None:
        left[0] -= 1
        if left[0] < 0:
            raise Exhausted


_STEP_START = re.compile(r"[a-z][a-z0-9_]*:")
# The platform's own policies, groups and attachments: never reached through an
# attachment at the platform (``names.platform_own``).
_IAM_OWNED = frozenset({("iam", "policy"), ("iam", "group"), ("iam", "attachment")})


def scope_forms(pattern: str, scope: str | None, *, over: bool = False) -> list[str]:
    """``pattern`` with ``${scope}`` filled for an attachment at ``scope``: one
    form at a container; at the platform, ``${scope}/`` as ``abi:`` (and
    ``${scope}`` alone matching nothing); below a container C, for ``${scope}/R``,
    ``C/R`` and, when R starts with a step, ``C/*/R`` (with ``over``, any other R
    as ``C/*R``), and for ``${scope}`` alone C and, with ``over``, ``C/*``. None of
    them when it names ``${scope}`` and there is no scope."""
    if "${scope}" not in pattern:
        return [pattern]
    if scope is None:
        return []
    if scope == PLATFORM:
        filled = pattern.replace("${scope}/", "abi:")
        # ``${scope}`` alone names the platform itself: nothing.
        return [] if "${scope}" in filled else [filled]
    if not is_below(scope):
        return [pattern.replace("${scope}", scope)]
    container = container_of_scope(scope)
    base = "abi:" if container == PLATFORM else container + "/"
    rest = pattern.removeprefix("${scope}").replace("${scope}", container)
    if not pattern.startswith("${scope}"):
        return [pattern.replace("${scope}", container)]
    if not rest:
        if container == PLATFORM:
            return ["abi:*"] if over else []
        return [container, base + "*"] if over else [container]
    if not rest.startswith("/"):
        return [base + "*" + rest] if over else [container + rest]
    tail = rest[1:]
    if tail.startswith("*"):
        return [base + tail]
    if _STEP_START.match(tail):
        return [base + tail, base + "*/" + tail]
    return [base + "*" + tail] if over else [base + tail]


def held_forms(
    pattern: str,
    scope: str | None,
    *,
    canonical: bool = True,
    variables: bool = False,
    over: bool = False,
) -> list[str]:
    """``pattern`` with ``${scope}`` filled (``scope_forms``) and the other
    variables as marks, a bus topic in its canonical spelling
    (``canonical_topic``, ``variables`` passed on) unless not ``canonical``."""
    found: list[str] = []
    for form in scope_forms(pattern, scope, over=over):
        if canonical:
            form = canonical_topic(form, variables=variables)
        for name, mark in MARKS.items():
            form = form.replace("${" + name + "}", mark)
        if form not in found:
            found.append(form)
    return found


def held_form(
    pattern: str,
    scope: str | None,
    *,
    canonical: bool = True,
    variables: bool = False,
) -> str | None:
    """The one held form of ``pattern`` at a container, the platform or with no
    scope; None when it matches nothing there."""
    forms = held_forms(pattern, scope, canonical=canonical, variables=variables)
    return forms[0] if forms else None


_VARIABLE = re.compile(r"(\$\{[^}]*\})")


def canonical_topic(pattern: str, *, variables: bool = False) -> str:
    """A bus topic (``abi:bus:topic/<t>``) as the broker grants it: each
    run of it decoded, then encoded as a canonical name is (``pay%6Dents`` is
    ``payments``, ``pay:ments`` is ``pay%3Aments``).

    A topic pattern (a ``*`` or ``?``) is kept as written: the broker grants
    none, and the evaluator compares it with canonical names as it stands. With
    ``variables``, the runs around a variable are canonical too, the variable
    kept (what a grant may name; the broker grants no topic naming one,
    ``broker.topic_problem``); without, a topic naming one is kept as written
    (what a caller holds: it reaches nothing more than so)."""
    if not pattern.startswith(TOPIC_PREFIX):
        return pattern
    topic = pattern[len(TOPIC_PREFIX) :]
    if any(c in topic for c in "*?") or ("${" in topic and not variables):
        return pattern
    return TOPIC_PREFIX + "".join(
        run if _VARIABLE.fullmatch(run) else encode_segment(unquote(run))
        for run in _VARIABLE.split(topic)
        if run
    )


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


@dataclass(frozen=True)
class Universe:
    """The names a pattern is compared within, as an automaton: a glob's tokens
    (``EVERYTHING``, the bus's topics), or the names of one resource type
    (``universe``): ``abi:``, steps ``<service>:<type>/<id>/`` of the container
    types, then ``<service>:<type>/`` and an id with no raw ``:``. For a
    container type that names its parents, its own step only right after one of
    them (``-``: right after ``abi:``)."""

    tokens: Tokens = ()
    final: str = ""  # "<service>:<type>/" of the names of one type
    containers: tuple[str, ...] = ()  # "<service>:<type>/" of each container type
    # The containers (indexes in ``containers``, -1 for the platform) the final
    # step may follow; None for any.
    after: frozenset[int] | None = None

    def start(self) -> frozenset[object]:
        if self.final:
            return frozenset({("p", 0)})
        return _close(self.tokens, (0,))

    def literals(self) -> set[str]:
        if self.final:
            return set("abi:/" + self.final + "".join(self.containers))
        return {c for kind, c in self.tokens if kind == _LIT}

    def step(self, states: frozenset[object], char: str) -> frozenset[object]:
        if not self.final:
            return _step(self.tokens, states, char)  # type: ignore[arg-type]
        after: set[object] = set()
        literals = (self.final, *self.containers)
        for state in states:
            kind = state[0]  # type: ignore[index]
            if kind == "p":
                index = state[1]  # type: ignore[index]
                if "abi:"[index] == char:
                    after |= {("p", index + 1)} if index < 3 else self._steps(-1)
            elif kind == "l":
                which: int = state[1]  # type: ignore[index]
                index = state[2]  # type: ignore[index]
                literal = literals[which]
                if literal[index] != char:
                    continue
                if index + 1 < len(literal):
                    after.add(("l", which, index + 1))
                else:
                    after.add(("id0",) if which == 0 else ("seg0", which - 1))
            elif kind in ("id0", "id"):
                if char != ":":
                    after.add(("id",))
            elif kind in ("seg0", "seg"):
                container: int = state[1]  # type: ignore[index]
                if char == "/" and kind == "seg":
                    after |= self._steps(container)
                elif char not in ":/":
                    after.add(("seg", container))
        return frozenset(after)

    def _steps(self, previous: int) -> set[object]:
        """The steps that may follow container ``previous`` (-1: the platform)."""
        first = 0 if self.after is None or previous in self.after else 1
        return {("l", which, 0) for which in range(first, len(self.containers) + 1)}

    def accepts(self, states: frozenset[object]) -> bool:
        if not self.final:
            return _accepts(self.tokens, states)  # type: ignore[arg-type]
        return ("id",) in states


@lru_cache(maxsize=1024)
def universe(
    service: str,
    resource_type: str,
    containers: frozenset[tuple[str, str]] = frozenset(),
    parents: tuple[str, ...] = (),
) -> Universe:
    """The canonical names of a resource type: at the platform or in containers
    of ``containers`` (``(service, type)``, the registered container types); for
    a container type that names ``parents``, only in those."""
    ordered = tuple(sorted(f"{s}:{t}/" for s, t in containers))
    after = (
        frozenset(
            -1 if parent == "-" else ordered.index(f"{parent}/")
            for parent in parents
            if parent == "-" or f"{parent}/" in ordered
        )
        if parents
        else None
    )
    return Universe(
        final=f"{service}:{resource_type}/", containers=ordered, after=after
    )


EVERYTHING = Universe(tokens=((_RUN, ""),))

# Actions the broker grants with no catalog to expand a wildcard against: the
# bus's, on its topics, which are never at a scope (``abi:bus:topic/<t>``).
# A wildcard reaching them is checked for them, like their names. Any run after
# the prefix is a topic, a raw ":" included: every topic resource needs cover.
UNCATALOGUED: dict[str, tuple[tuple[str, ...], Universe]] = {
    "bus": (BUS_ACTIONS, Universe(tokens=(*_glob(TOPIC_PREFIX), (_RUN, "")))),
}


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
            if char not in _MARK_CHARS:  # a variable is a whole id, not one character
                after.append(state + 1)
        elif kind == _RUN:
            after.append(state)
        elif char != ":":
            after.append(state + 1 if kind == _FIELD_ONE else state)
    return _close(tokens, after)


def _accepts(tokens: Tokens, states: frozenset[int]) -> bool:
    return len(tokens) in states


def _alphabet(literals: set[str], *token_lists: Tokens) -> list[str]:
    """Every literal character, ``:`` and ``/``, and one character none of them
    is: the patterns treat every other character alike."""
    literals = set(literals) | {
        c for tokens in token_lists for kind, c in tokens if kind == _LIT
    }
    literals |= {":", "/"}
    other = next(chr(c) for c in range(0x10, 0x110000) if chr(c) not in literals)
    return sorted(literals) + [other]


_prefix = lru_cache(maxsize=16384)(literal_prefix)


def _compatible(a: str, b: str) -> bool:
    """Whether some name could match both: one literal prefix extends the other."""
    pa, pb = _prefix(a), _prefix(b)
    return pa.startswith(pb) or pb.startswith(pa)


# A sub-policy's chain, for one action: per policy, the patterns it allows it on.
Bounds = tuple[tuple[str, ...], ...]


def _search(
    grant: str,
    others: tuple[str, ...],
    within: Universe,
    goal: Literal["uncovered", "overlap"],
    bounds: Bounds = (),
) -> bool:
    """Whether some name of ``within`` that one pattern of each level of
    ``bounds`` matches too matches ``grant`` and none of ``others``
    (``uncovered``), or ``grant`` and one of ``others`` (``overlap``)."""
    g, u = _glob(grant), within
    hs = [_glob(other) for other in others]
    bs = [[_glob(pattern) for pattern in level] for level in bounds]
    alphabet = _alphabet(u.literals(), g, *hs, *(b for level in bs for b in level))
    State = tuple[
        frozenset[int],
        frozenset[object],
        tuple[frozenset[int], ...],
        tuple[tuple[frozenset[int], ...], ...],
    ]
    start: State = (
        _close(g, (0,)),
        u.start(),
        tuple(_close(h, (0,)) for h in hs),
        tuple(tuple(_close(b, (0,)) for b in level) for level in bs),
    )
    seen = {start}
    queue = deque([start])
    while queue:
        gs, us, hstates, bstates = queue.popleft()
        if (
            _accepts(g, gs)
            and u.accepts(us)
            and all(
                any(_accepts(b, s) for b, s in zip(level, states))
                for level, states in zip(bs, bstates)
            )
        ):
            held = any(_accepts(h, s) for h, s in zip(hs, hstates))
            if (goal == "uncovered" and not held) or (goal == "overlap" and held):
                return True
        for char in alphabet:
            nxt: State = (
                _step(g, gs, char),
                u.step(us, char),
                tuple(_step(h, s, char) for h, s in zip(hs, hstates)),
                tuple(
                    tuple(_step(b, s, char) for b, s in zip(level, states))
                    for level, states in zip(bs, bstates)
                ),
            )
            if (
                not nxt[0]
                or not nxt[1]
                or (goal == "overlap" and not any(nxt[2]))
                or not all(any(states) for states in nxt[3])
            ):
                continue
            if nxt not in seen:
                if len(seen) >= STATE_BUDGET:
                    raise Unproven(grant)
                _spend()
                seen.add(nxt)
                queue.append(nxt)
    return False


@lru_cache(maxsize=16384)
def _embeds(grant: str, held: str) -> bool:
    """Whether ``held`` matches every name ``grant`` does, shown without a
    search: each ``*`` of ``grant`` falls within a ``*`` of ``held``, each
    ``?`` within a ``?`` or a ``*``, each character within the same one or a
    wildcard (a variable's mark within the same mark or a ``*``). Sufficient,
    not necessary: what it does not show, the search decides."""
    g, h = _glob(grant), _glob(held)
    # within[j]: whether grant[i:] embeds in held[j:], for i from the end.
    within = [all(kind == _RUN for kind, _ in h[j:]) for j in range(len(h) + 1)]
    for i in range(len(g) - 1, -1, -1):
        kind, char = g[i]
        row = [False] * (len(h) + 1)
        for j in range(len(h) - 1, -1, -1):
            held_kind, held_char = h[j]
            if held_kind == _RUN:
                row[j] = row[j + 1] or within[j]
            elif held_kind == _ONE:
                row[j] = (
                    kind == _ONE or (kind == _LIT and char not in _MARK_CHARS)
                ) and within[j + 1]
            else:
                row[j] = kind == _LIT and char == held_char and within[j + 1]
        within = row
    return within[0]


def _bounds_for(grant: str, bounds: Bounds) -> Bounds | None:
    """``bounds`` with the patterns no name of ``grant`` can match left out;
    None when a level is left with none: ``grant`` reaches nothing within them."""
    kept = tuple(tuple(b for b in level if _compatible(grant, b)) for level in bounds)
    if any(not level for level in kept):
        return None
    # A level one of whose patterns embeds the grant bounds nothing more.
    return tuple(level for level in kept if not any(_embeds(grant, b) for b in level))


@lru_cache(maxsize=16384)
def _covered(
    grant: str, held: tuple[str, ...], within: Universe, bounds: Bounds = ()
) -> bool:
    if grant in held or "*" in held:
        return True
    held = tuple(h for h in held if _compatible(grant, h))
    if any(_embeds(grant, h) for h in held):
        return True
    narrowed = _bounds_for(grant, bounds)
    if narrowed is None:
        return True
    try:
        return not _search(grant, held, within, "uncovered", narrowed)
    except Unproven:
        return False


@lru_cache(maxsize=16384)
def _overlaps(
    grant: str, others: tuple[str, ...], within: Universe, bounds: Bounds = ()
) -> bool:
    others = tuple(o for o in others if _compatible(grant, o))
    if not others:
        return False
    narrowed = _bounds_for(grant, bounds)
    if narrowed is None:
        return False
    try:
        return _search(grant, others, within, "overlap", narrowed)
    except Unproven:
        return True


def covered(
    grant: str,
    held: Iterable[str],
    within: Universe = EVERYTHING,
    bounds: Bounds = (),
) -> bool:
    """Whether every name of ``within`` that ``grant`` matches, and one pattern
    of each level of ``bounds`` too, is matched by one of ``held`` (so True when
    it matches none). False when that is not proven; ``Exhausted`` past the
    budget of the check (``budget()``)."""
    return _covered(grant, tuple(sorted(set(held))), within, bounds)


def overlaps(
    grant: str,
    others: Iterable[str],
    within: Universe = EVERYTHING,
    bounds: Bounds = (),
) -> bool:
    """Whether some name of ``within`` (within ``bounds``) matches ``grant`` and
    one of ``others``. True when that is not disproven; ``Exhausted`` past the
    budget of the check."""
    return _overlaps(grant, tuple(sorted(set(others))), within, bounds)


def _meet(ours: Iterable[str], theirs: Iterable[str]) -> tuple[str, ...]:
    """Patterns each within one of ``ours`` and one of ``theirs``, shown without
    a search: one of either side that a pattern of the other embeds. It may say
    less than the intersection, never more."""
    ours, theirs = tuple(ours), tuple(theirs)
    found = dict.fromkeys(p for p in ours if any(_embeds(p, t) for t in theirs))
    found.update(dict.fromkeys(t for t in theirs if any(_embeds(t, p) for p in ours)))
    return tuple(found)


def within_chain(
    statement: Statement,
    chain: Sequence[Sequence[Statement]],
    scope: str | None,
) -> list[Statement]:
    """An Allow of a sub-policy, attached at ``scope``, as Allows with no chain:
    each pair of action and resource patterns within its own and within an
    Allow of every policy of ``chain`` (nearest first), shown without a search
    (``_meet``, on held forms, ``${scope}`` filled). It may say less than the
    sub-policy reaches, never more: what a giver holds through it, and what the
    broker grants for it."""
    own = [
        f for r in statement.resources for f in held_forms(r, scope, canonical=False)
    ]
    parts = [(statement.actions, tuple(own))]
    for level in chain:
        narrowed: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
        for bound in level:
            if bound.effect != "Allow":
                continue
            theirs = [
                f
                for r in bound.resources
                for f in held_forms(r, scope, canonical=False)
            ]
            for actions, resources in parts:
                met_actions = _meet(actions, bound.actions)
                met_resources = _meet(resources, theirs)
                if met_actions and met_resources:
                    narrowed.append((met_actions, met_resources))
        parts = narrowed
    return [
        Statement("Allow", actions, tuple(shown(r) for r in resources), statement.sid)
        for actions, resources in parts
    ]


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
    # Held for actions on a container type only: below a container, ``${scope}``
    # alone reaches each container under it, nothing else of what it holds.
    containers_only: tuple[str, ...] = ()
    # Reached through an attachment at the platform: never the platform's own
    # policies, groups and attachments (``names.platform_own``).
    not_platform_own: tuple[str, ...] = ()


def held_statement(
    statement: Statement,
    scope: str | None,
    *,
    principal_id: str,
    user_id: str | None,
    policy_id: str | None = None,
) -> HeldStatement:
    """A statement of the giver, attached at ``scope``, in held form.

    With no user (``user_id`` None), a pattern naming ``${user.id}`` matches
    nothing, as the evaluator reads it, so it is left out. A Deny also refuses
    what its variables name for the giver: each pattern is kept bound to the
    giver's ids too, so it overlaps a grant of the giver's own literal id; a
    bus topic in its spelling as written as well as its canonical one, and its
    sub-topics (``<t>.*``) with it, as the broker grants a topic's."""
    values: dict[str, str | None] = {
        "scope": scope,
        "principal.id": encode_segment(principal_id),
        "user.id": encode_segment(user_id) if user_id is not None else None,
    }
    deny = statement.effect == "Deny"
    resources: dict[str, None] = {}
    containers_only: dict[str, None] = {}
    shielded: dict[str, None] = {}
    for pattern in statement.resources:
        if user_id is None and "${user.id}" in pattern:
            continue
        forms = held_forms(pattern, scope, over=deny)
        if not deny and pattern == "${scope}" and is_below(scope):
            # ${scope} alone, below a container: each container under it too.
            containers_only.update(
                dict.fromkeys(
                    f for f in held_forms(pattern, scope, over=True) if f not in forms
                )
            )
        if not deny and scope == PLATFORM and "${scope}" in pattern:
            shielded.update(dict.fromkeys(forms))
            continue
        resources.update(dict.fromkeys(forms))
        if deny:
            spellings: list[str | None] = [
                *held_forms(pattern, scope, canonical=False, over=True),
                *held_forms(pattern, scope, variables=True, over=True),
            ]
            for value in _scope_values(scope):
                bound = substitute(pattern, {**values, "scope": value})
                spellings += [bound, canonical_topic(bound) if bound else None]
            for spelling in spellings:
                if not spelling:
                    continue
                resources[spelling] = None
                topic = spelling.removeprefix(TOPIC_PREFIX)
                if topic != spelling and not any(c in topic for c in "*?"):
                    # A topic's stream holds its sub-topics (``<t>.>``).
                    resources[f"{spelling}.*"] = None
    return HeldStatement(
        statement.effect,
        statement.actions,
        tuple(resources),
        policy_id,
        tuple(containers_only),
        tuple(shielded),
    )


def _scope_values(scope: str | None) -> list[str | None]:
    """What ``${scope}`` is filled with to bind a Deny to the giver's ids: the
    container (below one, the container and a run of any below it)."""
    if not is_below(scope):
        return [scope]
    container = container_of_scope(scope or "")
    return [container, ("abi:" if container == PLATFORM else container + "/") + "*"]


@dataclass(frozen=True)
class Side:
    """One side that decides for the giver: the user, an actor acting for them,
    or the narrowing of their credential (Allow statements only)."""

    statements: tuple[HeldStatement, ...]
    lacks: str  # how a refusal says this side does not hold it
    active: bool = True


TOO_COSTLY = "proving you hold it takes too long: name fewer, or simpler, resources"


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
            on_containers = self._on_containers(action)
            platform_own = self._on_platform_own(action)
            self._allows[key] = (
                tuple(
                    sorted(
                        {
                            r
                            for s in side.statements
                            if s.effect == "Allow"
                            and any(matches(p, action) for p in s.actions)
                            for r in (
                                *s.resources,
                                *(s.containers_only if on_containers else ()),
                                *(s.not_platform_own if not platform_own else ()),
                            )
                        }
                    )
                )
                if side.active
                else ()
            )
        return self._allows[key]

    def _types(self, action: str) -> list[tuple[str, str]]:
        try:
            service, name = split_action(action)
        except ValueError:
            return []
        catalog = self.catalogs.get(service)
        spec = catalog.action(name) if catalog is not None else None
        return [(service, t) for t in spec.resource_types] if spec is not None else []

    def _on_containers(self, action: str) -> bool:
        """Whether ``action`` is on a container type (unknown: no)."""
        return any(self.catalogs.is_container(s, t) for s, t in self._types(action))

    def _on_platform_own(self, action: str) -> bool:
        """Whether ``action`` may name the platform's own policies, groups or
        attachments (unknown: yes)."""
        types = self._types(action)
        return not types or any(t in _IAM_OWNED for t in types)

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

    def _universes(self, action: str) -> list[Universe]:
        try:
            service, name = split_action(action)
        except ValueError:
            return [EVERYTHING]
        catalog = self.catalogs.get(service)
        if catalog is None and service in UNCATALOGUED:
            return [UNCATALOGUED[service][1]]
        spec = catalog.action(name) if catalog is not None else None
        if spec is None or not spec.resource_types:
            return [EVERYTHING]
        containers = self.catalogs.container_types()
        return [
            universe(service, t, containers, declared.parents if declared else ())
            for t in spec.resource_types
            for declared in [catalog.resource_type(t) if catalog is not None else None]
        ]

    def _actions(self, patterns: Iterable[str]) -> list[str]:
        """Each action a statement's patterns match: the registered ones a
        wildcard matches, the bus's it matches (``UNCATALOGUED``), and a
        concrete name as it is. A wildcard of the actions of one named service
        that has no catalog is taken as written, so only whoever holds it so
        may give it."""
        found: dict[str, None] = {}
        for pattern in patterns:
            if not ("*" in pattern or "?" in pattern):
                found[pattern] = None
                continue
            found.update(dict.fromkeys(self.catalogs.matching(pattern)))
            for service, (names, _within) in UNCATALOGUED.items():
                if self.catalogs.get(service) is None:
                    found.update(
                        dict.fromkeys(
                            f"{service}:{name}"
                            for name in names
                            if matches(pattern, f"{service}:{name}")
                        )
                    )
            service, colon, _name = pattern.partition(":")
            if (
                colon
                and not ("*" in service or "?" in service)
                and service not in UNCATALOGUED
                and self.catalogs.get(service) is None
            ):
                found[pattern] = None
        return list(found)

    # -- the rule ----------------------------------------------------------------

    def first_uncovered(
        self,
        statements: Sequence[Statement],
        scope: str | None,
        *,
        parents: Sequence[Sequence[Statement]] = (),
    ) -> Uncovered | None:
        """The first (statement, action, resource) of the grant of
        ``statements`` at ``scope`` (None: unscoped) the giver does not hold.
        For a sub-policy, ``parents`` is its chain, each policy's statements,
        nearest first: only what an Allow of each also names for the action is
        granted. Its searches share one budget (``CALL_BUDGET``): past it, what
        is left is not proven, and refused."""
        with budget():
            for index, raw in enumerate(statements):
                if raw.effect != "Allow":
                    continue  # a Deny only narrows: it needs no cover
                statement = within_scope(raw) if scope is not None else raw
                if statement is None:
                    continue
                grants = [
                    g
                    for r in statement.resources
                    for g in held_forms(r, scope, variables=True, over=True)
                ]
                for action in self._actions(statement.actions):
                    bounds = _chain_bounds(parents, action, scope)
                    if bounds is None:
                        continue  # the chain allows it nowhere: not granted
                    universes = self._universes(action)
                    for grant in grants:
                        try:
                            reason = self._refusal(action, grant, universes, bounds)
                        except Exhausted:
                            reason = TOO_COSTLY
                        if reason is not None:
                            return Uncovered(
                                index, raw.sid, action, shown(grant), reason
                            )
        return None

    def _refusal(
        self,
        action: str,
        grant: str,
        universes: list[Universe],
        bounds: Bounds = (),
    ) -> str | None:
        for index, side in enumerate(self.sides):
            allowed = self._allowed(index, action)
            if not all(covered(grant, allowed, u, bounds) for u in universes):
                return side.lacks
        for index in range(len(self.sides)):
            for pattern, policy_id in self._denied(index, action):
                if any(overlaps(grant, (pattern,), u, bounds) for u in universes):
                    return (
                        f"a Deny of policy {policy_id} refuses {shown(pattern)}"
                        if policy_id
                        else f"a Deny refuses {shown(pattern)}"
                    )
        return None

    # -- what may be granted -------------------------------------------------------

    def grantable(
        self, scope: str, *, parents: Sequence[Sequence[Statement]] = ()
    ) -> list[GrantableCatalog]:
        """For each catalog, the actions held at ``scope`` and the resource
        patterns they are held on there, written ``${scope}/...`` (or
        ``${scope}``, the container itself), minus what a Deny takes back (whole
        patterns dropped, partial ones in ``excluded``). Below a container, at it.
        With ``parents`` (a sub-policy's chain, each policy's statements, nearest
        first), only what an Allow of each also names (``_within_parents``)."""
        scope = container_of_scope(validate_scope(scope))
        found: list[GrantableCatalog] = []
        with budget():
            for catalog in self.catalogs.all():
                actions: list[GrantableAction] = []
                exhausted = False
                for spec in catalog.actions:
                    try:
                        held = self._held_at(
                            catalog.qualified(spec.name), scope, parents
                        )
                    except Exhausted:
                        exhausted = True
                        break
                    if held:
                        actions.append(held)
                if actions:
                    found.append(GrantableCatalog(catalog.service, tuple(actions)))
                if exhausted:
                    break
        return found

    def _held_at(
        self,
        action: str,
        scope: str,
        parents: Sequence[Sequence[Statement]] = (),
    ) -> GrantableAction | None:
        if not self.sides:
            return None
        universes = self._universes(action)
        denies = [
            d for i in range(len(self.sides)) for d, _policy in self._denied(i, action)
        ]
        kept: list[str] = []
        excluded: set[str] = set()
        on_containers = self._on_containers(action)
        for restricted in (
            r for pattern in self._allowed(0, action) for r in _restrict(pattern, scope)
        ):
            if restricted in kept:
                continue
            if (restricted == scope or on_containers) and not any(
                overlaps(restricted, ("*",), u) for u in universes
            ):
                # It names no name of the action's types there: the container
                # itself for an action on no container type, or a container type
                # that does not sit in this one (its ``parents``).
                continue
            if not all(
                covered(restricted, self._allowed(i, action), u)
                for i in range(1, len(self.sides))
                for u in universes
            ):
                continue
            if denies and all(covered(restricted, denies, u) for u in universes):
                continue
            kept.append(restricted)
        if parents:
            kept = _within_parents(kept, parents, action, scope)
        for restricted in kept:
            excluded.update(
                d
                for d in denies
                if any(overlaps(restricted, (d,), u) for u in universes)
            )
        if not kept:
            return None
        return GrantableAction(
            action,
            tuple(_written_at(k, scope) for k in kept),
            tuple(
                sorted(
                    {
                        written
                        for d in excluded
                        for written in (
                            [_written_at(r, scope) for r in _restrict(d, scope)]
                            or [shown(d)]
                        )
                    }
                )
            ),
        )


def _chain_bounds(
    parents: Sequence[Sequence[Statement]], action: str, scope: str | None
) -> Bounds | None:
    """Per policy of a chain, the patterns, in held form at ``scope``, its
    Allows name ``action`` on; None when one names it nowhere. ``action`` may
    be a pattern (``Holdings._actions`` keeps a wildcard of a service with no
    catalog as written): then every Allow whose actions may meet it bounds it,
    so the bounds may say more than the chain grants, never less."""
    bounds: list[tuple[str, ...]] = []
    for level in parents:
        patterns = tuple(
            dict.fromkeys(
                held
                for statement in level
                if statement.effect == "Allow"
                and any(_actions_meet(p, action) for p in statement.actions)
                for r in statement.resources
                for held in held_forms(r, scope, variables=True, over=True)
            )
        )
        if not patterns:
            return None
        bounds.append(patterns)
    return tuple(bounds)


def _within_parents(
    kept: Sequence[str],
    parents: Sequence[Sequence[Statement]],
    action: str,
    scope: str,
) -> list[str]:
    """``kept`` (held forms under ``scope``) within a sub-policy's chain: per
    policy of it, the patterns of either side the other embeds (``_meet``), the
    chain's restricted to ``scope`` first. It may say less than the chain lets
    through, never more; a pattern naming a variable is left out, as no
    container fills it."""
    bounds = _chain_bounds(parents, action, scope)
    if bounds is None:
        return []
    found = list(kept)
    for level in bounds:
        theirs = [r for pattern in level for r in _restrict(pattern, scope)]
        found = [
            p for p in _meet(found, theirs) if not any(m in p for m in _MARK_CHARS)
        ]
        if not found:
            break
    return found


def _actions_meet(pattern: str, action: str) -> bool:
    """Whether some action matches both: ``action`` itself when it is concrete;
    when it is a pattern, true unless shown otherwise."""
    if not ("*" in action or "?" in action):
        return matches(pattern, action)
    try:
        return overlaps(action, (pattern,))
    except Exhausted:
        return True


def _under(scope: str) -> str:
    """What a name under ``scope`` starts with: ``<container>/``, ``abi:`` at
    the platform."""
    return "abi:" if scope == PLATFORM else scope + "/"


def _written_at(pattern: str, scope: str) -> str:
    """A pattern under ``scope``, in held form, as a policy writes it there."""
    if pattern == scope:
        return "${scope}"
    return shown("${scope}/" + pattern.removeprefix(_under(scope)))


def _restrict(pattern: str, scope: str) -> list[str]:
    """Patterns, in held form, of the names under ``scope`` (and the container
    itself) that ``pattern`` matches. They may say less than ``pattern`` reaches
    there, never more. Shown without a search: what ``pattern`` is left with
    after ``<scope>/`` (``_after``) embeds each one, so a list costs no budget."""
    prefix = _under(scope)
    if pattern.startswith(prefix) or pattern == scope:
        return [pattern]
    found: list[str] = []
    if scope != PLATFORM and matches(pattern, scope):
        found.append(scope)
    rests = _after(pattern, prefix)
    if any(_embeds("*", rest) for rest in rests):
        return [*found, f"{prefix}*"]
    # A pattern written for every container (``abi:*/R``), the platform
    # (``abi:R``) or below a container above the scope (``<C>/*/R``) holds
    # ``<scope>/R`` when it covers it: each tail R of it, the shortest first,
    # one a kept one does not cover already.
    kept: list[str] = []
    for candidate in _candidates(pattern, prefix):
        tail = candidate[len(prefix) :]
        if any(_embeds(tail, rest) for rest in rests) and not any(
            _embeds(candidate, k) for k in kept
        ):
            kept.append(candidate)
    return [*found, *kept]


@lru_cache(maxsize=16384)
def _after(pattern: str, literal: str) -> frozenset[str]:
    """What ``pattern`` is left to match after ``literal``: the globs a rest
    matches exactly when ``literal`` and that rest match ``pattern``."""

    def close(states: Iterable[int]) -> set[int]:
        found: set[int] = set()
        stack = list(states)
        while stack:
            index = stack.pop()
            if index not in found:
                found.add(index)
                if index < len(pattern) and pattern[index] == "*":
                    stack.append(index + 1)
        return found

    states = close({0})
    for char in literal:
        moved: set[int] = set()
        for index in states:
            if index == len(pattern):
                continue
            current = pattern[index]
            if current == "*":
                moved.add(index)
            elif (current == "?" and char not in _MARK_CHARS) or current == char:
                moved.add(index + 1)
        states = close(moved)
    return frozenset(pattern[index:] for index in states)


def _candidates(pattern: str, prefix: str) -> list[str]:
    """``<prefix>R`` for each tail R of ``pattern`` after ``abi:`` or a ``/``,
    the shortest first, and ``<prefix>*R`` for ``abi:*R``."""
    tails = [
        pattern[index + 1 :]
        for index, char in enumerate(pattern)
        if char == "/" or (index == len("abi:") - 1 and pattern.startswith("abi:"))
    ]
    candidates = [prefix + tail for tail in sorted(set(tails), key=len) if tail]
    if pattern.startswith("abi:*"):
        candidates.append(prefix + "*" + pattern[len("abi:*") :])
    return candidates
