"""The evaluation algorithm (``AGENTS.md``, "Evaluation"), over a ``PolicySource``.

    decide(ctx, action, resource):
      1. the actor or the OBO user is not active        -> DENY (suspended)
      2. the resource is sealed to someone else         -> DENY (sealed)
      3. d_P = principal_decision(P); d_U likewise, ALLOW without a user
      4. either is EXPLICIT_DENY                        -> DENY (explicit)
      5. either is not ALLOW                            -> DENY (implicit)
      6. a bounded side, a module scope or a feature,
         outside the org's or the workspace's set       -> DENY (outside_set)
      7. the token narrows and no statement matches     -> DENY (implicit)
      8.                                                -> ALLOW

Nothing is allowed without a matching Allow; an explicit Deny wins over any
number of Allows; on behalf of a user, actor and user must both be allowed.
A user's Allow on a module scope or a feature counts only within the sets of
the resource's org and workspace (``sets.py``), unless the user holds
``builtin.platform_admin``. An Allow of a sub-policy counts only where each
policy of its chain allows too (``EffectiveStatement.bounds``); the chain's
Denies reach the principal as statements of their own ("Sub-policies").
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from naas_abi_core.engine.call_context import CallContext
from naas_abi_core.services.iam import sets
from naas_abi_core.services.iam.IAMPorts import (
    BoundingStatement,
    DecidingStatement,
    Decision,
    EffectiveStatement,
    Explanation,
    FilterResult,
    PolicySource,
    Reason,
    Seal,
    Subject,
)
from naas_abi_core.services.iam.names import (
    encode_segment,
    literal_prefix,
    matches,
    parse_resource_name,
    substitute,
)
from naas_abi_core.services.iam.policy import Statement

Outcome = Literal["allow", "explicit_deny", "implicit_deny"]


@dataclass(frozen=True)
class _Verdict:
    outcome: Outcome
    deciding: DecidingStatement | None = None


# The statement of each policy of a sub-policy's chain that allowed what its
# Allow did, nearest first.
_Bounding = tuple[BoundingStatement, ...]


class Evaluator:
    def __init__(self, source: PolicySource) -> None:
        self._source = source

    # -- public ----------------------------------------------------------------

    def explain(self, ctx: CallContext, action: str, resource: str) -> Explanation:
        actor = self._source.subject(ctx, "actor")
        user = self._source.subject(ctx, "user")
        return self._decide(ctx, actor, user, action, resource)

    def check(self, ctx: CallContext, action: str, resource: str) -> Decision:
        actor = self._source.subject(ctx, "actor")
        user = self._source.subject(ctx, "user")
        explanation = self._decide(ctx, actor, user, action, resource)
        if explanation.allowed:
            return Decision(True, True, explanation.reason)
        return Decision(
            False,
            self._visible(ctx, actor, user, resource),
            explanation.reason,
        )

    def filter(
        self, ctx: CallContext, action: str, resources: Iterable[str]
    ) -> FilterResult:
        actor = self._source.subject(ctx, "actor")
        user = self._source.subject(ctx, "user")
        allowed = [
            resource
            for resource in resources
            if self._decide(ctx, actor, user, action, resource).allowed
        ]
        return FilterResult(allowed, self._prefix_hints(ctx, actor, user, action))

    def allows_every(
        self, ctx: CallContext, action: str, service: str, resource_type: str
    ) -> bool:
        """Whether ``action`` is allowed on every resource of the type.

        Conservative: True only when nothing could deny any of them, that is
        no seal on the type, no narrowing token, no Deny naming the action on
        either side, and on each side an Allow whose pattern spans every org,
        workspace and id of the type.
        """
        actor = self._source.subject(ctx, "actor")
        user = self._source.subject(ctx, "user")
        if actor is None or actor.status != "active" or ctx.scope is not None:
            return False
        if ctx.on_behalf_of is not None and (user is None or user.status != "active"):
            return False
        if any(
            _may_name_type(seal.pattern, service, resource_type)
            for seal in self._source.seals()
        ):
            return False
        user_id = _user_id(ctx)
        sides = [actor] if user is None else [actor, user]
        if (
            any(side.bounded for side in sides)
            and self._source.has_sets()
            and sets.bounded(self._source.catalogs, service, resource_type)
        ):
            return False  # a set may leave some of them out
        return all(
            _spans_type(side, action, service, resource_type, user_id) for side in sides
        )

    # -- the algorithm -----------------------------------------------------------

    def _decide(
        self,
        ctx: CallContext,
        actor: Subject | None,
        user: Subject | None,
        action: str,
        resource: str,
    ) -> Explanation:
        def denied(reason: Reason, deciding: DecidingStatement | None = None):
            return Explanation(False, reason, action, resource, deciding)

        # 1. Suspended (or deleted, or nobody at all) acts for no one.
        if actor is None or actor.status != "active":
            return denied("suspended" if actor is not None else "implicit_deny")
        if ctx.on_behalf_of is not None and (user is None or user.status != "active"):
            return denied("suspended")
        # 2. Sealed resources open to their owner only, whatever the policies say.
        # Acting for a user never opens one, whoever the actor is: a call made for
        # a user (Nexus's, over the engine's facade) is the user's, not the owner's.
        seal = self._seal(resource)
        if seal is not None and (not _owns(seal, ctx) or ctx.on_behalf_of is not None):
            return denied("sealed")
        # 3. Each side on its own.
        user_id = _user_id(ctx)
        d_p = _principal_decision(actor, "actor", action, resource, user_id)
        d_u = (
            _principal_decision(user, "user", action, resource, user_id)
            if user is not None
            else _Verdict("allow")
        )
        # 4. An explicit Deny wins.
        for verdict in (d_p, d_u):
            if verdict.outcome == "explicit_deny":
                return denied("explicit_deny", verdict.deciding)
        # 5. Both must be allowed.
        for verdict in (d_p, d_u):
            if verdict.outcome != "allow":
                return denied("implicit_deny", verdict.deciding)
        # 6. The sets bound a user's Allow on module scopes and features.
        if (actor.bounded or (user is not None and user.bounded)) and not (
            self._within_sets(action, resource)
        ):
            return denied("outside_set")
        # 7. A narrowed token only narrows.
        if ctx.scope is not None:
            narrowing = _token_allow(ctx, action, resource, actor, user_id)
            if narrowing is None:
                return denied("implicit_deny")
        # 8.
        return Explanation(True, "allow", action, resource, d_p.deciding)

    def _within_sets(self, action: str, resource: str) -> bool:
        """Whether the sets of the resource's org and workspace have it (true
        for a resource they do not bound)."""
        if not self._source.has_sets():
            return True
        try:
            name = parse_resource_name(resource)
        except ValueError:
            return True
        if not sets.bounded(self._source.catalogs, name.service, name.type):
            return True
        org_set, workspace_set = self._source.scope_sets(name.org, name.workspace)
        return all(
            sets.allows(found, self._source.catalogs, action, name)
            for found in (org_set, workspace_set)
            if found is not None
        )

    def _visible(
        self,
        ctx: CallContext,
        actor: Subject | None,
        user: Subject | None,
        resource: str,
    ) -> bool:
        """Some action of the resource's service, on its type, is allowed (§5.4)."""
        try:
            name = parse_resource_name(resource)
        except ValueError:
            return False
        return any(
            self._decide(ctx, actor, user, action, resource).allowed
            for action in self._source.catalogs.actions_on(name.service, name.type)
        )

    def _seal(self, resource: str) -> Seal | None:
        return next(
            (s for s in self._source.seals() if matches(s.pattern, resource)), None
        )

    def _prefix_hints(
        self,
        ctx: CallContext,
        actor: Subject | None,
        user: Subject | None,
        action: str,
    ) -> list[str]:
        """Literal prefixes of the Allow patterns that could admit an item.

        Each side's set is a superset of what the call may list, so any one of
        them can be pushed down: the token's, else the user's, else the actor's,
        the first that is bounded.
        """
        if actor is None or actor.status != "active":
            return []
        if ctx.on_behalf_of is not None and (user is None or user.status != "active"):
            return []  # a suspended user lists nothing, through any actor
        user_id = _user_id(ctx)
        sides: list[list[str]] = []
        if ctx.scope is not None:
            sides.append(
                _hints(
                    (
                        EffectiveStatement(statement, "token", index)
                        for index, statement in enumerate(token_statements(ctx))
                    ),
                    action,
                    actor.principal_id,
                    user_id,
                )
            )
        if user is not None:
            sides.append(_hints(user.statements, action, user.principal_id, user_id))
        sides.append(_hints(actor.statements, action, actor.principal_id, user_id))
        if any(not hints for hints in sides):
            return []  # one side allows nothing: the call lists nothing
        for hints in sides:
            if "" not in hints:
                return hints
        return [""]


