"""The evaluator reads only the statements that name the action it decides.

``filter``, ``check`` and ``explain`` decide one action: a statement whose
actions do not match it can neither allow nor deny, so each subject is narrowed
to the statements that name it once per call, before the per-resource loop.
The decisions are those of the unnarrowed algorithm (``Evaluator._decide`` on the
whole subjects), checked here over generated policies.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any, Literal

import pytest

from naas_abi_core.engine.call_context import CallContext, Principal
from naas_abi_core.services.iam import evaluator as evaluator_module
from naas_abi_core.services.iam.catalog import CatalogRegistry
from naas_abi_core.services.iam.evaluator import Evaluator
from naas_abi_core.services.iam.IAMPorts import (
    Bound,
    Decision,
    EffectiveStatement,
    PolicySource,
    Seal,
    Subject,
)
from naas_abi_core.services.iam.names import PLATFORM
from naas_abi_core.services.iam.policy import Statement
from naas_abi_core.services.iam.tests.iam_harness import (
    NEXUS,
    TRIPLE_STORE,
    below,
    graph,
    org,
    workspace,
)

QUERY = "triple_store:Query"
INSERT = "triple_store:Insert"
DROP = "triple_store:DropGraph"
GET_WS = "nexus:GetWorkspace"

ORGS = ("org-1", "org-2")
WORKSPACES = ("ws-1", "ws-2", "ws-3")


class _Source(PolicySource):
    def __init__(
        self,
        actor: Subject | None,
        user: Subject | None,
        seals: Sequence[Seal] = (),
    ) -> None:
        self._actor = actor
        self._user = user
        self._seals = tuple(seals)
        self._catalogs = CatalogRegistry()
        self._catalogs.register(NEXUS)
        self._catalogs.register(TRIPLE_STORE)

    def subject(
        self, ctx: CallContext, side: Literal["actor", "user"]
    ) -> Subject | None:
        return self._actor if side == "actor" else self._user

    def seals(self) -> Sequence[Seal]:
        return self._seals

    @property
    def catalogs(self) -> CatalogRegistry:
        return self._catalogs


# -- generated policies ------------------------------------------------------------

ACTIONS = (
    QUERY,
    INSERT,
    DROP,
    GET_WS,
    "triple_store:*",
    "triple_store:Q*",
    "*:Get*",
    "*",
)


def _scope(rng: random.Random) -> str | None:
    o = rng.choice(ORGS)
    return rng.choice(
        [None, PLATFORM, org(o), below(o), workspace(rng.choice(WORKSPACES), o)]
    )


def _resource_pattern(rng: random.Random) -> str:
    o, w = rng.choice(ORGS), rng.choice(WORKSPACES)
    return rng.choice(
        [
            graph(f"g{rng.randint(1, 3)}", o, w),
            graph("*", o, w),
            graph("${user.id}*", o, w),
            graph("${principal.id}", o, w),
            "${scope}/triple_store:graph/*",
            "${scope}/*",
            "${scope}",
            below(o),
            workspace(w, o),
            "abi:*",
            "*",
        ]
    )


def _statement(rng: random.Random, effect: str | None = None) -> Statement:
    return Statement(
        effect=effect or rng.choice(["Allow", "Allow", "Allow", "Deny"]),  # type: ignore[arg-type]
        actions=tuple(rng.sample(ACTIONS, rng.randint(1, 2))),
        resources=tuple(_resource_pattern(rng) for _ in range(rng.randint(1, 2))),
        sid=rng.choice([None, f"s{rng.randint(1, 99)}"]),
    )


def _bounds(rng: random.Random) -> tuple[Bound, ...]:
    if rng.random() < 0.7:
        return ()
    return tuple(
        Bound(
            policy_id=f"parent-{index}",
            allows=tuple(
                (i, _statement(rng, "Allow")) for i in range(rng.randint(1, 2))
            ),
        )
        for index in range(rng.randint(1, 2))
    )


def _subject(rng: random.Random, principal_id: str, count: int) -> Subject:
    statements = []
    for index in range(count):
        statement = _statement(rng)
        statements.append(
            EffectiveStatement(
                statement=statement,
                policy_id=f"pol-{rng.randint(1, 9)}",
                statement_index=index,
                attachment_id=rng.choice([None, f"att-{index}"]),
                scope=_scope(rng),
                via_group=rng.choice([None, "grp-1"]),
                bounds=_bounds(rng) if statement.effect == "Allow" else (),
                through=rng.choice([(), ("sub-1",)]),
            )
        )
    return Subject(
        principal_id=principal_id,
        status=rng.choice(["active"] * 9 + ["suspended"]),  # type: ignore[arg-type]
        statements=tuple(statements),
    )


def _resources() -> list[str]:
    found = []
    for o in ORGS:
        found.append(org(o))
        for w in WORKSPACES:
            found.append(workspace(w, o))
            for g in ("g1", "g2", "g3", "usr-1-notes", "sa-1"):
                found.append(graph(g, o, w))
    found.append(f"{PLATFORM}triple_store:view/v1")
    return found


def _token_scope(rng: random.Random) -> tuple[Mapping[str, Any], ...] | None:
    """A token's ``abi_scope``, as the token carries it: Allow statements."""
    if rng.random() < 0.6:
        return None
    return tuple(_statement(rng, "Allow").to_dict() for _ in range(rng.randint(1, 2)))


