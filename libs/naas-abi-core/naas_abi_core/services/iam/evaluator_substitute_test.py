"""The evaluator substitutes a statement's patterns once per distinct value set.

A pattern's expansion depends on the pattern and on ``${scope}``,
``${principal.id}`` and ``${user.id}``, never on the resource decided: one
``filter`` over a feature flag of each of a platform admin's workspaces asked the
same few expansions thousands of times. ``evaluator._expanded`` keeps them. The
decisions are those of a plain ``substitute`` on each call, checked here over
the generated policies of ``evaluator_narrow_test``.
"""

from __future__ import annotations

import pytest

from naas_abi_core.engine.call_context import CallContext, Principal
from naas_abi_core.services.iam import evaluator as evaluator_module
from naas_abi_core.services.iam import names
from naas_abi_core.services.iam.evaluator import Evaluator
from naas_abi_core.services.iam.evaluator_narrow_test import (
    DROP,
    GET_WS,
    INSERT,
    QUERY,
    _admin_of_many_workspaces,
    _case,
    _resources,
    _Source,
)
from naas_abi_core.services.iam.tests.iam_harness import workspace


def _plain(pattern, scope, principal_id, user_id):
    """``_expanded`` without the cache: ``substitute`` on every call."""
    return names.substitute(
        pattern, {"scope": scope, "principal.id": principal_id, "user.id": user_id}
    )


@pytest.mark.parametrize("seed", range(150))
def test_kept_expansions_decide_what_plain_substitution_does(
    seed: int, monkeypatch
) -> None:
    ctx, actor, user, seals = _case(seed)
    resources = _resources()
    actions = (QUERY, INSERT, DROP, GET_WS)

    def decisions(evaluator: Evaluator):
        return [
            (
                evaluator.filter(ctx, action, resources),
                [evaluator.explain(ctx, action, r) for r in resources],
                [evaluator.check(ctx, action, r) for r in resources],
            )
            for action in actions
        ]

    evaluator_module._expanded.cache_clear()
    kept = decisions(Evaluator(_Source(actor, user, seals)))
    # Asked again: answered from the kept expansions.
    again = decisions(Evaluator(_Source(actor, user, seals)))
    with monkeypatch.context() as patched:
        patched.setattr(evaluator_module, "_expanded", _plain)
        plain = decisions(Evaluator(_Source(actor, user, seals)))
    assert kept == plain
    assert again == plain


def test_a_filter_substitutes_each_pattern_once_per_scope(monkeypatch) -> None:
    workspaces, per_workspace, features = 40, 25, 15
    user = _admin_of_many_workspaces(workspaces, per_workspace)
    ctx = CallContext(principal=Principal(id="usr-1", kind="user"))
    evaluator = Evaluator(_Source(user, None))
    resources = [
        f"{workspace(f'ws-{w}', 'org-1')}/nexus:feature/f{f}"
        for w in range(workspaces)
        for f in range(features)
    ]

    calls = 0
    original = names.substitute

    def counting(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(evaluator_module, "substitute", counting)
    evaluator_module._expanded.cache_clear()

    result = evaluator.filter(ctx, "nexus:UseFeature", resources)

    assert result.allowed == resources
    # Each resource used to expand every statement naming the action: 600
    # resources x 40 statements = 24,000 substitutions. One pattern per
    # workspace scope: 40 (and the prefix hints', computed once per call).
    assert calls <= 2 * workspaces
    calls = 0
    evaluator.filter(ctx, "nexus:UseFeature", resources)
    assert calls <= workspaces  # the next call reuses them: only the hints'