# -- helpers --------------------------------------------------------------------


def _owns(seal: Seal, ctx: CallContext) -> bool:
    """Whether the actor is the owner of ``seal``: the service account it names,
    or the module account of the module it names."""
    if seal.owner in _names(ctx):
        return True
    principal = ctx.principal
    if seal.module_id is None or principal.kind != "service_account":
        return False
    from naas_abi_core.services.iam.modules import parse_account

    account = parse_account(principal.name)
    return account is not None and account[1] == seal.module_id


def _names(ctx: CallContext) -> set[str]:
    principal = ctx.principal
    return {name for name in (principal.id, principal.name) if name}


def _user_id(ctx: CallContext) -> str | None:
    user = ctx.user
    return user.id if user is not None else None


def _values(
    effective: EffectiveStatement, principal_id: str, user_id: str | None
) -> dict[str, str | None]:
    return {
        "scope": effective.scope,
        "principal.id": encode_segment(principal_id),
        "user.id": encode_segment(user_id) if user_id is not None else None,
    }


def _matches(
    statement: Statement,
    values: dict[str, str | None],
    action: str,
    resource: str,
) -> bool:
    if not any(matches(pattern, action) for pattern in statement.actions):
        return False
    for pattern in statement.resources:
        expanded = substitute(pattern, values)
        if expanded is not None and matches(expanded, resource):
            return True
    return False