def _case(seed: int):
    rng = random.Random(seed)
    user_principal = Principal(id="usr-1", kind="user")
    obo = rng.random() < 0.5
    if obo:
        ctx = CallContext(
            principal=Principal(id="sa-1", kind="service_account", name="api"),
            on_behalf_of=user_principal,
            scope=_token_scope(rng),
        )
        actor = _subject(rng, "sa-1", rng.randint(0, 25))
        user = _subject(rng, "usr-1", rng.randint(0, 25))
    else:
        ctx = CallContext(principal=user_principal, scope=_token_scope(rng))
        actor = _subject(rng, "usr-1", rng.randint(0, 25))
        user = None
    seals = (
        [Seal(pattern=graph("g3", "org-1", "ws-1"), owner=rng.choice(["api", "x"]))]
        if rng.random() < 0.3
        else []
    )
    return ctx, actor, user, seals


def _reference_check(
    evaluator: Evaluator,
    ctx: CallContext,
    actor: Subject | None,
    user: Subject | None,
    action: str,
    resource: str,
    source: _Source,
) -> Decision:
    """``check`` as the unnarrowed algorithm decides it."""
    explanation = evaluator._decide(ctx, actor, user, action, resource)
    if explanation.allowed:
        return Decision(True, True, explanation.reason)
    from naas_abi_core.services.iam.names import parse_resource_name

    try:
        name = parse_resource_name(resource)
    except ValueError:
        visible = False
    else:
        visible = any(
            evaluator._decide(ctx, actor, user, other, resource).allowed
            for other in source.catalogs.actions_on(name.service, name.type)
        )
    return Decision(False, visible, explanation.reason)


@pytest.mark.parametrize("seed", range(150))
def test_narrowed_decisions_are_the_unnarrowed_ones(seed: int) -> None:
    ctx, actor, user, seals = _case(seed)
    source = _Source(actor, user, seals)
    evaluator = Evaluator(source)
    resources = _resources()
    for action in (QUERY, INSERT, DROP, GET_WS):
        expected = [
            evaluator._decide(ctx, actor, user, action, resource)
            for resource in resources
        ]
        result = evaluator.filter(ctx, action, resources)
        assert result.allowed == [e.resource for e in expected if e.allowed]
        assert result.prefix_hints == evaluator._prefix_hints(ctx, actor, user, action)
        for resource, explanation in zip(resources, expected):
            assert evaluator.explain(ctx, action, resource) == explanation
            assert evaluator.check(ctx, action, resource) == _reference_check(
                evaluator, ctx, actor, user, action, resource, source
            )


def test_the_generated_cases_reach_every_outcome() -> None:
    """Allows, Denies, seals, suspended principals, and tokens that narrow what
    both sides allow: the comparison above means something."""
    reasons: set[str] = set()
    token_narrowed = False
    for seed in range(150):
        ctx, actor, user, seals = _case(seed)
        evaluator = Evaluator(_Source(actor, user, seals))
        tokenless = Evaluator(_Source(actor, user, seals))
        for action in (QUERY, INSERT, DROP, GET_WS):
            for resource in _resources():
                decided = evaluator._decide(ctx, actor, user, action, resource)
                reasons.add(decided.reason)
                if ctx.scope is not None and not decided.allowed:
                    without = replace(ctx, scope=None)
                    if tokenless._decide(
                        without, actor, user, action, resource
                    ).allowed:
                        token_narrowed = True
    assert {"allow", "explicit_deny", "implicit_deny", "sealed", "suspended"} <= reasons
    assert token_narrowed


# -- at scale: one statement per workspace names the action ----------------------------


def _admin_of_many_workspaces(
    workspaces: int, statements_per_workspace: int
) -> Subject:
    """A user granted a role in each workspace: one statement of each grant names
    ``nexus:UseFeature``, the others other actions."""
    statements: list[EffectiveStatement] = []
    for w in range(workspaces):
        scope = workspace(f"ws-{w}", "org-1")
        for i in range(statements_per_workspace):
            action = "nexus:UseFeature" if i == 0 else f"svc{i}:Action{i}"
            statements.append(
                EffectiveStatement(
                    statement=Statement(
                        effect="Allow",
                        actions=(action,),
                        resources=("${scope}/*",),
                    ),
                    policy_id=f"pol-{i}",
                    statement_index=i,
                    attachment_id=f"att-{w}-{i}",
                    scope=scope,
                )
            )
    return Subject("usr-1", "active", tuple(statements))


def test_filter_visits_only_the_statements_naming_the_action(monkeypatch) -> None:
    workspaces, per_workspace, features = 40, 25, 15
    user = _admin_of_many_workspaces(workspaces, per_workspace)
    ctx = CallContext(principal=Principal(id="usr-1", kind="user"))
    evaluator = Evaluator(_Source(user, None))
    resources = [
        f"{workspace(f'ws-{w}', 'org-1')}/nexus:feature/f{f}"
        for w in range(workspaces)
        for f in range(features)
    ]

    visits = 0
    original = evaluator_module._statement_matches

    def counting(*args, **kwargs):
        nonlocal visits
        visits += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(evaluator_module, "_statement_matches", counting)

    result = evaluator.filter(ctx, "nexus:UseFeature", resources)

    assert result.allowed == resources
    # Unnarrowed, each resource would walk every statement of the subject
    # (40 x 25 = 1,000 of them): 600,000 visits. Narrowed, only the 40 that
    # name the action (a Deny among them could still win): 24,000.
    assert visits <= len(resources) * workspaces