def _bounding(
    effective: EffectiveStatement,
    values: dict[str, str | None],
    action: str,
    resource: str,
) -> _Bounding | None:
    """For an Allow of a sub-policy, the statement of each policy of its chain
    that allows the same, its variables filled as the sub-policy's; None when
    one of them allows nothing of it. Empty for a policy with no parent."""
    found: list[BoundingStatement] = []
    for bound in effective.bounds:
        allowing = next(
            (
                (index, statement)
                for index, statement in bound.allows
                if _matches(statement, values, action, resource)
            ),
            None,
        )
        if allowing is None:
            return None
        found.append(BoundingStatement(bound.policy_id, allowing[0], allowing[1].sid))
    return tuple(found)


def _statement_matches(
    effective: EffectiveStatement,
    action: str,
    resource: str,
    principal_id: str,
    user_id: str | None,
) -> _Bounding | None:
    """None when ``effective`` does not match; else what bounded it (empty for a
    statement that no chain bounds)."""
    values = _values(effective, principal_id, user_id)
    if not _matches(effective.statement, values, action, resource):
        return None
    if effective.statement.effect == "Deny" or not effective.bounds:
        return ()
    return _bounding(effective, values, action, resource)


def _deciding(
    effective: EffectiveStatement,
    side: Literal["actor", "user", "token"],
    principal_id: str,
    bounded_by: _Bounding = (),
) -> DecidingStatement:
    return DecidingStatement(
        side=side,
        principal_id=principal_id,
        effect=effective.statement.effect,
        policy_id=effective.policy_id if side != "token" else None,
        statement_index=effective.statement_index,
        sid=effective.statement.sid,
        attachment_id=effective.attachment_id,
        scope=effective.scope,
        via_group=effective.via_group,
        bounded_by=bounded_by,
        through=effective.through,
    )


def _principal_decision(
    subject: Subject,
    side: Literal["actor", "user"],
    action: str,
    resource: str,
    user_id: str | None,
) -> _Verdict:
    allow: tuple[EffectiveStatement, _Bounding] | None = None
    for effective in subject.statements:
        bounded_by = _statement_matches(
            effective, action, resource, subject.principal_id, user_id
        )
        if bounded_by is None:
            continue
        if effective.statement.effect == "Deny":
            return _Verdict(
                "explicit_deny", _deciding(effective, side, subject.principal_id)
            )
        if allow is None:
            allow = (effective, bounded_by)
    if allow is not None:
        return _Verdict(
            "allow", _deciding(allow[0], side, subject.principal_id, allow[1])
        )
    return _Verdict("implicit_deny")


def _patterns(value: object) -> tuple[str, ...]:
    """A list or tuple of strings, else nothing.

    A bare string is refused: iterated, ``"svc:Get*"`` would become one pattern
    per character, ``"*"`` among them, and the token would stop narrowing.
    """
    if not isinstance(value, (list, tuple)):
        return ()
    if not all(isinstance(item, str) for item in value):
        return ()
    return tuple(value)


def token_statements(ctx: CallContext) -> list[Statement]:
    """The token's ``abi_scope``: Allow statements only; anything else matches nothing."""
    statements: list[Statement] = []
    for raw in ctx.scope or ():
        if not isinstance(raw, Mapping) or raw.get("effect") != "Allow":
            continue
        actions = _patterns(raw.get("actions"))
        resources = _patterns(raw.get("resources"))
        if not actions or not resources:
            continue
        statements.append(
            Statement(
                effect="Allow",
                actions=actions,
                resources=resources,
                sid=raw.get("sid") if isinstance(raw.get("sid"), str) else None,
            )
        )
    return statements


def _token_allow(
    ctx: CallContext,
    action: str,
    resource: str,
    actor: Subject,
    user_id: str | None,
) -> EffectiveStatement | None:
    for index, statement in enumerate(token_statements(ctx)):
        effective = EffectiveStatement(statement, "token", index)
        if (
            _statement_matches(effective, action, resource, actor.principal_id, user_id)
            is not None
        ):
            return effective
    return None


# Stand-ins for an org, a workspace and an id that no literal character
# matches: a pattern matching them at both lengths has only wildcards there,
# a "*" among them, so it matches every non-empty value.
_PROBES = ("\x00", "\x00\x00")


# The literal ":<service>:<type>/<id>" end of a pattern (ids hold no raw ":").
_NAMED_TYPE = re.compile(r":([a-z][a-z0-9_]*):([a-z][a-z0-9_]*)/[^:]*$")


def _may_name_type(pattern: str, service: str, resource_type: str) -> bool:
    """Whether ``pattern`` may match some resource of the type."""
    named = _NAMED_TYPE.search(pattern)
    if named is None:
        return True
    return named.groups() == (service, resource_type)


def _spans_type(
    subject: Subject,
    action: str,
    service: str,
    resource_type: str,
    user_id: str | None,
) -> bool:
    probes = [f"abi:{p}:{p}:{service}:{resource_type}/{p}" for p in _PROBES]
    spanning = False
    for effective in subject.statements:
        statement = effective.statement
        if not any(matches(pattern, action) for pattern in statement.actions):
            continue
        if statement.effect == "Deny":
            return False  # it may deny one of them: check each
        if effective.bounds:
            continue  # a sub-policy's parent may leave some of them out
        values = _values(effective, subject.principal_id, user_id)
        for pattern in statement.resources:
            expanded = substitute(pattern, values)
            if expanded is not None and all(matches(expanded, p) for p in probes):
                spanning = True
    return spanning


def _hints(
    statements: Iterable[EffectiveStatement],
    action: str,
    principal_id: str,
    user_id: str | None,
) -> list[str]:
    prefixes: set[str] = set()
    for effective in statements:
        statement = effective.statement
        if statement.effect != "Allow":
            continue
        if not any(matches(pattern, action) for pattern in statement.actions):
            continue
        values = _values(effective, principal_id, user_id)
        for pattern in statement.resources:
            expanded = substitute(pattern, values)
            if expanded is not None:
                prefixes.add(literal_prefix(expanded))
    if "" in prefixes:
        return [""]
    # A prefix that extends another adds nothing to a scan.
    ordered = sorted(prefixes)
    kept: list[str] = []
    for prefix in ordered:
        if not any(prefix.startswith(shorter) for shorter in kept):
            kept.append(prefix)
    return kept
